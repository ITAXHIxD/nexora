import discord
from discord.ext import commands
from discord import app_commands

import aiohttp
import re
import logging

from io import BytesIO
from PIL import Image
from typing import Optional, List

logger = logging.getLogger(__name__)

# ================= REGEX =================

EMOJI_REGEX = re.compile(r"<(a)?:([a-zA-Z0-9_]+):(\d+)>")
IMAGE_URL_REGEX = re.compile(
    r"https?:\/\/\S+\.(?:png|jpg|jpeg|gif|webp)(?:\?\S*)?",
    re.IGNORECASE
)

# ================= HELPERS =================

def clean_name(name: str, fallback="emoji") -> str:
    name = re.sub(r"[^a-zA-Z0-9_]", "", name)
    if len(name) < 2:
        name = f"{fallback}_x"
    return name[:32]


def compress_emoji(data: bytes) -> bytes:
    img = Image.open(BytesIO(data)).convert("RGBA")
    img.thumbnail((128, 128), Image.Resampling.LANCZOS)
    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    out.seek(0)
    return out.read()


def prepare_sticker(data: bytes) -> bytes:
    img = Image.open(BytesIO(data)).convert("RGBA")
    img.thumbnail((320, 320), Image.Resampling.LANCZOS)
    out = BytesIO()
    img.save(out, format="PNG", optimize=True)
    out.seek(0)
    return out.read()


# ================= MODALS =================

class EmojiNameModal(discord.ui.Modal):
    def __init__(self, default_name: str, callback):
        super().__init__(title="Emoji Name")
        self.callback = callback

        self.name = discord.ui.TextInput(
            label="Emoji Name",
            min_length=2,
            max_length=32,
            default=default_name
        )
        self.add_item(self.name)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "⏳ Creating emoji…", ephemeral=True
        )
        await self.callback(interaction, clean_name(self.name.value))


class StickerModal(discord.ui.Modal):
    def __init__(self, default_name: str, callback):
        super().__init__(title="Sticker Details")
        self.callback = callback

        self.name = discord.ui.TextInput(
            label="Sticker Name",
            min_length=2,
            max_length=30,
            default=default_name
        )
        self.desc = discord.ui.TextInput(
            label="Description",
            max_length=100,
            required=False
        )
        self.emoji = discord.ui.TextInput(
            label="Emoji Tag",
            max_length=5,
            required=False
        )

        self.add_item(self.name)
        self.add_item(self.desc)
        self.add_item(self.emoji)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.send_message(
            "⏳ Creating sticker…", ephemeral=True
        )
        await self.callback(
            interaction,
            clean_name(self.name.value, "sticker"),
            self.desc.value or "Stolen sticker",
            self.emoji.value or "😀"
        )


# ================= VIEW =================

class StealView(discord.ui.View):
    def __init__(self, ctx, image: bytes, name: str, animated: bool):
        super().__init__(timeout=60)
        self.ctx = ctx
        self.image = image
        self.name = name
        self.animated = animated

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.ctx.author.id:
            await interaction.response.send_message(
                "❌ You didn’t run this command.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Add as Emoji", style=discord.ButtonStyle.green)
    async def emoji_button(self, interaction: discord.Interaction, _):
        async def create(inter, name):
            try:
                data = compress_emoji(self.image)
                emoji = await self.ctx.guild.create_custom_emoji(
                    name=name,
                    image=data,
                    reason=f"Requested by {self.ctx.author}"
                )
                await inter.followup.send(f"✅ Created {emoji}", ephemeral=True)
            except discord.HTTPException as e:
                await inter.followup.send(f"❌ {e}", ephemeral=True)

        await interaction.response.send_modal(
            EmojiNameModal(self.name, create)
        )

    @discord.ui.button(label="Add as Sticker", style=discord.ButtonStyle.blurple)
    async def sticker_button(self, interaction: discord.Interaction, _):
        if self.animated:
            return await interaction.response.send_message(
                "❌ Animated images can’t be stickers.",
                ephemeral=True
            )

        async def create(inter, name, desc, emoji):
            try:
                data = prepare_sticker(self.image)
                file = discord.File(BytesIO(data), filename="sticker.png")

                sticker = await self.ctx.guild.create_sticker(
                    name=name,
                    description=desc,
                    emoji=emoji,
                    file=file,
                    reason=f"Requested by {self.ctx.author}"
                )
                await inter.followup.send(
                    f"✅ Created sticker `{sticker.name}`",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                await inter.followup.send(f"❌ {e}", ephemeral=True)

        await interaction.response.send_modal(
            StickerModal(self.name, create)
        )


# ================= COG =================

class Steal(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.session: Optional[aiohttp.ClientSession] = None

    async def cog_load(self):
        self.session = aiohttp.ClientSession()

    async def cog_unload(self):
        if self.session:
            await self.session.close()

    async def fetch(self, url: str) -> Optional[bytes]:
        try:
            async with self.session.get(url) as r:
                if r.status == 200:
                    return await r.read()
        except Exception as e:
            logger.error("Download error: %s", e)
        return None

    def parse_emojis(self, text: str) -> List[dict]:
        out = []
        for a, name, eid in EMOJI_REGEX.findall(text):
            animated = bool(a)
            ext = "gif" if animated else "png"
            out.append({
                "name": name,
                "animated": animated,
                "url": f"https://cdn.discordapp.com/emojis/{eid}.{ext}"
            })
        return out

    # ================= COMMAND =================

    @commands.hybrid_command(name="steal")
    @commands.has_permissions(manage_emojis=True)
    @commands.bot_has_permissions(manage_emojis=True)
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def steal(
        self,
        ctx: commands.Context,
        emoji: Optional[str] = None
    ):
        if not ctx.guild:
            return await ctx.send("❌ Server only.")

        await ctx.defer()

        url = None
        name = "emoji"
        animated = False

        # -------- STRING INPUT --------
        if emoji:
            parsed = self.parse_emojis(emoji)
            if parsed:
                url = parsed[0]["url"]
                name = parsed[0]["name"]
                animated = parsed[0]["animated"]

            elif IMAGE_URL_REGEX.search(emoji):
                url = IMAGE_URL_REGEX.search(emoji).group(0)
                animated = url.endswith(".gif")

                if "name=" in url:
                    try:
                        name = clean_name(url.split("name=")[1].split("&")[0])
                    except Exception:
                        pass

        # -------- ATTACHMENT --------
        if not url and ctx.message.attachments:
            att = ctx.message.attachments[0]
            if att.content_type and att.content_type.startswith("image/"):
                url = att.url
                name = att.filename.split(".")[0]

        if not url:
            return await ctx.send("❌ No emoji or image found.")

        data = await self.fetch(url)
        if not data:
            return await ctx.send("❌ Failed to download image.")

        embed = discord.Embed(
            title="🎨 Choose Action",
            description=f"**Name:** `{clean_name(name)}`\n"
                        f"**Animated:** {'Yes' if animated else 'No'}",
            color=discord.Color.blue()
        )
        embed.set_image(url=url)

        await ctx.send(
            embed=embed,
            view=StealView(ctx, data, clean_name(name), animated)
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Steal(bot))

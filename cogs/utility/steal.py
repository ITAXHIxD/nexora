import asyncio
import discord
from discord.ext import commands
from discord import app_commands

import aiohttp
import re
import logging

from io import BytesIO
from PIL import Image
from typing import Optional, List

from utils.ui import (
    BRAND_COLOR,
    SUCCESS_COLOR,
    NexoraView,
    DismissButton,
    send_view,
)

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

class StealLayoutView(NexoraView):
    """Components V2 asset manager for importing emojis and stickers."""

    def __init__(self, ctx: commands.Context, image: bytes, name: str, animated: bool, preview_url: str):
        super().__init__(bot=ctx.bot, user_id=ctx.author.id, color=BRAND_COLOR, timeout=120)
        self.ctx = ctx
        self.image = image
        self.name = name
        self.animated = animated
        self.preview_url = preview_url
        self._build()

    def _build(self):
        self.clear_container()
        format_badge = "🎞️ **Animated GIF**" if self.animated else "🖼️ **Static Image**"
        header = (
            f"# 🎨 Asset Importer · Preview\n"
            f"> **Suggested Name:** `{self.name}` · Type: {format_badge}\n"
            f"> Ready to convert and add to **{self.ctx.guild.name}**."
        )
        self.add_section(header, thumbnail_url=self.preview_url)
        self.add_separator(discord.SeparatorSpacing.small)

        note = (
            "### 💡 Choose Import Mode\n"
            "• **Custom Emoji:** Compresses and installs directly into server emoji slots.\n"
            "• **Custom Sticker:** Scales and installs as a server sticker *(static only)*."
        )
        self.add_text(note)
        self.add_footer(f"Requested by {self.ctx.author.display_name} · Permissions: Manage Expressions")

        btn_emoji = discord.ui.Button(
            label="Add as Emoji",
            emoji="😃",
            style=discord.ButtonStyle.success,
        )
        btn_emoji.callback = self._on_emoji

        btn_sticker = discord.ui.Button(
            label="Add as Sticker",
            emoji="🏷️",
            style=discord.ButtonStyle.primary,
            disabled=self.animated,
        )
        btn_sticker.callback = self._on_sticker

        dismiss = DismissButton(user_id=self.ctx.author.id)
        self.add_row(btn_emoji, btn_sticker, dismiss)

    async def _on_emoji(self, interaction: discord.Interaction):
        async def create(inter, name):
            try:
                data = await asyncio.to_thread(compress_emoji, self.image)
                emoji = await self.ctx.guild.create_custom_emoji(
                    name=name,
                    image=data,
                    reason=f"Requested by {self.ctx.author}"
                )
                await inter.followup.send(f"✅ Successfully created custom emoji {emoji} (`:{emoji.name}:`)!", ephemeral=True)
            except discord.HTTPException as e:
                await inter.followup.send(f"❌ Failed to create emoji: {e}", ephemeral=True)

        await interaction.response.send_modal(
            EmojiNameModal(self.name, create)
        )

    async def _on_sticker(self, interaction: discord.Interaction):
        if self.animated:
            return await interaction.response.send_message(
                "❌ Animated images cannot be uploaded as stickers.",
                ephemeral=True
            )

        async def create(inter, name, desc, emoji):
            try:
                data = await asyncio.to_thread(prepare_sticker, self.image)
                file = discord.File(BytesIO(data), filename="sticker.png")

                sticker = await self.ctx.guild.create_sticker(
                    name=name,
                    description=desc,
                    emoji=emoji,
                    file=file,
                    reason=f"Requested by {self.ctx.author}"
                )
                await inter.followup.send(
                    f"✅ Successfully created server sticker **{sticker.name}**!",
                    ephemeral=True
                )
            except discord.HTTPException as e:
                await inter.followup.send(f"❌ Failed to create sticker: {e}", ephemeral=True)

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
        session = getattr(self.bot, "session", None)
        if session is None or session.closed:
            if self.session is None or self.session.closed:
                self.session = aiohttp.ClientSession()
            session = self.session
        try:
            async with session.get(url) as r:
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
        if not url and ctx.message and ctx.message.attachments:
            att = ctx.message.attachments[0]
            if (att.content_type and att.content_type.startswith("image/")) or att.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                url = att.url
                name = att.filename.split(".")[0]
                animated = att.filename.lower().endswith(".gif")

        # -------- REPLIED MESSAGE SUPPORT --------
        if not url and ctx.message and ctx.message.reference and ctx.message.reference.message_id:
            ref_msg = getattr(ctx.message.reference, "resolved", None)
            if not isinstance(ref_msg, discord.Message):
                try:
                    ref_msg = await ctx.channel.fetch_message(ctx.message.reference.message_id)
                except Exception:
                    ref_msg = None
            if isinstance(ref_msg, discord.Message):
                if ref_msg.stickers:
                    stk = ref_msg.stickers[0]
                    url = stk.url
                    name = stk.name
                    animated = url.lower().endswith(".gif")
                elif ref_msg.content:
                    parsed = self.parse_emojis(ref_msg.content)
                    if parsed:
                        url = parsed[0]["url"]
                        name = parsed[0]["name"]
                        animated = parsed[0]["animated"]
                if not url and ref_msg.attachments:
                    att = ref_msg.attachments[0]
                    url = att.url
                    name = att.filename.split(".")[0]
                    animated = att.filename.lower().endswith(".gif")

        if not url:
            return await ctx.send("❌ Provide a custom emoji, image URL, attachment, or reply to a message containing an emoji/sticker!")

        data = await self.fetch(url)
        if not data:
            return await ctx.send("❌ Failed to download image.")

        view = StealLayoutView(ctx, data, clean_name(name), animated, preview_url=url)
        await send_view(ctx, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Steal(bot))

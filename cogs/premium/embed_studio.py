"""
cogs/premium/embed_studio.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enterprise Embed & Announcement Studio for Nexora Premium.

Permits server managers in premium guilds to craft, live-preview,
and dispatch state-of-the-art embeds to any channel.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    PREMIUM_COLOR,
    SUCCESS_COLOR,
    ERROR_COLOR,
    CYAN_COLOR,
)

logger = logging.getLogger(__name__)


class EmbedEditorModal(discord.ui.Modal, title="🎨 Embed Studio Composer"):
    embed_title = discord.ui.TextInput(
        label="Embed Title",
        placeholder="e.g. 📢 Server Announcement / Official Guidelines",
        max_length=256,
        required=True,
    )
    embed_desc = discord.ui.TextInput(
        label="Description / Body (Markdown supported)",
        placeholder="Write your announcement body here...",
        style=discord.TextStyle.paragraph,
        max_length=3500,
        required=True,
    )
    embed_color = discord.ui.TextInput(
        label="Hex Color Code",
        placeholder="e.g. #5865F2, #FFB800, #00D2FF (or leave blank)",
        max_length=16,
        required=False,
    )
    embed_image = discord.ui.TextInput(
        label="Banner Image URL (Optional)",
        placeholder="https://example.com/banner.png",
        max_length=512,
        required=False,
    )
    embed_footer = discord.ui.TextInput(
        label="Footer Text (Optional)",
        placeholder="e.g. Nexora Community · Stay Awesome",
        max_length=256,
        required=False,
    )

    def __init__(self, original_embed: Optional[discord.Embed] = None):
        super().__init__()
        if original_embed:
            if original_embed.title:
                self.embed_title.default = original_embed.title
            if original_embed.description:
                self.embed_desc.default = original_embed.description
            if original_embed.color:
                self.embed_color.default = f"#{original_embed.color.value:06X}"
            if original_embed.image and original_embed.image.url:
                self.embed_image.default = original_embed.image.url
            if original_embed.footer and original_embed.footer.text:
                self.embed_footer.default = original_embed.footer.text

    async def on_submit(self, interaction: discord.Interaction):
        color_val = BRAND_COLOR
        if self.embed_color.value:
            clean = self.embed_color.value.lstrip("#").replace("0x", "").strip()
            if re.fullmatch(r"[0-9a-fA-F]{6}", clean):
                color_val = int(clean, 16)

        new_embed = discord.Embed(
            title=self.embed_title.value.strip(),
            description=self.embed_desc.value.strip(),
            color=color_val,
            timestamp=datetime.now(timezone.utc),
        )

        if self.embed_image.value and self.embed_image.value.startswith("http"):
            new_embed.set_image(url=self.embed_image.value.strip())

        if self.embed_footer.value:
            new_embed.set_footer(text=self.embed_footer.value.strip())

        preview_view = EmbedPreviewView(interaction.user, new_embed)
        await interaction.response.send_message(
            content="👀 **Embed Preview** (Visible only to you). Use the action buttons below to edit or dispatch:",
            embed=new_embed,
            view=preview_view,
            ephemeral=True,
        )


class ChannelSelect(discord.ui.ChannelSelect):
    def __init__(self, embed_to_send: discord.Embed):
        super().__init__(
            placeholder="Choose target channel to dispatch embed...",
            channel_types=[discord.ChannelType.text, discord.ChannelType.news],
            min_values=1,
            max_values=1,
        )
        self.embed_to_send = embed_to_send

    async def callback(self, interaction: discord.Interaction):
        target_channel = self.values[0]
        if not target_channel.permissions_for(interaction.guild.me).send_messages:
            return await interaction.response.send_message(f"❌ I don't have permission to send messages in {target_channel.mention}!", ephemeral=True)

        try:
            msg = await target_channel.send(embed=self.embed_to_send)
            await interaction.response.send_message(f"🚀 **Embed successfully dispatched to {target_channel.mention}!** [Jump to Message]({msg.jump_url})", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Failed to dispatch embed: `{e}`", ephemeral=True)


class EmbedPreviewView(discord.ui.View):
    def __init__(self, requester: discord.abc.User, built_embed: discord.Embed):
        super().__init__(timeout=300)
        self.requester = requester
        self.built_embed = built_embed

    @discord.ui.button(label="Send to Channel", emoji="🚀", style=discord.ButtonStyle.success, row=0)
    async def btn_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel_view = discord.ui.View(timeout=60)
        channel_view.add_item(ChannelSelect(self.built_embed))
        await interaction.response.send_message("Select the channel where you'd like to publish this announcement:", view=channel_view, ephemeral=True)

    @discord.ui.button(label="Edit Content", emoji="✏️", style=discord.ButtonStyle.primary, row=0)
    async def btn_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(EmbedEditorModal(original_embed=self.built_embed))

    @discord.ui.button(label="Discard", emoji="🗑️", style=discord.ButtonStyle.danger, row=0)
    async def btn_discard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


class EmbedStudio(commands.Cog):
    """Enterprise announcement and custom embed composer."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_premium(self, guild_id: int) -> bool:
        checker = getattr(self.bot, "is_premium_guild", None)
        if checker:
            return await checker(guild_id)
        return False

    @commands.hybrid_command(name="embed_studio", description="Open the enterprise embed builder & announcement composer", aliases=["embed_builder"])
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def embed_studio(self, ctx: commands.Context):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**: The Embed & Announcement Studio requires an active server subscription. Use `/premium_price` to learn more!", ephemeral=True)

        if ctx.interaction:
            await ctx.interaction.response.send_modal(EmbedEditorModal())
        else:
            view = discord.ui.View(timeout=120)
            btn = discord.ui.Button(label="Open Embed Composer", emoji="🎨", style=discord.ButtonStyle.primary)

            async def on_click(interaction: discord.Interaction):
                if interaction.user.id != ctx.author.id:
                    return await interaction.response.send_message("❌ This composer belongs to someone else.", ephemeral=True)
                await interaction.response.send_modal(EmbedEditorModal())

            btn.callback = on_click
            view.add_item(btn)
            await ctx.send("Click the button below to launch the **Embed Composer** modal:", view=view)


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedStudio(bot))
    logger.debug("Loaded EmbedStudio Cog")

"""
cogs/info/randomavatar.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Random Server Member Showcase
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    PURPLE_COLOR,
    SUCCESS_COLOR,
    NexoraView,
    DismissButton,
    send_view,
    ts_format,
    status_badge,
)

logger = logging.getLogger(__name__)


class RandomAvatarView(NexoraView):
    """Interactive Components V2 view for exploring random guild members."""

    def __init__(
        self,
        bot: commands.Bot,
        guild: discord.Guild,
        target: discord.Member,
        requester: discord.abc.User,
        current_tab: str = "avatar",
        timeout: float = 120,
    ):
        super().__init__(
            bot=bot,
            user_id=requester.id,
            color=BRAND_COLOR if current_tab == "avatar" else PURPLE_COLOR,
            timeout=timeout,
        )
        self.guild = guild
        self.target = target
        self.requester = requester
        self.current_tab = current_tab
        self._build()

    def _build(self):
        self.clear_container()
        u = self.target
        avatar_url = str(u.display_avatar.with_size(1024).url)

        if self.current_tab == "avatar":
            is_animated = u.display_avatar.is_animated()
            formats = [
                f"[PNG]({u.display_avatar.with_format('png').with_size(1024).url})",
                f"[WebP]({u.display_avatar.with_format('webp').with_size(1024).url})",
                f"[JPG]({u.display_avatar.with_format('jpeg').with_size(1024).url})",
            ]
            if is_animated:
                formats.insert(0, f"[GIF]({u.display_avatar.with_format('gif').with_size(1024).url})")

            header_text = (
                f"# 🎲 {u.display_name}\n"
                f"> `@{u.name}` · ID: `{u.id}`\n\n"
                f"**High-Res Downloads (1024px):**\n"
                f"{'  ·  '.join(formats)}"
            )
            self.add_section(header_text, thumbnail_url=avatar_url)

        elif self.current_tab == "profile":
            created_str = f"{ts_format(u.created_at, 'D')} ({ts_format(u.created_at, 'R')})"
            joined_str = f"{ts_format(u.joined_at, 'D')} ({ts_format(u.joined_at, 'R')})" if u.joined_at else "Unknown"
            top_role = u.top_role.mention if u.top_role.name != "@everyone" else "`None`"

            profile_text = (
                f"# 👤 {u.display_name} · Dossier\n"
                f"> `@{u.name}` · Status: {status_badge(u.status)}\n\n"
                f"• **Account Created:** {created_str}\n"
                f"• **Joined Server:** {joined_str}\n"
                f"• **Top Role:** {top_role} · Roles: `{len(u.roles) - 1}`"
            )
            self.add_section(profile_text, thumbnail_url=avatar_url)

        self.add_footer(f"Requested by {self.requester.display_name} · Random Guild Explorer")

        # Interactive controls
        btn_reroll = discord.ui.Button(
            label="Another",
            emoji="🎲",
            style=discord.ButtonStyle.primary,
        )
        btn_reroll.callback = self._on_reroll

        btn_avatar = discord.ui.Button(
            label="Avatar",
            emoji="🖼️",
            style=discord.ButtonStyle.secondary if self.current_tab == "avatar" else discord.ButtonStyle.secondary,
            disabled=(self.current_tab == "avatar"),
        )
        btn_avatar.callback = self._make_tab_callback("avatar")

        btn_profile = discord.ui.Button(
            label="Profile",
            emoji="👤",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_tab == "profile"),
        )
        btn_profile.callback = self._make_tab_callback("profile")

        dismiss = DismissButton(user_id=self.requester.id)
        self.add_row(btn_reroll, btn_avatar, btn_profile, dismiss)

    def _make_tab_callback(self, tab: str):
        async def callback(interaction: discord.Interaction):
            self.current_tab = tab
            self.container.accent_colour = BRAND_COLOR if tab == "avatar" else PURPLE_COLOR
            self._build()
            await interaction.response.edit_message(view=self)
        return callback

    async def _on_reroll(self, interaction: discord.Interaction):
        members = [m for m in self.guild.members if not m.bot and m.id != self.target.id]
        if not members:
            members = [m for m in self.guild.members if not m.bot]
        if not members:
            await interaction.response.send_message("❌ No eligible members found.", ephemeral=True)
            return

        self.target = random.choice(members)
        self._build()
        await interaction.response.edit_message(view=self)


class RandomAvatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="randomavatar",
        description="🎲 Inspect a random member's avatar and profile with live re-roll",
        aliases=["rav"],
    )
    async def randomavatar(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("❌ This command must be used within a server.", ephemeral=True)
            return

        members = [m for m in ctx.guild.members if not m.bot]
        if not members:
            await ctx.send("❌ Could not find any eligible server members.", ephemeral=True)
            return

        user = random.choice(members)
        view = RandomAvatarView(self.bot, ctx.guild, user, ctx.author)
        await send_view(ctx, view)


async def setup(bot):
    await bot.add_cog(RandomAvatar(bot))
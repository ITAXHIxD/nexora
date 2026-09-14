"""
cogs/info/avatar.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Avatar & Media Showcase
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    PURPLE_COLOR,
    NexoraView,
    DismissButton,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)


class AvatarView(NexoraView):
    """Interactive media switcher for Avatar, Banner, and Download assets."""

    def __init__(
        self,
        bot: commands.Bot,
        target: discord.User,
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
        self.target = target
        self.requester = requester
        self.current_tab = current_tab
        self._fetched_user: Optional[discord.User] = None
        self._build()

    async def _ensure_fetched_user(self):
        if not self._fetched_user:
            try:
                self._fetched_user = await self.bot.fetch_user(self.target.id)
            except Exception:
                self._fetched_user = self.target

    def _build(self):
        self.clear_container()
        u = self._fetched_user or self.target
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
                f"# 🖼️ {u.display_name}'s Avatar\n"
                f"> `@{u.name}` · ID: `{u.id}`\n\n"
                f"**Direct High-Res Downloads (1024px):**\n"
                f"{'  ·  '.join(formats)}"
            )
            self.add_section(header_text, thumbnail_url=avatar_url)

        elif self.current_tab == "banner":
            banner = getattr(u, "banner", None)
            if banner:
                banner_url = str(banner.with_size(1024).url)
                is_animated = banner.is_animated()
                formats = [
                    f"[PNG]({banner.with_format('png').with_size(1024).url})",
                    f"[WebP]({banner.with_format('webp').with_size(1024).url})",
                    f"[JPG]({banner.with_format('jpeg').with_size(1024).url})",
                ]
                if is_animated:
                    formats.insert(0, f"[GIF]({banner.with_format('gif').with_size(1024).url})")

                header_text = (
                    f"# 🌆 {u.display_name}'s Banner\n"
                    f"> `@{u.name}` · Accent Color: `#{banner.accent_color.value:06x}`"
                    if banner.accent_color
                    else f"# 🌆 {u.display_name}'s Banner\n> `@{u.name}`"
                )
                header_text += f"\n\n**Direct Banner Downloads (1024px):**\n{'  ·  '.join(formats)}"
                self.add_section(header_text, thumbnail_url=banner_url)
            else:
                header_text = (
                    f"# 🌆 {u.display_name}'s Banner\n"
                    f"> `@{u.name}` does not currently have a custom profile banner set."
                )
                self.add_section(header_text, thumbnail_url=avatar_url)

        elif self.current_tab == "profile":
            created_str = f"{ts_format(u.created_at, 'D')} ({ts_format(u.created_at, 'R')})"
            has_banner = "✅ Yes" if getattr(u, "banner", None) else "❌ None"
            profile_text = (
                f"# 👤 {u.display_name}'s Profile Overview\n"
                f"> Handle: `@{u.name}` · ID: `{u.id}`\n\n"
                f"• **Account Created:** {created_str}\n"
                f"• **Custom Banner:** {has_banner}\n"
                f"• **Avatar Type:** {'🎞️ Animated' if u.display_avatar.is_animated() else '🖼️ Static'}"
            )
            self.add_section(profile_text, thumbnail_url=avatar_url)

        # Footer
        self.add_footer(f"Requested by {self.requester.display_name}")

        # Buttons
        btn_avatar = discord.ui.Button(
            label="Avatar",
            emoji="🖼️",
            style=discord.ButtonStyle.primary if self.current_tab == "avatar" else discord.ButtonStyle.secondary,
            custom_id="av-tab-avatar",
        )
        btn_banner = discord.ui.Button(
            label="Banner",
            emoji="🌆",
            style=discord.ButtonStyle.primary if self.current_tab == "banner" else discord.ButtonStyle.secondary,
            custom_id="av-tab-banner",
        )
        btn_profile = discord.ui.Button(
            label="Profile",
            emoji="👤",
            style=discord.ButtonStyle.primary if self.current_tab == "profile" else discord.ButtonStyle.secondary,
            custom_id="av-tab-profile",
        )

        btn_avatar.callback = self._make_tab_callback("avatar")
        btn_banner.callback = self._make_tab_callback("banner")
        btn_profile.callback = self._make_tab_callback("profile")

        dismiss = DismissButton(user_id=self.requester.id)
        self.add_row(btn_avatar, btn_banner, btn_profile, dismiss)

    def _make_tab_callback(self, tab: str):
        async def callback(interaction: discord.Interaction):
            await self._ensure_fetched_user()
            self.current_tab = tab
            self.container.accent_colour = BRAND_COLOR if tab == "avatar" else PURPLE_COLOR
            self._build()
            await interaction.response.edit_message(view=self)
        return callback


class Avatar(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="avatar",
        description="🖼️ Inspect and download a user's high-resolution avatar or banner",
        aliases=["av", "pfp"],
    )
    @app_commands.describe(user="The user whose avatar or banner you want to view (defaults to yourself)")
    async def avatar(self, ctx: commands.Context, user: Optional[discord.User] = None):
        target = user or ctx.author
        try:
            target = await self.bot.fetch_user(target.id)
        except Exception:
            pass

        view = AvatarView(self.bot, target, ctx.author, current_tab="avatar")
        await send_view(ctx, view)


async def setup(bot):
    await bot.add_cog(Avatar(bot))
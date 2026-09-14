"""
cogs/info/invite.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Bot Invitation Card
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    SUCCESS_COLOR,
    NexoraView,
    DismissButton,
    send_view,
)

logger = logging.getLogger(__name__)


class InviteView(NexoraView):
    """Components V2 invite showcase with direct authorization buttons."""

    def __init__(self, bot: commands.Bot, requester: discord.abc.User, timeout: float = 180):
        super().__init__(bot=bot, user_id=requester.id, color=BRAND_COLOR, timeout=timeout)
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()

        admin_perms = discord.Permissions(administrator=True)
        recommended_perms = discord.Permissions(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            use_external_emojis=True,
            add_reactions=True,
            use_application_commands=True,
            manage_roles=True,
            manage_channels=True,
            kick_members=True,
            ban_members=True,
        )

        admin_url = discord.utils.oauth_url(self.bot.user.id, permissions=admin_perms)
        standard_url = discord.utils.oauth_url(self.bot.user.id, permissions=recommended_perms)
        avatar_url = str(self.bot.user.display_avatar.url) if self.bot.user else None

        # ── Header Section ────────────────────────────────────────────────────
        header_text = (
            "# 🌌 Invite Nexora\n"
            "> Empower your Discord community with a next-generation multipurpose bot."
        )
        self.add_section(header_text, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── Highlights Block ──────────────────────────────────────────────────
        highlights = (
            "### ✨ What Nexora Delivers\n"
            "• 🛡️ **Moderation Engine:** Robust ban, kick, mute, snipe, and audit logging\n"
            "• 🎂 **Birthday Network:** Configurable introductions, countdowns & announcement roles\n"
            "• 📊 **Live Diagnostics:** High-speed server analytics, member tracking & channel stats\n"
            "• 💤 **Smart AFK:** Global or server-specific statuses with DM mention summaries\n"
            "• 🎮 **Fun & Social:** Interactive games, anime reaction cards & Spotify player"
        )
        self.add_text(highlights)

        # ── Footer ────────────────────────────────────────────────────────────
        self.add_footer(f"Requested by {self.requester.display_name} · Built with Components V2")

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_admin = discord.ui.Button(
            label="Invite (Full Admin)",
            emoji="👑",
            style=discord.ButtonStyle.link,
            url=admin_url,
        )
        btn_standard = discord.ui.Button(
            label="Invite (Standard)",
            emoji="🛡️",
            style=discord.ButtonStyle.link,
            url=standard_url,
        )
        dismiss = DismissButton(user_id=self.requester.id)

        self.add_row(btn_admin, btn_standard, dismiss)


class Invite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="invite",
        description="🔗 Get instant authorization links to invite Nexora to your server",
        aliases=["inv"],
    )
    async def invite(self, ctx: commands.Context):
        view = InviteView(self.bot, ctx.author)
        await send_view(ctx, view)


async def setup(bot):
    await bot.add_cog(Invite(bot))
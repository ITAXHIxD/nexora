"""
cogs/info/serverinfo.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Server Information & Analytics Dashboard
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    PURPLE_COLOR,
    NexoraView,
    DismissButton,
    progress_bar,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)


class ServerInfoView(NexoraView):
    """Components V2 dashboard for server metrics and features."""

    def __init__(self, guild: discord.Guild, requester: discord.abc.User, timeout: float = 180):
        super().__init__(
            user_id=requester.id,
            color=PURPLE_COLOR,
            timeout=timeout,
        )
        self.guild = guild
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()
        g = self.guild

        # Counts
        bot_count = sum(1 for m in g.members if m.bot)
        human_count = max(0, g.member_count - bot_count)
        online_count = sum(1 for m in g.members if m.status != discord.Status.offline)
        human_pct = (human_count / max(1, g.member_count)) * 100

        text_chans = len(g.text_channels)
        voice_chans = len(g.voice_channels)
        stage_chans = len(g.stage_channels)
        cat_count = len(g.categories)

        # Boost tier display
        boost_tier_name = f"Level {g.premium_tier}" if g.premium_tier > 0 else "No Level"
        boost_summary = f"🚀 **{boost_tier_name}** · `{g.premium_subscription_count or 0}` Boosts"

        icon_url = str(g.icon.url) if g.icon else None

        # ── Header Section ────────────────────────────────────────────────────
        header_text = (
            f"# 🏰 {g.name}\n"
            f"> Created {ts_format(g.created_at, 'D')} ({ts_format(g.created_at, 'R')})\n"
            f"👑 **Owner:** {g.owner.mention if g.owner else 'Unknown'} · **ID:** `{g.id}`"
        )
        self.add_section(header_text, thumbnail_url=icon_url)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── Member Demographics Block ─────────────────────────────────────────
        bar = progress_bar(human_count, max_val=max(1, g.member_count), length=8)
        demographics = (
            "### 👥 Member Demographics\n"
            f"• **Total Population:** `{g.member_count:,}` members\n"
            f"• **Humans vs Bots:** `{bar}` **{human_pct:.0f}%** Humans\n"
            f"  └ 👤 Humans: `{human_count:,}` · 🤖 Bots: `{bot_count:,}`\n"
            f"• **Currently Online:** 🟢 `{online_count:,}` members active"
        )
        self.add_text(demographics)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── Guild Assets & Features Block ─────────────────────────────────────
        assets = (
            "### 📊 Channels & Assets\n"
            f"• **Channels:** `{text_chans}` Text · `{voice_chans}` Voice"
            + (f" · `{stage_chans}` Stage" if stage_chans else "")
            + f" · `{cat_count}` Categories\n"
            f"• **Roles & Emojis:** `{len(g.roles)}` roles · `{len(g.emojis)}` emojis\n"
            f"• **Nitro Status:** {boost_summary}"
        )
        self.add_text(assets)

        # ── Footer ────────────────────────────────────────────────────────────
        self.add_footer(
            f"Requested by {self.requester.display_name} · Verification: {str(g.verification_level).title()}"
        )

        # ── Interactive Buttons ───────────────────────────────────────────────
        buttons = []
        if g.icon:
            buttons.append(
                discord.ui.Button(
                    label="Server Icon",
                    emoji="🖼️",
                    style=discord.ButtonStyle.link,
                    url=g.icon.url,
                )
            )
        if g.banner:
            buttons.append(
                discord.ui.Button(
                    label="Server Banner",
                    emoji="🌆",
                    style=discord.ButtonStyle.link,
                    url=g.banner.url,
                )
            )

        dismiss = DismissButton(user_id=self.requester.id)
        buttons.append(dismiss)
        self.add_row(*buttons)


class ServerInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="serverinfo",
        description="🏰 View comprehensive server information and statistics",
        aliases=["si"],
    )
    async def serverinfo(self, ctx: commands.Context):
        if not ctx.guild:
            await ctx.send("❌ This command must be used within a server.", ephemeral=True)
            return

        view = ServerInfoView(ctx.guild, ctx.author)
        await send_view(ctx, view)


async def setup(bot):
    await bot.add_cog(ServerInfo(bot))
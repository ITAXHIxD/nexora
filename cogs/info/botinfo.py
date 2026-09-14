"""
cogs/info/botinfo.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Bot Information & Diagnostics
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import inspect
import logging
import os
import platform
import sys
from datetime import datetime, timezone

import discord
import psutil
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    CYAN_COLOR,
    BRAND_COLOR,
    NexoraView,
    DismissButton,
    latency_badge,
    progress_bar,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)


class BotInfoView(NexoraView):
    """Interactive Components V2 system diagnostics view."""

    def __init__(self, cog: "BotInfo", requester: discord.abc.User, timeout: float = 180):
        super().__init__(
            bot=cog.bot,
            user_id=requester.id,
            color=CYAN_COLOR,
            timeout=timeout,
        )
        self.cog = cog
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()
        now = datetime.now(timezone.utc)
        start_time = self.cog._coerce_datetime(
            getattr(self.bot, "bot_stats", {}).get("start_time", now)
        )
        uptime = now - start_time
        uptime_str = (
            f"{uptime.days}d "
            f"{uptime.seconds // 3600:02d}h "
            f"{(uptime.seconds // 60) % 60:02d}m "
            f"{uptime.seconds % 60:02d}s"
        )

        try:
            proc = psutil.Process(os.getpid())
            mem_mb = proc.memory_info().rss / 1024 / 1024
            cpu_percent = proc.cpu_percent(interval=None)
        except Exception:
            mem_mb = 0.0
            cpu_percent = 0.0

        latency_ms = self.bot.latency * 1000
        lat_indicator = latency_badge(latency_ms)

        total_users = sum(g.member_count or 0 for g in self.bot.guilds)
        total_channels = sum(len(g.channels) for g in self.bot.guilds)
        total_guilds = len(self.bot.guilds)

        avatar_url = str(self.bot.user.display_avatar.url) if self.bot.user else None

        # ── Header Section ────────────────────────────────────────────────────
        header_text = (
            "# 🤖 Nexora Core · Diagnostics\n"
            "> High-performance multi-purpose Discord system · Built with Components V2"
        )
        self.add_section(header_text, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── System Performance Block ──────────────────────────────────────────
        mem_bar = progress_bar(mem_mb, 1024.0, length=8)
        cpu_bar = progress_bar(cpu_percent, 100.0, length=8)

        sys_block = (
            "### ⚡ Performance & Health\n"
            f"• **Ping / Latency:** {lat_indicator}\n"
            f"• **Memory:** `{mem_bar}` **{mem_mb:.1f} MB**\n"
            f"• **CPU Load:** `{cpu_bar}` **{cpu_percent:.1f}%**\n"
            f"• **Uptime:** **{uptime_str}** · Online since {ts_format(start_time, 'D')}"
        )
        self.add_text(sys_block)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── Network & Environment Block ───────────────────────────────────────
        py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        os_name = f"{platform.system()} {platform.release()}"

        stats_block = (
            "### 🌐 Network & Infrastructure\n"
            f"• **Guilds:** `{total_guilds:,}` servers · **Users:** `{total_users:,}` members\n"
            f"• **Channels:** `{total_channels:,}` total channels\n"
            f"• **Engine:** Python `{py_ver}` · discord.py `{discord.__version__}`\n"
            f"• **Environment:** `{os_name}`"
        )
        self.add_text(stats_block)

        # ── Footer ────────────────────────────────────────────────────────────
        self.add_footer(
            f"Requested by {self.requester.display_name} · Last updated {ts_format(now, 'T')}"
        )

        # ── Action Buttons ────────────────────────────────────────────────────
        refresh_btn = discord.ui.Button(
            label="Refresh",
            emoji="🔄",
            style=discord.ButtonStyle.primary,
        )
        refresh_btn.callback = self._on_refresh

        invite_perms = discord.Permissions(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            use_application_commands=True,
        )
        invite_url = discord.utils.oauth_url(self.bot.user.id, permissions=invite_perms)
        invite_btn = discord.ui.Button(
            label="Invite",
            emoji="🔗",
            style=discord.ButtonStyle.link,
            url=invite_url,
        )

        dismiss_btn = DismissButton(user_id=self.requester.id)
        self.add_row(refresh_btn, invite_btn, dismiss_btn)

    async def _on_refresh(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "❌ You cannot interact with someone else's bot info card.",
                ephemeral=True,
            )
            return
        self._build()
        await interaction.response.edit_message(view=self)


class BotInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        if not hasattr(self.bot, "bot_stats"):
            self.bot.bot_stats = {"start_time": datetime.now(timezone.utc)}
        if not hasattr(self.bot, "is_premium_guild"):
            self.bot.is_premium_guild = self._default_premium_check

    def _default_premium_check(self, guild_id):
        return False

    def _coerce_datetime(self, value) -> datetime:
        if not isinstance(value, datetime):
            return datetime.now(timezone.utc)
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @commands.hybrid_command(
        name="botinfo",
        description="🤖 View live bot statistics and system diagnostics",
        aliases=["bi"],
    )
    async def botinfo(self, ctx: commands.Context):
        view = BotInfoView(self, ctx.author)
        await send_view(ctx, view)


async def setup(bot):
    await bot.add_cog(BotInfo(bot))

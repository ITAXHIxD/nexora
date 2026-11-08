"""
cogs/core/status.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 System Status & Telemetry Dashboard
Multi-tab real-time telemetry (Hardware, Cluster, Games & Live Presence)
with live CPU/RAM meters, latency diagnostics, and cluster statistics.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import os
import platform
import sys
import threading
from datetime import datetime, timezone

import discord
import psutil
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    PURPLE_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    cfg_color,
    latency_badge,
    progress_bar,
    send_view,
    ts_format,
)
from utils.game_stats import _load_local_stats

logger = logging.getLogger(__name__)


class PingLayoutView(NexoraView):
    """Components V2 LayoutView for ping/latency diagnostics."""

    def __init__(self, bot: commands.Bot, requester: discord.Member | discord.User):
        color = cfg_color(bot, "success_color", SUCCESS_COLOR)
        super().__init__(bot=bot, user_id=requester.id, color=color, timeout=120)
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()
        latency_ms = self.bot.latency * 1000.0
        badge = latency_badge(latency_ms)
        bar = progress_bar(latency_ms, 300.0, length=10)

        avatar_url = str(self.bot.user.display_avatar.url) if self.bot.user else None

        header = (
            "# 🏓 Pong! · Gateway Telemetry\n"
            "> Real-time WebSocket heartbeat and cluster response rate"
        )
        self.add_section(header, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        content = (
            "### ⚡ Gateway Performance\n"
            f"• **WebSocket Ping:** {badge}\n"
            f"• **Meter:** `{bar}` `{latency_ms:.1f} ms`\n"
            f"• **Active Shard:** `0/1` · Primary Cluster Gateway Node\n"
            f"• **Gateway State:** 🟢 Connected & Responsive"
        )
        self.add_text(content)
        self.add_footer(f"Requested by {self.requester.display_name} · Real-time Heartbeat")

        refresh_btn = discord.ui.Button(
            label="Re-ping",
            emoji="🔄",
            style=discord.ButtonStyle.secondary,
        )
        refresh_btn.callback = self._on_refresh
        dismiss_btn = DismissButton(user_id=self.requester.id)
        self.add_row(refresh_btn, dismiss_btn)

    async def _on_refresh(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            return await interaction.response.send_message("❌ This ping card belongs to someone else.", ephemeral=True)
        self._build()
        await interaction.response.edit_message(view=self)


class StatusDashboardView(NexoraView):
    """Components V2 Multi-Tab Cluster Dashboard & System Telemetry."""

    def __init__(self, bot: commands.Bot, requester: discord.Member | discord.User):
        super().__init__(bot=bot, user_id=requester.id, color=BRAND_COLOR, timeout=240)
        self.requester = requester
        self.current_tab = "system"  # "system", "cluster", "games", "presence"
        self._process = psutil.Process(os.getpid())
        self._build()

    def _build(self):
        self.clear_container()
        avatar_url = str(self.bot.user.display_avatar.url) if self.bot.user else None

        # Uptime Calculation
        start_time = getattr(self.bot, "bot_stats", {}).get("start_time", None)
        if start_time is None:
            start_time = datetime.fromtimestamp(self._process.create_time(), tz=timezone.utc)
        elif getattr(start_time, "tzinfo", None) is None:
            start_time = start_time.replace(tzinfo=timezone.utc)

        uptime = datetime.now(timezone.utc) - start_time
        uptime_days = uptime.days
        uptime_hours = uptime.seconds // 3600
        uptime_mins = (uptime.seconds // 60) % 60
        uptime_secs = uptime.seconds % 60
        uptime_str = f"{uptime_days}d {uptime_hours}h {uptime_mins}m {uptime_secs}s"

        # Tab Navigation Header
        tab_titles = {
            "system": "📊 System & Hardware Telemetry",
            "cluster": "🌐 Cluster & Network Infrastructure",
            "games": "🎮 Games & Community Activity",
            "presence": "🎭 Live Activity & Presence Matrix",
        }
        active_tab_title = tab_titles.get(self.current_tab, "System & Operations")

        header = (
            f"# 🤖 Nexora Cluster · {active_tab_title}\n"
            f"> Online for **{uptime_str}** · Version `3.5.0-pro` · Python `{platform.python_version()}`"
        )
        self.add_section(header, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        # Tab Content Generation
        if self.current_tab == "system":
            cpu_pct = psutil.cpu_percent(interval=None)
            cpu_bar = progress_bar(cpu_pct, 100.0, length=12)

            mem = psutil.virtual_memory()
            mem_bar = progress_bar(mem.percent, 100.0, length=12)

            proc_mem_mb = self._process.memory_info().rss / (1024 * 1024)
            thread_cnt = threading.active_count()

            system_text = (
                "### 🖥️ Hardware Utilization\n"
                f"• **CPU Load:** `{cpu_bar}` **{cpu_pct:.1f}%**\n"
                f"• **System RAM:** `{mem_bar}` **{mem.percent:.1f}%** ({mem.used // (1024**3):.1f}GB / {mem.total // (1024**3):.1f}GB)\n"
                f"• **Bot Process Memory:** `{proc_mem_mb:.1f} MB`\n"
                f"• **Active Worker Threads:** `{thread_cnt}`\n\n"
                "### ⚙️ Runtime Environment\n"
                f"• **Platform:** `{platform.system()} {platform.release()} ({platform.machine()})`\n"
                f"• **Python Runtime:** `v{sys.version.split()[0]}`\n"
                f"• **Discord API Engine:** `discord.py v{discord.__version__}` (Components V2 Active)"
            )
            self.add_text(system_text)

        elif self.current_tab == "cluster":
            latency_ms = self.bot.latency * 1000.0
            badge = latency_badge(latency_ms)

            total_guilds = len(self.bot.guilds)
            total_members = sum(g.member_count or 0 for g in self.bot.guilds)
            total_channels = len(list(self.bot.get_all_channels()))

            bot_stats = getattr(self.bot, "bot_stats", {})
            messages_proc = bot_stats.get("messages_processed", 0)
            cmds_used = bot_stats.get("commands_used", 0)
            errors = bot_stats.get("errors_encountered", 0)

            cluster_text = (
                "### 🌐 Network & Scale\n"
                f"• **Connected Servers:** `{total_guilds:,}` guilds\n"
                f"• **Cached Members:** `{total_members:,}` users\n"
                f"• **Active Channels:** `{total_channels:,}` channels\n"
                f"• **Cluster Shard:** `0/1` · WebSocket Heartbeat: {badge} (`{latency_ms:.1f}ms`)\n\n"
                "### 📈 Throughput Metrics\n"
                f"• **Messages Processed:** `{messages_proc:,}`\n"
                f"• **Commands Executed:** `{cmds_used:,}`\n"
                f"• **Recorded Incidents:** `{errors:,}`"
            )
            self.add_text(cluster_text)

        elif self.current_tab == "games":
            # Load game stats
            local_stats = _load_local_stats()
            total_games_played = 0
            for g_data in local_stats.values():
                for u_data in g_data.values():
                    total_games_played += u_data.get("wins", 0) + u_data.get("losses", 0) + u_data.get("draws", 0)

            # AFK count
            afk_count = 0
            try:
                if os.path.exists("data/afk_data.json"):
                    with open("data/afk_data.json", "r", encoding="utf-8") as f:
                        afk_count = len(json.load(f))
            except Exception:
                pass

            games_text = (
                "### 🎮 Multiplayer & Party Ecosystem\n"
                f"• **Supported Games:** `RPS`, `TicTacToe`, `Connect4`, `Number Guess`, `Truth or Dare`\n"
                f"• **Total Recorded Matches:** `{total_games_played:,}` duels logged across all servers\n"
                f"• **Dual Persistence Engine:** 🍃 MongoDB Atlas + 💾 Local JSON Backup Active\n"
                f"• **Currently AFK Members:** `{afk_count}` users safely away\n\n"
                "### 🎪 Fun & Entertainment\n"
                f"• **Reddit Stream:** Unlimited Subreddit browsing, Hot/Top/New sorting & caching\n"
                f"• **Truth or Dare:** 150+ curated party prompts across PG, Teen & Spicy tiers\n"
                f"• **Multiplayer Pings:** Real-time push turn alerts enabled on all turn-based games"
            )
            self.add_text(games_text)

        elif self.current_tab == "presence":
            current_act = "Rotating Dynamic Activities"
            if self.bot.guilds and self.bot.user:
                current_act = f"Serving {len(self.bot.guilds)} servers with {len(list(self.bot.get_all_channels()))} channels"

            presence_text = (
                "### 🎭 Dynamic Status Engine\n"
                f"• **Current Status:** 🟢 `Online`\n"
                f"• **Activity Cycle:** Every `5 minutes`\n"
                f"• **Activity Pool:** `50+` Creative, Gaming, Anime, and Music presences\n"
                f"• **Prefixes:** Default `n!` or customizable per-guild + Slash `/commands`\n"
                f"• **Components Version:** Discord UI Kit V2 Container & MediaGallery"
            )
            self.add_text(presence_text)

        self.add_separator(discord.SeparatorSpacing.small)
        self.add_footer(f"Requested by {self.requester.display_name} · Click tabs below to view detailed diagnostics")

        # Tab Switching Buttons
        btn_sys = discord.ui.Button(
            label="Hardware",
            emoji="🖥️",
            style=discord.ButtonStyle.primary if self.current_tab == "system" else discord.ButtonStyle.secondary,
        )
        btn_cluster = discord.ui.Button(
            label="Network",
            emoji="🌐",
            style=discord.ButtonStyle.primary if self.current_tab == "cluster" else discord.ButtonStyle.secondary,
        )
        btn_games = discord.ui.Button(
            label="Games & Fun",
            emoji="🎮",
            style=discord.ButtonStyle.primary if self.current_tab == "games" else discord.ButtonStyle.secondary,
        )
        btn_presence = discord.ui.Button(
            label="Activities",
            emoji="🎭",
            style=discord.ButtonStyle.primary if self.current_tab == "presence" else discord.ButtonStyle.secondary,
        )
        btn_refresh = discord.ui.Button(label="Refresh", emoji="🔄", style=discord.ButtonStyle.secondary)

        btn_sys.callback = lambda i: self._switch_tab(i, "system")
        btn_cluster.callback = lambda i: self._switch_tab(i, "cluster")
        btn_games.callback = lambda i: self._switch_tab(i, "games")
        btn_presence.callback = lambda i: self._switch_tab(i, "presence")
        btn_refresh.callback = self._on_refresh

        self.add_row(btn_sys, btn_cluster, btn_games, btn_presence)
        self.add_row(btn_refresh, DismissButton(user_id=self.requester.id))

    async def _switch_tab(self, interaction: discord.Interaction, tab: str):
        if interaction.user.id != self.requester.id:
            return await interaction.response.send_message("❌ This status card belongs to someone else.", ephemeral=True)
        self.current_tab = tab
        self._build()
        await interaction.response.edit_message(view=self)

    async def _on_refresh(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            return await interaction.response.send_message("❌ This status card belongs to someone else.", ephemeral=True)
        self._build()
        await interaction.response.edit_message(view=self)


class Status(commands.Cog):
    """Core Diagnostics & System Status Engine."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="status",
        aliases=["stats", "botstatus", "cluster"],
        description="📊 View live bot status, hardware metrics, and cluster telemetry",
    )
    async def status(self, ctx: commands.Context):
        view = StatusDashboardView(self.bot, ctx.author)
        await send_view(ctx, view)

    @commands.hybrid_command(
        name="ping",
        description="🏓 Check bot response time, gateway latency, and WebSocket heartbeat",
    )
    async def ping(self, ctx: commands.Context):
        view = PingLayoutView(self.bot, ctx.author)
        await send_view(ctx, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Status(bot))
    logger.debug("Loaded Status Cog")
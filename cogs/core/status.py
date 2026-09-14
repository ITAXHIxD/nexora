import discord
from discord.ext import commands
from datetime import datetime, timezone
import logging

from utils.ui import (
    NexoraView,
    DismissButton,
    send_view,
    latency_badge,
    progress_bar,
    cfg_color,
    BRAND_COLOR,
    SUCCESS_COLOR,
)

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
            "# 🏓 Pong! · Heartbeat Diagnostics\n"
            "> WebSocket heartbeat & gateway response metrics"
        )
        self.add_section(header, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        content = (
            "### ⚡ Gateway Connection\n"
            f"• **Latency:** {badge}\n"
            f"• **Meter:** `{bar}` `{latency_ms:.1f} ms`\n"
            f"• **Shard:** `0/1` · Active Gateway Node"
        )
        self.add_text(content)
        self.add_footer(f"Requested by {self.requester.display_name} · Real-time")

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
            await interaction.response.send_message(
                "❌ This ping card belongs to someone else.",
                ephemeral=True,
            )
            return
        self._build()
        await interaction.response.edit_message(view=self)


class StatusDashboardView(NexoraView):
    """Components V2 LayoutView for cluster status and operations."""

    def __init__(self, bot: commands.Bot, requester: discord.Member | discord.User):
        color = cfg_color(bot, "brand_color", BRAND_COLOR)
        super().__init__(bot=bot, user_id=requester.id, color=color, timeout=180)
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()

        # 1. Uptime Calculation and Formatting
        start_time = getattr(self.bot, "bot_stats", {}).get("start_time", datetime.now(timezone.utc))
        if hasattr(start_time, "tzinfo") and start_time.tzinfo is None:
            uptime = datetime.now() - start_time
        else:
            uptime = datetime.now(timezone.utc) - start_time

        uptime_str = (
            f"{uptime.days}d {uptime.seconds // 3600}h "
            f"{(uptime.seconds // 60) % 60}m {uptime.seconds % 60}s"
        )

        # 2. API Key Status
        try:
            failed_keys = len(getattr(self.bot.api_key_manager, "failed_keys", []))
            total_keys = getattr(self.bot.api_key_manager, "total_keys", 0)
            active = total_keys - failed_keys
            rotation_time = (datetime.now() - self.bot.api_key_manager.last_rotation).seconds
            api_key_value = (
                f"• **Total Keys:** `{total_keys}` · **Active:** `{active}` · **Failed:** `{failed_keys}`\n"
                f"• **Last Rotation:** `{rotation_time}s` ago"
            )
        except Exception:
            api_key_value = "• *API Key Manager is operating in single-key or offline mode.*"

        # 3. Performance Metrics
        bot_stats = getattr(self.bot, "bot_stats", {})
        messages_proc = bot_stats.get("messages_processed", 0)
        cmds_used = bot_stats.get("commands_used", 0)
        api_calls = bot_stats.get("api_calls_made", 0)
        errors = bot_stats.get("errors_encountered", 0)

        servers_cnt = len(self.bot.guilds)
        channels_cnt = len(list(self.bot.get_all_channels()))
        personalities_cnt = len(getattr(self.bot, "personalities", {}))

        avatar_url = str(self.bot.user.display_avatar.url) if self.bot.user else None

        header = (
            "# 🤖 Nexora Cluster Dashboard\n"
            "> Operational metrics, traffic statistics, and system telemetry"
        )
        self.add_section(header, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        metrics_text = (
            "### 📊 Throughput & Operations\n"
            f"• **Messages Handled:** `{messages_proc:,}`\n"
            f"• **Commands Executed:** `{cmds_used:,}`\n"
            f"• **API Invocations:** `{api_calls:,}`\n"
            f"• **Error Incidents:** `{errors:,}`"
        )
        self.add_text(metrics_text)
        self.add_separator(discord.SeparatorSpacing.small)

        infra_text = (
            "### 🌐 Infrastructure & Coverage\n"
            f"• **Guilds:** `{servers_cnt:,}` servers\n"
            f"• **Channels:** `{channels_cnt:,}` active channels\n"
            f"• **AI Personalities:** `{personalities_cnt:,}` active profiles\n"
            f"• **System Uptime:** **{uptime_str}**"
        )
        self.add_text(infra_text)
        self.add_separator(discord.SeparatorSpacing.small)

        api_text = (
            "### 🔑 Key Management\n"
            f"{api_key_value}"
        )
        self.add_text(api_text)
        self.add_footer(f"Requested by {self.requester.display_name} · Cluster telemetry")

        refresh_btn = discord.ui.Button(
            label="Refresh",
            emoji="🔄",
            style=discord.ButtonStyle.primary,
        )
        refresh_btn.callback = self._on_refresh
        dismiss_btn = DismissButton(user_id=self.requester.id)
        self.add_row(refresh_btn, dismiss_btn)

    async def _on_refresh(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message(
                "❌ This status card belongs to someone else.",
                ephemeral=True,
            )
            return
        self._build()
        await interaction.response.edit_message(view=self)


class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="status", description="View bot status and statistics.")
    async def status(self, ctx: commands.Context):
        view = StatusDashboardView(self.bot, ctx.author)
        await send_view(ctx, view)

    @commands.hybrid_command(name="ping", description="Check bot response time.")
    async def ping(self, ctx: commands.Context):
        view = PingLayoutView(self.bot, ctx.author)
        await send_view(ctx, view)


async def setup(bot):
    await bot.add_cog(Status(bot))
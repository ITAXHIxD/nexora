import inspect
import logging
import os
import sys
from datetime import datetime, timezone

import discord
import psutil
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)


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

    async def _is_premium(self, guild_id: int) -> bool:
        checker = getattr(self.bot, "is_premium_guild", self._default_premium_check)
        result = checker(guild_id)
        if inspect.isawaitable(result):
            result = await result
        return bool(result)

    async def _build_embed(self, requester: discord.abc.User) -> discord.Embed:
        now = datetime.now(timezone.utc)
        start_time = self._coerce_datetime(
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
            cpu_percent = proc.cpu_percent(interval=0.1)
        except Exception:
            mem_mb = 0
            cpu_percent = 0

        premium_servers = 0
        try:
            for guild in self.bot.guilds:
                if await self._is_premium(guild.id):
                    premium_servers += 1
        except Exception as exc:
            logger.warning("Failed to count premium servers: %s", exc)
            premium_servers = 0

        total_users = sum(g.member_count or 0 for g in self.bot.guilds)

        embed = discord.Embed(
            title="🤖 Nexora Bot",
            description="**Premium Discord Management Bot**",
            color=0x0099FF,
            timestamp=now,
        )
        embed.add_field(name="🖥️ Servers", value=f"{len(self.bot.guilds):,}", inline=True)
        embed.add_field(name="👥 Users", value=f"{total_users:,}", inline=True)
        embed.add_field(
            name="📢 Channels",
            value=f"{len(list(self.bot.get_all_channels())):,}",
            inline=True,
        )
        embed.add_field(name="⏱️ Uptime", value=uptime_str, inline=True)
        embed.add_field(name="🌐 Latency", value=f"{self.bot.latency * 1000:.1f}ms", inline=True)
        embed.add_field(name="💾 Memory", value=f"{mem_mb:.1f} MB", inline=True)
        embed.add_field(name="🖱️ CPU", value=f"{cpu_percent:.1f}%", inline=True)
        embed.add_field(name="🐍 Python", value=".".join(map(str, sys.version_info[:3])), inline=True)
        embed.add_field(name="💎 Premium Servers", value=f"{premium_servers:,}", inline=True)

        if self.bot.user:
            embed.set_thumbnail(url=str(self.bot.user.display_avatar))
        embed.set_footer(
            text=f"Requested by {requester.display_name}",
            icon_url=str(requester.display_avatar),
        )
        return embed

    @commands.hybrid_command(name="botinfo", description="🤖 View bot and system information", aliases=["bi"])
    async def botinfo(self, ctx: commands.Context):
        if ctx.interaction:
            await ctx.defer(ephemeral=False)

        embed = await self._build_embed(ctx.author)
        try:
            await ctx.send(embed=embed)
        except Exception as exc:
            logger.error("Botinfo error: %s", exc)
            await ctx.send("❌ Error sending info")

    @app_commands.command(name="bi", description="Alias for /botinfo")
    async def botinfo_alias(self, interaction: discord.Interaction):
        embed = await self._build_embed(interaction.user)
        await interaction.response.send_message(embed=embed)


async def setup(bot):
    await bot.add_cog(BotInfo(bot))

import discord
import os
import psutil
import sys
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class BotInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        if not hasattr(self.bot, 'bot_stats'):
            self.bot.bot_stats = {'start_time': datetime.now()}
        if not hasattr(self.bot, 'is_premium_guild'):
            self.bot.is_premium_guild = self._default_premium_check

    def _default_premium_check(self, guild_id):
        return False

    @commands.hybrid_command(name="botinfo", description="🤖 View bot and system information", aliases=['bi'])
    async def botinfo(self, ctx: commands.Context):
        """Hybrid command - works for both prefix AND slash"""

        # ✅ FIXED: Hybrid ALWAYS passes Context (not Interaction)
        await ctx.defer(ephemeral=False) if ctx.interaction else None

        # Calculate uptime
        uptime = datetime.now() - getattr(self.bot, 'bot_stats', {}).get('start_time', datetime.now())
        uptime_str = f"{uptime.days}d {uptime.seconds//3600:02d}h {(uptime.seconds//60)%60:02d}m {uptime.seconds%60:02d}s"

        # System stats
        try:
            proc = psutil.Process(os.getpid())
            mem_mb = proc.memory_info().rss / 1024 / 1024
            cpu_percent = proc.cpu_percent(interval=0.1)
        except:
            mem_mb = cpu_percent = 0

        # ✅ FIXED PREMIUM CHECK - Multiple fallback methods
        premium_servers = 0
        try:
            # Your Vanity cog method (PREFERRED)
            if hasattr(self.bot, 'get_cog') and self.bot.get_cog('Vanity'):
                vanity_cog = self.bot.get_cog('Vanity')
                premium_servers = sum(1 for guild in self.bot.guilds if vanity_cog.is_premium(guild.id))

            # Fallback: Direct JSON check
            elif os.path.exists("data/premium.json"):
                import json
                with open("data/premium.json", 'r') as f:
                    data = json.load(f)
                premium_servers = len([gid for gid in data.get("subscriptions", {}) 
                                     if data["subscriptions"][gid].get("expires_at") is None or 
                                     datetime.fromisoformat(data["subscriptions"][gid]["expires_at"]) > datetime.now()])

            # Fallback: Count 0
        except:
            premium_servers = 0

        total_users = sum(g.member_count or 0 for g in self.bot.guilds)

        # Embed
        embed = discord.Embed(
            title="🤖 Nexora Bot",
            description="**Premium Discord Management Bot**",
            color=0x0099ff,
            timestamp=datetime.utcnow()
        )
        embed.add_field(name="🖥️ Servers", value=f"{len(self.bot.guilds):,}", inline=True)
        embed.add_field(name="👥 Users", value=f"{total_users:,}", inline=True)
        embed.add_field(name="📢 Channels", value=f"{len(list(self.bot.get_all_channels())):,}", inline=True)
        embed.add_field(name="⏱️ Uptime", value=uptime_str, inline=True)
        embed.add_field(name="🌐 Latency", value=f"{self.bot.latency*1000:.1f}ms", inline=True)
        embed.add_field(name="💾 Memory", value=f"{mem_mb:.1f} MB", inline=True)
        embed.add_field(name="🖱️ CPU", value=f"{cpu_percent:.1f}%", inline=True)
        embed.add_field(name="🐍 Python", value=".".join(map(str, sys.version_info[:3])), inline=True)
        embed.add_field(name="💎 Premium Servers", value=f"{premium_servers:,}", inline=True)

        embed.set_thumbnail(url=str(self.bot.user.display_avatar))
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", 
                        icon_url=str(ctx.author.display_avatar))

        # Send response ✅ FIXED
        try:
            await ctx.send(embed=embed)  # Works for BOTH prefix and slash
        except Exception as e:
            logger.error(f"Botinfo error: {e}")
            await ctx.send("❌ Error sending info")

async def setup(bot):
    await bot.add_cog(BotInfo(bot))

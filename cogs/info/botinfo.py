import discord
import os
import psutil
import sys
from discord.ext import commands
from discord import app_commands
from datetime import datetime

class BotInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="botinfo", description="View bot and system information.",aliases=['bi'])
    async def botinfo(self, ctx: commands.Context):
        # The logic remains the same, but we use ctx.author for the request info
        uptime = datetime.now() - self.bot.bot_stats['start_time']
        uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m {uptime.seconds%60}s"
        try:
            proc = psutil.Process(os.getpid())
            mem_mb = proc.memory_info().rss / 1024 / 1024
            cpu = proc.cpu_percent()
        except Exception:
            mem_mb = 0
            cpu = 0

        # You can compute this dynamically using your bot's `is_premium_guild` method
        premium_servers = sum(1 for guild in self.bot.guilds if self.bot.is_premium_guild(guild.id))

        embed = discord.Embed(
            title="🤖 Nexora Bot",
            description="Bot information",
            # Assuming you use the embed_color from your config.json
            color=self.bot.bot_config['ui_settings']['embed_color']
        )
        embed.add_field(name="Servers", value=str(len(self.bot.guilds)), inline=True)
        embed.add_field(name="Users", value=str(sum(g.member_count for g in self.bot.guilds if g.member_count)), inline=True)
        embed.add_field(name="Channels", value=str(len(list(self.bot.get_all_channels()))), inline=True)
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Latency", value=f"{self.bot.latency*1000:.2f}ms", inline=True)
        embed.add_field(name="Memory", value=f"{mem_mb:.1f} MB", inline=True)
        embed.add_field(name="CPU", value=f"{cpu:.1f}%", inline=True)
        embed.add_field(name="Python", value=".".join(map(str, sys.version_info[:3])), inline=True)
        embed.add_field(name="Premium Servers", value=str(premium_servers), inline=True)

        # Use ctx.send() for hybrid commands
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(BotInfo(bot))
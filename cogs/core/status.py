import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
import math

logger = logging.getLogger(__name__)

class Status(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
    def get_config_color(self, key: str, fallback: int = 0x00ff00) -> int:
        """Safely retrieves a color from the bot config."""
        try:
            return int(self.bot.bot_config['ui_settings'][key], 16)
        except (AttributeError, KeyError, ValueError):
            return fallback

    @commands.hybrid_command(name="status", description="View bot status and statistics.")
    async def status(self, ctx: commands.Context):
        # 1. Uptime Calculation and Formatting
        uptime = datetime.now() - self.bot.bot_stats['start_time']
        uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m {uptime.seconds%60}s"

        # 2. API Key Status (Protected with try/except)
        try:
            failed_keys = len(getattr(self.bot.api_key_manager, 'failed_keys', []))
            total_keys = getattr(self.bot.api_key_manager, 'total_keys', 0)
            active = total_keys - failed_keys
            rotation_time = (datetime.now() - self.bot.api_key_manager.last_rotation).seconds
            api_key_value = (
                f"Total: {total_keys}\n"
                f"Active: {active}\n"
                f"Failed: {failed_keys}\n"
                f"Last Rotation: {rotation_time}s ago"
            )
        except AttributeError:
            api_key_value = "API Manager not fully initialized or attributes missing."
            failed_keys = 'N/A' # Use this for the footer if needed

        # 3. Embed Creation
        embed_color = self.get_config_color('success_color', 0x00ff00)
        
        embed = discord.Embed(
            title="🤖 Nexora Bot Status Dashboard", 
            color=embed_color, 
            timestamp=datetime.now()
        )
        
        embed.add_field(
            name="📊 Performance", 
            value=(
                f"Messages: {self.bot.bot_stats.get('messages_processed', 0):,}\n"
                f"Commands: {self.bot.bot_stats.get('commands_used', 0):,}\n"
                f"API Calls: {self.bot.bot_stats.get('api_calls_made', 0):,}\n"
                f"Errors: {self.bot.bot_stats.get('errors_encountered', 0):,}"
            ), 
            inline=True
        )
        
        embed.add_field(
            name="🌐 System", 
            value=(
                f"Uptime: {uptime_str}\n"
                f"Servers: {len(self.bot.guilds):,}\n"
                f"Channels: {len(list(self.bot.get_all_channels())):,}\n"
                f"Personalities: {len(getattr(self.bot, 'personalities', {})):,}"
            ), 
            inline=True
        )
        
        embed.add_field(name="🔑 API Keys", value=api_key_value, inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="ping", description="Check bot response time.")
    async def ping(self, ctx: commands.Context):
        latency = round(self.bot.latency * 1000)
        embed_color = self.get_config_color('success_color', 0x00ff00)
        
        embed = discord.Embed(
            title="🏓 Pong!", 
            description=f"Bot latency: **{latency}ms**", 
            color=embed_color
        )
        await ctx.send(embed=embed)
        
async def setup(bot):
    await bot.add_cog(Status(bot))
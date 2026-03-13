import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
logger = logging.getLogger(__name__)
# --- Helper Function for Color Consistency ---
def get_config_color(bot, key: str, fallback: int = 0x5865F2) -> int:
    """Safely retrieves a color from the bot config."""
    try:
        # Assuming bot.bot_config is attached to the bot instance
        return int(bot.bot_config['ui_settings'][key], 16)
    except (AttributeError, KeyError, ValueError):
        return fallback

class ChannelInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="channelinfo", description="Displays detailed information about a channel.")
    @app_commands.describe(channel="The channel to inspect (defaults to current channel).")
    async def channelinfo(self, ctx: commands.Context, channel: discord.abc.GuildChannel = None):
        """Displays detailed information about a channel."""
        
        target = channel or ctx.channel
        
        if not ctx.guild:
            await ctx.send("❌ This command must be used in a server.", ephemeral=True)
            return
        
        if not isinstance(target, discord.abc.GuildChannel):
            await ctx.send("❌ Cannot get info for this type of channel (e.g., DMs).", ephemeral=True)
            return

        embed_color = get_config_color(self.bot, 'embed_color')
        
        embed = discord.Embed(
            title=f"📝 Channel Information: #{target.name}",
            color=embed_color,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)

        # Standard Info Fields
        embed.add_field(name="Name", value=target.name, inline=True)
        embed.add_field(name="ID", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Type", value=str(target.type).split('.')[-1].title(), inline=True)
        embed.add_field(name="Category", value=target.category.name if target.category else "None", inline=True)
        
        # Dynamic Timestamp
        embed.add_field(
            name="Created", 
            value=f"<t:{int(target.created_at.timestamp())}:R>", 
            inline=True
        )

        # Type-specific details
        if isinstance(target, discord.TextChannel):
            embed.add_field(name="Topic", value=target.topic or "None", inline=False)
            embed.add_field(name="Slowmode", value=f"{target.slowmode_delay}s", inline=True)
            embed.add_field(name="NSFW", value="Yes" if target.is_nsfw() else "No", inline=True)
        elif isinstance(target, discord.VoiceChannel):
            embed.add_field(name="Bitrate", value=f"{target.bitrate // 1000}kbps", inline=True)
            embed.add_field(name="User Limit", value=f"{target.user_limit}" if target.user_limit > 0 else "Unlimited", inline=True)
            embed.add_field(name="Members", value=f"{len(target.members)}", inline=True)
        
        # Link to channel
        embed.add_field(name="Link", value=f"[Jump to Channel]({target.jump_url})", inline=False)


        embed.set_footer(text=f"Requested by {ctx.author.display_name}")

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ChannelInfo(bot))
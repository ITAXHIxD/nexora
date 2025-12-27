import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

class ServerInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="serverinfo", description="View server information.",aliases=['si'])
    async def serverinfo(self, ctx: commands.Context):
        # We can use ctx.guild directly as hybrid commands won't run in DMs by default
        guild = ctx.guild
        
        if not guild:
            await ctx.reply("❌ This command must be used in a server!", ephemeral=True)
            return

        text_channels = len(guild.text_channels)
        voice_channels = len(guild.voice_channels)
        categories = len(guild.categories)
        bot_count = sum(1 for m in guild.members if m.bot)
        human_count = guild.member_count - bot_count
        # The presence intent in your bot.py allows this to work accurately
        online_members = sum(1 for m in guild.members if m.status != discord.Status.offline)

        # Get the embed color from your bot_config
        try:
            embed_color = int(self.bot.bot_config['ui_settings']['embed_color'], 16)
        except (KeyError, ValueError):
            embed_color = 0x5DADE2 # Fallback color
            
        embed = discord.Embed(
            title=guild.name,
            description="Server information",
            color=embed_color,
            timestamp=datetime.now()
        )
        if guild.icon:
            embed.set_thumbnail(url=guild.icon.url)
            
        embed.add_field(name="Owner", value=guild.owner.mention if guild.owner else "Unknown", inline=True)
        # Use a dynamic timestamp for a better user experience
        embed.add_field(name="Created", value=f"<t:{int(guild.created_at.timestamp())}:R>", inline=True)
        embed.add_field(name="Members", value=f"Total: {guild.member_count}\nHumans: {human_count}\nBots: {bot_count}\nOnline: {online_members}", inline=True)
        embed.add_field(name="Channels", value=f"Text: {text_channels}\nVoice: {voice_channels}\nCategories: {categories}", inline=True)
        embed.add_field(name="Roles", value=f"{len(guild.roles)}", inline=True)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(ServerInfo(bot))
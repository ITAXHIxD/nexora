import discord
from discord.ext import commands
from discord import app_commands
import logging
logger = logging.getLogger(__name__)
class Invite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="invite", description="Get the bot's invite link.",aliases=['inv'])
    async def invite(self, ctx: commands.Context):
        # A more reasonable set of permissions for a general-purpose bot
        # You can adjust this list to your needs.
        perms = discord.Permissions(
            view_channel=True,
            send_messages=True,
            embed_links=True,
            attach_files=True,
            read_message_history=True,
            use_external_emojis=True,
            add_reactions=True,
            use_application_commands=True,
            connect=True,
            speak=True
        )
        
        url = discord.utils.oauth_url(self.bot.user.id, permissions=perms)
        
        # Get the success_color from your bot_config
        try:
            embed_color = int(self.bot.bot_config['ui_settings']['success_color'], 16)
        except (KeyError, ValueError):
            embed_color = 0x57F287 # Fallback color
            
        embed = discord.Embed(
            title="🔗 Invite Nexora Bot",
            description="Add me to your server!",
            color=embed_color
        )
        
        embed.add_field(name="Invite Link", value=f"[Click here to invite me]({url})", inline=False)
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        # Use ctx.send() for hybrid commands
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Invite(bot))
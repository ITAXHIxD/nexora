import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

# --- Helper Function for Color Consistency ---
def get_config_color(bot, key: str, fallback: int = 0x5865F2) -> int:
    """Safely retrieves a color from the bot config."""
    try:
        # Assuming bot.bot_config is attached to the bot instance
        return int(bot.bot_config['ui_settings'][key], 16)
    except (AttributeError, KeyError, ValueError):
        return fallback

class RoleInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="roleinfo", description="Displays detailed information about a specified role.",aliases=['ri'])
    @app_commands.describe(role="The role you want to inspect.")
    async def roleinfo(self, ctx: commands.Context, role: discord.Role):
        """Displays detailed information about a specified role."""
        
        if not ctx.guild:
            await ctx.send("❌ This command must be used in a server.", ephemeral=True)
            return

        try:
            # Use role's color or fallback to the bot's embed color
            embed_color = role.color.value if role.color.value else get_config_color(self.bot, 'embed_color')
        except:
            embed_color = get_config_color(self.bot, 'embed_color')
            
        # Get member count
        member_count = len(role.members)
        
        # Permission summary
        permission_list = [
            perm.replace('_', ' ').title() for perm, value in role.permissions 
            if value and perm not in ["read_message_history", "view_channel"]
        ]
        permission_summary = ", ".join(permission_list[:5])
        if len(permission_list) > 5:
            permission_summary += f", and {len(permission_list) - 5} more..."
        
        # Hoist/Mentionable text
        hoist = "Yes" if role.hoist else "No"
        mentionable = "Yes" if role.mentionable else "No"

        embed = discord.Embed(
            title=f"🎭 Role Information: {role.name}",
            color=embed_color,
            timestamp=datetime.now()
        )
        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        
        embed.add_field(name="Name", value=role.name, inline=True)
        embed.add_field(name="ID", value=f"`{role.id}`", inline=True)
        embed.add_field(name="Members", value=f"{member_count:,}", inline=True)
        
        embed.add_field(name="Color", value=f"#{role.color.value:06x}", inline=True)
        embed.add_field(name="Hoisted", value=hoist, inline=True)
        embed.add_field(name="Mentionable", value=mentionable, inline=True)
        
        # Dynamic Timestamp for creation
        embed.add_field(
            name="Created", 
            value=f"<t:{int(role.created_at.timestamp())}:R>", 
            inline=True
        )
        
        embed.add_field(
            name=f"Key Permissions ({len(permission_list)})", 
            value=permission_summary or "None", 
            inline=False
        )
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(RoleInfo(bot))
import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime

class UserInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="userinfo", description="View user information",aliases=['ui'])
    @app_commands.describe(user="User to inspect (optional)")
    async def userinfo(self, ctx: commands.Context, user: discord.Member = None):
        target = user or ctx.author

        roles = [r.mention for r in target.roles if r.name != "@everyone"]
        roles_text = ", ".join(roles[:10]) if roles else "None"
        if len(roles) > 10:
            roles_text += f" (+{len(roles)-10} more)"

        embed = discord.Embed(
            title=target.display_name,
            description=f"User info for {target.mention}",
            color=target.color if target.color.value else 0x5DADE2,
            timestamp=datetime.now()
        )
        if target.avatar:
            embed.set_thumbnail(url=target.avatar.url)
        embed.add_field(name="Username", value=target.name, inline=True)
        embed.add_field(name="ID", value=str(target.id), inline=True)
        embed.add_field(name="Bot", value="Yes" if target.bot else "No", inline=True)
        embed.add_field(name="Account Created", value=target.created_at.strftime('%Y-%m-%d'), inline=True)
        embed.add_field(name="Joined Server", value=target.joined_at.strftime('%Y-%m-%d') if target.joined_at else "Unknown", inline=True)
        embed.add_field(name=f"Roles ({len(target.roles)-1})", value=roles_text, inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(UserInfo(bot))


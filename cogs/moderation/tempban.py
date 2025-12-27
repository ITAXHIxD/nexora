import discord
from discord.ext import commands
import logging
log = logging.getLogger(__name__)
class tempban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="tempban", description="Temporarily ban a member from the server")
    async def tempban(self, ctx, member: discord.Member = None, duration: int = None):
        await ctx.send("Coming soon!")

async def setup(bot):
    await bot.add_cog(tempban(bot))
import discord
from discord.ext import commands
import logging
logger = logging.getLogger(__name__)
class Ban(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="ban", description="Ban a member from the server")
    async def ban(self, ctx, member: discord.Member = None):
        await ctx.send("Coming soon!")

async def setup(bot):
    await bot.add_cog(Ban(bot))
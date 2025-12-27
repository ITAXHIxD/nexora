import discord
from discord.ext import commands
import logging
log = logging.getLogger(__name__)
class Kick(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="kick", description="Kick a member from the server")
    async def kick(self, ctx, member: discord.Member = None):
        await ctx.send("Coming soon!")

async def setup(bot):
    await bot.add_cog(Kick(bot))
import discord
from discord.ext import commands
import logging
logger = logging.getLogger(__name__)
class mute(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="mute", description="Mute a member in the server")
    async def mute(self, ctx, member: discord.Member = None):
        await ctx.send("Coming soon!")

async def setup(bot):
    await bot.add_cog(mute(bot))
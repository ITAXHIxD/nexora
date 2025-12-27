import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed
import logging
logger = logging.getLogger(__name__)

class Cuddle(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="cuddle", description="Cuddle someone warmly!")
    @app_commands.describe(user="Who do you want to cuddle?")
    async def cuddle(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author

        await send_owo_action_embed(
            ctx,
            target,
            "cuddle",
            text_template="**{author}** snuggles close to **{target}**… comfy and warm~ 🐻💞",
            self_template="**{author}** curls up hugging themselves… aww sweetie…",
        )


async def setup(bot):
    await bot.add_cog(Cuddle(bot))

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

    @commands.command(name="cuddle", description="Cuddle someone warmly!")
    async def cuddle(self, ctx, *users: discord.Member):
        targets = list(users) if users else [ctx.author]

        await send_owo_action_embed(
            ctx,
            targets,
            "cuddle",
            text_template="**{author}** snuggles close to **{target}**… comfy and warm~ 🐻💞",
            self_template="**{author}** curls up hugging themselves… aww sweetie…",
        )


async def setup(bot):
    await bot.add_cog(Cuddle(bot))

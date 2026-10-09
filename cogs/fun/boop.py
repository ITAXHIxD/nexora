import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed

import logging
logger = logging.getLogger(__name__)

class Boop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="boop", description="Boop someone's nose!")
    async def boop(self, ctx, *users: discord.Member):
        targets = list(users) if users else [ctx.author]

        await send_owo_action_embed(
            ctx,
            targets,
            "boop",
            text_template="**{author}** gently boops **{target}** on the nose~ 👉🐽",
            self_template="**{author}** boops their *own* nose… cute but weird owo.",
        )


async def setup(bot):
    await bot.add_cog(Boop(bot))

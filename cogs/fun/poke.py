import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed
import logging
logger = logging.getLogger(__name__)

class Poke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="poke", description="Poke someone!")
    async def poke(self, ctx, *users: discord.Member):
        targets = list(users) if users else [ctx.author]

        await send_owo_action_embed(
            ctx,
            targets,
            "poke",
            text_template="**{author}** pokes **{target}** gently~ 👉😳",
            self_template="**{author}** pokes themselves and giggles… okay cutie.",
        )


async def setup(bot):
    await bot.add_cog(Poke(bot))

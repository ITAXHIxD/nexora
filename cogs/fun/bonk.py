import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed
import logging
logger = logging.getLogger(__name__)

class Bonk(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="bonk", description="Bonk someone!")
    async def bonk(self, ctx, *users: discord.Member):
        targets = list(users) if users else [ctx.author]

        await send_owo_action_embed(
            ctx,
            targets,
            "bonk",
            text_template="**{author}** bonks **{target}** on the head! 🔨🐶",
            self_template="**{author}** bonks themselves… self-punishment? owo",
        )


async def setup(bot):
    await bot.add_cog(Bonk(bot))

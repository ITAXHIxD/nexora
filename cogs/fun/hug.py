import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed
import logging
logger = logging.getLogger(__name__)

class Hug(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="hug", description="Give someone a warm hug OwO!")
    async def hug(self, ctx, *users: discord.Member):
        targets = list(users) if users else [ctx.author]

        await send_owo_action_embed(
            ctx,
            targets,
            "hug",
            text_template="**{author}** wraps **{target}** in a warm comfy hug… 🤗💞",
            self_template="**{author}** hugs themselves tightly… you okay, sweet bean? 🥺",
        )


async def setup(bot):
    await bot.add_cog(Hug(bot))

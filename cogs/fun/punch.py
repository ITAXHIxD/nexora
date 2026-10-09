import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed
import logging
logger = logging.getLogger(__name__)

class Punch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="punch", description="Punch someone playfully.")
    async def punch(self, ctx, *users: discord.Member):
        if not users:
            await ctx.send("You swing at the air like a clown. 👋🤣")
            return

        await send_owo_action_embed(
            ctx,
            list(users),
            "punch",
            text_template="**{author}** punches **{target}**! (playfully... maybe) 👊😳",
            self_template="**{author}** punches themselves??? why tho 💀",
        )


async def setup(bot):
    await bot.add_cog(Punch(bot))

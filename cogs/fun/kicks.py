# cogs/fun/kick.py

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from .actions import send_owo_action_embed
import logging
logger = logging.getLogger(__name__)

class Kicks(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="kicks",
        description="Kick someone (playfully, probably)."
    )
    async def kick(self, ctx: commands.Context, *users: discord.Member):
        if not users:
            await ctx.send("Tag someone to kick, you little gremlin.")
            return

        await send_owo_action_embed(
            ctx,
            list(users),
            "kicks",  # data/owo_gifs/kick.json
            text_template="**{author}** yeets **{target}** with a smol and hard kick",
            self_template="**{author}** tries to kick themselves and almost falls over. (╯°□°）╯︵ ┻━┻",
            color=discord.Color.orange(),
            action_emoji="🦵",
            action_label="Kicks",
        )


async def setup(bot):
    await bot.add_cog(Kicks(bot))

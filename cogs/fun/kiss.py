# cogs/fun/kick.py

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from .actions import send_owo_action_embed
import logging
logger = logging.getLogger(__name__)

class Kiss(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(
        name="kiss",
        description="Kiss someone (playfully, probably)."
    )
    async def kiss(self, ctx: commands.Context, *users: discord.Member):
        if not users:
            await ctx.send("Tag someone to kiss, you little gremlin.")
            return

        await send_owo_action_embed(
            ctx,
            list(users),
            "kiss",  # data/owo_gifs/kiss.json
            text_template="**awwwww... {author}** kisses **{target}** 💗",
            self_template="**{author}** attempts self-kiss but fails spectacularly. ;-;",
            color=discord.Color.red(),
            action_emoji="💗",
            action_label="Kiss",
        )


async def setup(bot):
    await bot.add_cog(Kiss(bot))

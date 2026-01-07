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

    @commands.hybrid_command(
        name="kiss",
        description="Kiss someone (playfully, probably)."
    )
    @app_commands.describe(user="Who do you want to kiss?")
    async def kiss(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        if user is None:
            await ctx.send("Tag someone to kiss, you little gremlin.")
            return

        await send_owo_action_embed(
            ctx,
            user,
            "kiss",  # data/owo_gifs/kiss.json
            text_template="**awwwww... {author}** kisses **{target}** 💗",
            self_template="**{author}** attempts self-kiss but fails spectacularly. ;-;",
            color=discord.Color.red(),
            action_emoji="💗",
            action_label="Kiss",
        )


async def setup(bot):
    await bot.add_cog(Kiss(bot))

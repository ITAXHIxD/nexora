# cogs/fun/kick.py

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from .actions import send_owo_action_embed
import logging
logger = logging.getLogger(__name__)

class Kill(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="kill",
        description="Kill someone (playfully, probably)."
    )
    @app_commands.describe(user="Who do you want to kill?")
    async def kill(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        if user is None:
            await ctx.send("Tag someone to kill, you little gremlin.")
            return

        await send_owo_action_embed(
            ctx,
            user,
            "kill",  # data/owo_gifs/kill.json
            text_template="**{author}** eliminates **{target}** 💀",
            self_template="**{author}** attempts self-elimination but fails spectacularly. (╯°□°）╯︵ ┻━┻",
            color=discord.Color.red(),
            action_emoji="💀",
            action_label="Kill",
        )


async def setup(bot):
    await bot.add_cog(Kill(bot))

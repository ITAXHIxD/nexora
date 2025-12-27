# cogs/fun/pat.py

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

from .actions import send_owo_action_embed
import logging
logger = logging.getLogger(__name__)

class Pat(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="pat",
        description="Pat someone in a cute way."
    )
    @app_commands.describe(user="Who do you want to pat?")
    async def pat(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        target = user or ctx.author

        await send_owo_action_embed(
            ctx,
            target,
            "pat",  # will load data/owo_gifs/pat.json
            text_template="**{author}** gently pats **{target}** on the head… uwu ✨",
            self_template="**{author}** pats themselves softly… are you okay, friend? 🤍",
            color=discord.Color.from_rgb(255, 192, 203),  # soft pink
            action_emoji="🤍",
            action_label="Headpat",
        )


async def setup(bot):
    await bot.add_cog(Pat(bot))

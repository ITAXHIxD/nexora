import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed
import logging
logger = logging.getLogger(__name__)

class Bite(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="bite", description="Bite someone (softly, I hope).")
    async def bite(self, ctx, *users: discord.Member):
        targets = list(users) if users else [ctx.author]
        
        await send_owo_action_embed(
            ctx,
            targets,
            "bite",
            text_template="**{author}** bites **{target}** softly… *chomp chomp* 🦷😳",
            self_template="**{author}** bites their own hand… okay buddy…",
        )


async def setup(bot):
    await bot.add_cog(Bite(bot))

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed


class Boop(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="boop", description="Boop someone's nose!")
    @app_commands.describe(user="Who do you want to boop?")
    async def boop(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author

        await send_owo_action_embed(
            ctx,
            target,
            "boop",
            text_template="**{author}** gently boops **{target}** on the nose~ 👉🐽",
            self_template="**{author}** boops their *own* nose… cute but weird owo.",
        )


async def setup(bot):
    await bot.add_cog(Boop(bot))

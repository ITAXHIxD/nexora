import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed


class Poke(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="poke", description="Poke someone!")
    @app_commands.describe(user="Who do you want to poke?")
    async def poke(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author

        await send_owo_action_embed(
            ctx,
            target,
            "poke",
            text_template="**{author}** pokes **{target}** gently~ 👉😳",
            self_template="**{author}** pokes themselves and giggles… okay cutie.",
        )


async def setup(bot):
    await bot.add_cog(Poke(bot))

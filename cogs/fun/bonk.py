import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed


class Bonk(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="bonk", description="Bonk someone!")
    @app_commands.describe(user="Who do you want to bonk?")
    async def bonk(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author

        await send_owo_action_embed(
            ctx,
            target,
            "bonk",
            text_template="**{author}** bonks **{target}** on the head! 🔨🐶",
            self_template="**{author}** bonks themselves… self-punishment? owo",
        )


async def setup(bot):
    await bot.add_cog(Bonk(bot))

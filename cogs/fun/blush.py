import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed


class Blush(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="blush", description="Blush at someone.")
    @app_commands.describe(user="Who makes you blush?")
    async def blush(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author

        await send_owo_action_embed(
            ctx,
            target,
            "blush",
            text_template="**{author}** blushes at **{target}**… omg cute— 🥺💗",
            self_template="**{author}** blushes at themselves in a mirror… precious baby.",
        )


async def setup(bot):
    await bot.add_cog(Blush(bot))

import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed


class Hug(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="hug", description="Give someone a warm hug OwO!")
    @app_commands.describe(user="Who do you want to hug?")
    async def hug(self, ctx, user: Optional[discord.Member] = None):
        target = user or ctx.author

        await send_owo_action_embed(
            ctx,
            target,
            "hug",
            text_template="**{author}** wraps **{target}** in a warm comfy hug… 🤗💞",
            self_template="**{author}** hugs themselves tightly… you okay, sweet bean? 🥺",
        )


async def setup(bot):
    await bot.add_cog(Hug(bot))

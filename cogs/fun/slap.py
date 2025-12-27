import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed


class Slap(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="slap", description="Slap someone playfully.")
    @app_commands.describe(user="Who do you want to slap?")
    async def slap(self, ctx, user: Optional[discord.Member] = None):
        if user is None:
            await ctx.send("You swing at the air like a clown. 👋🤣")
            return

        await send_owo_action_embed(
            ctx,
            user,
            "slap",
            text_template="**{author}** slaps **{target}**! (playfully... maybe) 👋😳",
            self_template="**{author}** slaps themselves??? why tho 💀",
        )


async def setup(bot):
    await bot.add_cog(Slap(bot))

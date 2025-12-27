import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional
from .actions import send_owo_action_embed


class Punch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="punch", description="Punch someone playfully.")
    @app_commands.describe(user="Who do you want to punch?")
    async def punch(self, ctx, user: Optional[discord.Member] = None):
        if user is None:
            await ctx.send("You swing at the air like a clown. 👋🤣")
            return

        await send_owo_action_embed(
            ctx,
            user,
            "punch",
            text_template="**{author}** punches **{target}**! (playfully... maybe) �😳",
            self_template="**{author}** punches themselves??? why tho 💀",
        )


async def setup(bot):
    await bot.add_cog(Punch(bot))

import discord
import random
import sqlite3
import json
import logging
from discord.ext import commands
from discord import app_commands
from datetime import datetime
logger = logging.getLogger(__name__)

class Say(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        if not hasattr(self.bot, "active_saying"):
            self.bot.active_saying = {}

    @commands.hybrid_command(name="say", description="Make the bot say something")
    @app_commands.describe(message="The message you want the bot to say")
    async def say(self, ctx: commands.Context, *, message: str):
        """Make the bot say something"""
        
        if len(message) > 2000:
            await ctx.send("❌ Message is too long! Please keep it under 2000 characters.", ephemeral=True)
            return
        
        channel_key = str(ctx.channel.id)
        user_id = str(ctx.author.id)
        key = f"{channel_key}_{user_id}"
        
        self.bot.active_saying[key] = {
            "message": message,
            "timestamp": datetime.now().isoformat()
        }
        
        await ctx.send(message)

async def setup(bot):
    await bot.add_cog(Say(bot))

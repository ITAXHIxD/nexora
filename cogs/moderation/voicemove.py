import discord
from discord.ext import commands
from discord import app_commands
import logging
logger = logging.getLogger(__name__)
class VoiceMove(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="vmove",
        description="Move everyone in your current voice channel to another voice channel."
    )
    @commands.has_guild_permissions(move_members=True)  # needs Move Members perm [web:139]
    @app_commands.describe(
        channel="Voice channel to move everyone into"
    )
    async def vmove(self, ctx: commands.Context, channel: discord.VoiceChannel):
        # must be in voice
        if not ctx.author.voice or not ctx.author.voice.channel:
            await ctx.send("❌ You must be connected to a voice channel to use this.", ephemeral=True)
            return

        source = ctx.author.voice.channel

        if source.id == channel.id:
            await ctx.send("❌ You are already in that voice channel.", ephemeral=True)
            return

        moved = 0
        for member in list(source.members):
            try:
                await member.move_to(channel)
                moved += 1
            except discord.Forbidden:
                continue

        if moved == 0:
            await ctx.send("⚠️ No members could be moved (missing permissions or empty channel).", ephemeral=True)
            return

        await ctx.send(
            f"✅ Moved **{moved}** member(s) from **{source.name}** to **{channel.name}**.",
            ephemeral=True
        )

async def setup(bot):
    await bot.add_cog(VoiceMove(bot))

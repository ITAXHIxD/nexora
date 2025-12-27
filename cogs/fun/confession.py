import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import logging

log = logging.getLogger(__name__)


class Confession(commands.Cog):
    """Anonymous confession system with per‑server channel + counters."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.data_file = "data/confessions.json"
        os.makedirs("data", exist_ok=True)

        # {
        #   "guild_id": {
        #       "channel_id": int | null,
        #       "counter": int
        #   }
        # }
        self.guild_data = {}
        self._load()

    # ---------- persistence ----------

    def _load(self):
        if not os.path.exists(self.data_file):
            self.guild_data = {}
            return
        try:
            with open(self.data_file, "r", encoding="utf-8") as f:
                self.guild_data = json.load(f)
        except Exception as e:
            log.error("Failed to load confessions file: %s", e)
            self.guild_data = {}

    def _save(self):
        try:
            with open(self.data_file, "w", encoding="utf-8") as f:
                json.dump(self.guild_data, f, indent=4)
        except Exception as e:
            log.error("Failed to save confessions file: %s", e)

    def _get_guild_cfg(self, guild: discord.Guild) -> dict:
        gid = str(guild.id)
        if gid not in self.guild_data:
            self.guild_data[gid] = {
                "channel_id": None,
                "counter": 0
            }
        return self.guild_data[gid]

    # ---------- commands ----------

    @commands.hybrid_command(
        name="confessionsetup",
        description="Set or change this server's confession channel."
    )
    @commands.has_permissions(manage_guild=True)
    @app_commands.describe(
        channel="Channel where anonymous confessions will be posted"
    )
    async def confession_setup(
        self,
        ctx: commands.Context,
        channel: discord.TextChannel
    ):
        cfg = self._get_guild_cfg(ctx.guild)
        cfg["channel_id"] = channel.id
        self._save()

        embed = discord.Embed(
            title="✅ Confession channel set",
            description=f"All anonymous confessions will now be sent in {channel.mention}.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Configured by {ctx.author}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed)

    @commands.hybrid_command(
        name="confess",
        description="Send an anonymous confession to the server's confession channel."
    )
    @app_commands.describe(
        text="Your confession (your name will NOT be shown)"
    )
    async def confess(self, ctx: commands.Context, *, text: str):
        cfg = self._get_guild_cfg(ctx.guild)
        channel_id = cfg.get("channel_id")

        if not channel_id:
            # for slash -> ephemeral; for prefix -> normal reply
            if ctx.interaction:
                await ctx.send(
                    "❌ Confession channel is not set yet. Ask a staff member to run `/confessionsetup`.",
                    ephemeral=True
                )
            else:
                await ctx.reply(
                    "❌ Confession channel is not set yet. Ask a staff member to run `/confessionsetup`."
                )
            return

        channel = ctx.guild.get_channel(channel_id)
        if channel is None:
            if ctx.interaction:
                await ctx.send(
                    "❌ The configured confession channel no longer exists. Please ask staff to set it again.",
                    ephemeral=True
                )
            else:
                await ctx.reply(
                    "❌ The configured confession channel no longer exists. Please ask staff to set it again."
                )
            return

        # Increase counter
        cfg["counter"] = cfg.get("counter", 0) + 1
        confession_id = cfg["counter"]
        self._save()

        # Build anonymous embed that goes ONLY to the confession channel
        embed = discord.Embed(
            title=f"🕊️ Confession #{confession_id}",
            description=text,
            color=discord.Color.random(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        await channel.send(embed=embed)

        # ---------- prefix behaviour ----------
        if not ctx.interaction:
            # delete the original command message so chat does not see who confessed
            try:
                await ctx.message.delete()
            except discord.Forbidden:
                pass

            # DM the user a confirmation
            try:
                await ctx.author.send(
                    f"✅ Your anonymous confession **#{confession_id}** has been sent in {channel.mention}."
                )
            except discord.Forbidden:
                # fall back to a quiet message in the channel
                await channel.send(
                    f"✅ An anonymous confession **#{confession_id}** was sent (could not DM the user).",
                    delete_after=5
                )
            return

        # ---------- slash behaviour ----------
        # For slash commands: ephemeral confirmation so only the user sees it
        await ctx.send(
            f"✅ Your anonymous confession **#{confession_id}** has been sent.",
            ephemeral=True
        )


    @commands.hybrid_command(
        name="confessionstats",
        description="Show confession stats for this server."
    )
    async def confession_stats(self, ctx: commands.Context):
        cfg = self._get_guild_cfg(ctx.guild)
        total = cfg.get("counter", 0)

        embed = discord.Embed(
            title="📊 Confession stats",
            color=discord.Color.blurple(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="Total confessions", value=str(total), inline=True)

        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Confession(bot))
    log.info("Loaded Confession cog")

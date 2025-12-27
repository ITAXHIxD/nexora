import discord
from discord.ext import commands
from discord import app_commands
import datetime
from typing import Optional
import logging

logger = logging.getLogger(__name__)

# Cute but clean Spotify logo (make sure the link is correct!)
SPOTIFY_LOGO = "https://i.imgur.com/1b57Ych.png"


class SpotifyStatus(commands.Cog):
    """Show what a user is currently listening to on Spotify via Discord presence."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        logger.info("%s loaded", self.__class__.__name__)

    @commands.hybrid_command(
        name="spotify",
        description="Show what someone is listening to on Spotify right now.",
        aliases=["showspotify", "spt"]
    )
    @app_commands.describe(
        user="The user to check (leave empty to check yourself)"
    )
    async def spotify(
        self,
        ctx: commands.Context,
        user: Optional[discord.Member] = None
    ):
        if not ctx.guild:
            return await ctx.send("❌ This command can only be used in a server.", ephemeral=True)

        target: discord.Member = user or ctx.author
        cached = ctx.guild.get_member(target.id)
        if cached:
            target = cached

        spotify_activity: Optional[discord.Spotify] = None

        for activity in getattr(target, "activities", []):
            if isinstance(activity, discord.Spotify):
                spotify_activity = activity
                break

        if not spotify_activity:
            return await ctx.send(
                f"{target.mention} is **not** listening to Spotify right now, "
                "or their Spotify status is hidden. 💭"
            )

        a = spotify_activity
        track_url = f"https://open.spotify.com/track/{a.track_id}" if a.track_id else None

        # ---------------- PROGRESS BAR ----------------
        bar = "▬▬▬▬▬▬▬▬▬▬🔘▬▬▬▬▬▬▬▬▬▬"
        current_time = "0:00"
        total_time = "??:??"

        if a.start and a.duration:
            now = datetime.datetime.now(datetime.timezone.utc)
            elapsed = now - a.start
            total = a.duration

            progress = max(0.0, min(elapsed.total_seconds() / total.total_seconds(), 1.0))
            bar_length = 20
            filled = int(progress * bar_length)
            empty = bar_length - filled

            bar = "▬" * filled + "🔘" + "▬" * empty

            cur_sec = int(elapsed.total_seconds())
            tot_sec = int(total.total_seconds())

            cur_min, cur_s = divmod(cur_sec, 60)
            tot_min, tot_s = divmod(tot_sec, 60)

            current_time = f"{cur_min}:{cur_s:02}"
            total_time = f"{tot_min}:{tot_s:02}"

        # ---------------- UI BUILD ----------------

        embed = discord.Embed(
            color=discord.Color.from_rgb(30, 215, 96),  # Spotify green
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )

        # Header with Spotify logo (cuter + clear)
        embed.set_author(
            name=f"{target.display_name} • Listening on Spotify",
            icon_url=SPOTIFY_LOGO
        )

        # Cute but clean main text
        embed.description = (
            f"🎶 **{a.title}**\n"
            f"✨ *{', '.join(a.artists)}*\n\n"
            f"`{current_time}`  {bar}  `{total_time}`\n"
        )

        embed.add_field(
            name="Album",
            value=f"`{a.album}`",
            inline=False
        )

        if a.album_cover_url:
            embed.set_thumbnail(url=a.album_cover_url)

        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )

        # -------- BUTTONS (real clickable stuff) --------

        view = None
        if track_url:
            view = SpotifyView(track_url)

        await ctx.send(embed=embed, view=view)


class SpotifyView(discord.ui.View):
    def __init__(self, track_url: str):
        super().__init__(timeout=60)  # 60s is plenty for a link
        # Main link button
        self.add_item(
            discord.ui.Button(
                label="Open in Spotify",
                url=track_url,
                emoji="🎧",
                style=discord.ButtonStyle.link
            )
        )
        # Cute disabled “Now Playing” pill
        self.add_item(
            discord.ui.Button(
                label="Now Playing",
                disabled=True,
                emoji="💚",
                style=discord.ButtonStyle.success
            )
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SpotifyStatus(bot))
    logger.info("Loaded %s", SpotifyStatus.__name__)

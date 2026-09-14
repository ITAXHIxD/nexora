"""
cogs/utility/spotifyview.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Spotify Player & Activity Showcase
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import datetime
import logging
import urllib.parse
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    NexoraView,
    DismissButton,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)

SPOTIFY_GREEN = 0x1DB954
GENIUS_SEARCH = "https://genius.com/search?q="


def fmt_time(seconds: float) -> str:
    s = max(0, int(seconds))
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


def build_progress(a: discord.Spotify):
    """Returns (bar_str, cur_str, tot_str, rem_str, pct_int)"""
    if not (a.start and a.duration):
        return "─" * 12 + "●" + "─" * 8, "0:00", "?:??", "?:??", 0

    now = datetime.datetime.now(datetime.timezone.utc)
    elapsed = (now - a.start).total_seconds()
    total = a.duration.total_seconds()
    if total <= 0:
        return "─" * 12 + "●" + "─" * 8, "0:00", "?:??", "?:??", 0

    pct = max(0.0, min(elapsed / total, 1.0))
    pct_int = int(pct * 100)
    remaining = max(0.0, total - elapsed)

    bar_len = 16
    filled = int(pct * bar_len)
    bar = "━" * filled + "⬤" + "─" * (bar_len - filled)
    return bar, fmt_time(elapsed), fmt_time(total), fmt_time(remaining), pct_int


def block_bar(pct: int, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "▰" * filled + "▱" * (width - filled)


class SpotifyLayoutView(NexoraView):
    """Components V2 Spotify music player card."""

    def __init__(
        self,
        target: discord.Member,
        activity: Optional[discord.Spotify],
        requester: discord.abc.User,
        timeout: float = 180,
    ):
        super().__init__(user_id=requester.id, color=SPOTIFY_GREEN, timeout=timeout)
        self.target = target
        self.activity = activity
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()

        if not self.activity:
            self.add_text(
                f"# 🎵 Nothing Playing on Spotify\n"
                f"> **{self.target.display_name}** is not listening to Spotify, or their Discord activity status is hidden.\n\n"
                f"**How to enable:**\n"
                f"Settings → Activity Privacy → Enable *Display current activity as a status message*."
            )
            self.add_footer("Nexora Spotify Status")
            self.add_row(DismissButton(user_id=self.requester.id))
            return

        a = self.activity
        bar, cur, tot, rem, pct = build_progress(a)
        track_url = f"https://open.spotify.com/track/{a.track_id}" if a.track_id else None
        artists = ", ".join(a.artists)
        album = a.album or "Single"

        # ── Header Section with Album Art ─────────────────────────────────────
        title_md = f"[{a.title}]({track_url})" if track_url else a.title
        header = (
            f"# 🎧 {title_md}\n"
            f"> By **{artists}** · Album: *{album}*\n"
            f"👤 Listener: **{self.target.display_name}**"
        )
        self.add_section(header, thumbnail_url=str(a.album_cover_url) if a.album_cover_url else None)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── Progress Block ────────────────────────────────────────────────────
        progress_content = (
            "### ▶ Track Progress\n"
            f"`{cur}` {bar} `{tot}`\n"
            f"`{block_bar(pct)}` **{pct}%** complete · `{rem}` remaining"
        )
        self.add_text(progress_content)
        self.add_footer(f"Requested by {self.requester.display_name} · Spotify for Discord")

        # ── Action Buttons ────────────────────────────────────────────────────
        buttons = []
        if track_url:
            buttons.append(
                discord.ui.Button(
                    label="Open in Spotify",
                    emoji="🎧",
                    style=discord.ButtonStyle.link,
                    url=track_url,
                )
            )

        btn_refresh = discord.ui.Button(
            label="Refresh",
            emoji="🔄",
            style=discord.ButtonStyle.secondary,
            custom_id="spotify-refresh",
        )
        btn_refresh.callback = self._on_refresh
        buttons.append(btn_refresh)

        btn_lyrics = discord.ui.Button(
            label="Lyrics",
            emoji="🎤",
            style=discord.ButtonStyle.secondary,
            custom_id="spotify-lyrics",
        )
        btn_lyrics.callback = self._on_lyrics
        buttons.append(btn_lyrics)

        buttons.append(DismissButton(user_id=self.requester.id))
        self.add_row(*buttons)

    async def _on_refresh(self, interaction: discord.Interaction):
        member = interaction.guild.get_member(self.target.id) if interaction.guild else None
        if member:
            self.target = member
            self.activity = next(
                (act for act in getattr(member, "activities", []) if isinstance(act, discord.Spotify)),
                None,
            )
        self._build()
        await interaction.response.edit_message(view=self)

    async def _on_lyrics(self, interaction: discord.Interaction):
        if not self.activity:
            await interaction.response.send_message("❌ No track currently playing.", ephemeral=True)
            return
        query = urllib.parse.quote(f"{self.activity.title} {' '.join(self.activity.artists)}")
        url = GENIUS_SEARCH + query
        await interaction.response.send_message(
            f"🎤 Search lyrics for **{self.activity.title}** on Genius:\n<{url}>",
            ephemeral=True,
        )


class SpotifyStatus(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="spotify",
        description="🎧 View live Spotify playback with track progress and lyrics shortcut",
        aliases=["np", "nowplaying", "spt"],
    )
    @app_commands.describe(user="User whose Spotify playback you want to view (defaults to yourself)")
    async def spotify(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        if not ctx.guild:
            await ctx.send("❌ This command must be used within a server.", ephemeral=True)
            return

        target = user or ctx.author
        activity = next(
            (a for a in getattr(target, "activities", []) if isinstance(a, discord.Spotify)),
            None,
        )

        view = SpotifyLayoutView(target, activity, ctx.author)
        await send_view(ctx, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(SpotifyStatus(bot))
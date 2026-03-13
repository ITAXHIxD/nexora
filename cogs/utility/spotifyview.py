"""
cogs/utility/spotifyview.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Commands: n!spotify / /spotify  (aliases: np, nowplaying, spt)

Features:
  • Rich embed — album art thumbnail, clickable track title
  • Dual progress display: ━━⬤─ bar + █░ block bar + %
  • Colour shifts green → teal → blue → gold as song progresses
  • Remaining time + elapsed / total always visible
  • 🔄 Refresh     — re-fetches live progress, disables on track end
  • 🎤 Lyrics      — Genius search link (ephemeral)
  • 🎵 Queue It    — public vote counter, increments on each click
  • 📤 Share       — posts a clean announcement embed publicly
  • Graceful "not playing" embed with setup tip
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import datetime
import logging
import urllib.parse
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

SPOTIFY_LOGO  = "https://i.imgur.com/1b57Ych.png"
GENIUS_SEARCH = "https://genius.com/search?q="

# ── Progress colour: shifts as song advances ───────────────────────────────────
def color_for_pct(pct: int) -> discord.Color:
    if pct >= 85: return discord.Color.from_rgb(255, 180, 50)   # gold — nearly done
    if pct >= 60: return discord.Color.from_rgb(80,  160, 220)  # blue
    if pct >= 30: return discord.Color.from_rgb(30,  180, 140)  # teal-green
    return discord.Color.from_rgb(30, 215, 96)                  # Spotify green


# ── Time formatter ─────────────────────────────────────────────────────────────
def fmt_time(seconds: float) -> str:
    s = max(0, int(seconds))
    m, s = divmod(s, 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02}:{s:02}" if h else f"{m}:{s:02}"


# ── Progress calculation ───────────────────────────────────────────────────────
def build_progress(a: discord.Spotify):
    """Returns (bar_str, cur_str, tot_str, rem_str, pct_int)"""
    if not (a.start and a.duration):
        return "─" * 12 + "●" + "─" * 8, "0:00", "?:??", "?:??", 0

    now       = datetime.datetime.now(datetime.timezone.utc)
    elapsed   = (now - a.start).total_seconds()
    total     = a.duration.total_seconds()
    if total <= 0:
        return "─" * 12 + "●" + "─" * 8, "0:00", "?:??", "?:??", 0

    pct       = max(0.0, min(elapsed / total, 1.0))
    pct_int   = int(pct * 100)
    remaining = max(0.0, total - elapsed)

    BAR    = 22
    filled = int(pct * BAR)
    bar    = "━" * filled + "⬤" + "─" * (BAR - filled)

    return bar, fmt_time(elapsed), fmt_time(total), fmt_time(remaining), pct_int


def block_bar(pct: int, width: int = 10) -> str:
    filled = round(pct / 100 * width)
    return "█" * filled + "░" * (width - filled)


# ── Embed builder ──────────────────────────────────────────────────────────────
def build_embed(
    target: discord.Member,
    a: discord.Spotify,
    requester: discord.Member,
    *,
    refreshed: bool = False,
) -> discord.Embed:
    bar, cur, tot, rem, pct = build_progress(a)
    track_url = f"https://open.spotify.com/track/{a.track_id}" if a.track_id else None
    artists   = ", ".join(a.artists)
    album     = a.album or "Unknown Album"

    embed = discord.Embed(
        color=color_for_pct(pct),
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )

    embed.set_author(
        name=f"{target.display_name}  ·  Listening on Spotify",
        icon_url=target.display_avatar.url,
    )

    if a.album_cover_url:
        embed.set_thumbnail(url=a.album_cover_url)

    title_md = f"[{a.title}]({track_url})" if track_url else a.title
    embed.description = (
        f"## {title_md}\n"
        f"**{artists}**\n"
        f"*{album}*"
    )

    # Progress section
    embed.add_field(
        name="▶  Now Playing",
        value=(
            f"`{cur}` {bar} `{tot}`\n"
            f"{block_bar(pct)} **{pct}%** complete  ·  `{rem}` remaining"
        ),
        inline=False,
    )

    # Stats row
    embed.add_field(name="💿 Album",    value=f"`{album}`",              inline=True)
    embed.add_field(name="⏱ Elapsed",  value=f"`{cur}` / `{tot}`",      inline=True)
    embed.add_field(name="⌛ Left",     value=f"`{rem}` remaining",       inline=True)

    footer = (
        f"{'🔃 Refreshed' if refreshed else '🎵 Requested'} by "
        f"{requester.display_name}  ·  Nexora"
    )
    embed.set_footer(text=footer, icon_url=requester.display_avatar.url)
    return embed


def build_not_playing(target: discord.Member, is_self: bool) -> discord.Embed:
    who = "You're" if is_self else f"**{target.display_name}** is"
    embed = discord.Embed(
        description=(
            f"### 🎵 Nothing playing\n"
            f"{who} not listening to Spotify right now, or their activity is hidden.\n\n"
            f"**To fix:** `User Settings → Activity Privacy → Share your activity`"
        ),
        color=discord.Color.greyple(),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.set_footer(text="Nexora  ·  Spotify Status")
    return embed


# ── View ───────────────────────────────────────────────────────────────────────
class SpotifyView(discord.ui.View):
    def __init__(self, target: discord.Member, activity: discord.Spotify, requester: discord.Member):
        super().__init__(timeout=180)
        self.target        = target
        self.activity      = activity
        self.requester     = requester
        self.queue_voters: set[int] = set()

        if activity.track_id:
            self.add_item(discord.ui.Button(
                label="Open in Spotify",
                url=f"https://open.spotify.com/track/{activity.track_id}",
                emoji="🎧",
                style=discord.ButtonStyle.link,
                row=0,
            ))

    def _disable_interactive(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.url is None:
                child.disabled = True

    @discord.ui.button(label="Refresh", emoji="🔄", style=discord.ButtonStyle.grey, row=1)
    async def refresh(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        member = interaction.guild.get_member(self.target.id)
        if not member:
            return await interaction.followup.send("❌ User not found.", ephemeral=True)

        new_act = next(
            (a for a in getattr(member, "activities", []) if isinstance(a, discord.Spotify)),
            None,
        )
        if not new_act:
            self._disable_interactive()
            return await interaction.edit_original_response(
                embed=build_not_playing(member, member.id == interaction.user.id),
                view=self,
            )

        self.activity = new_act
        await interaction.edit_original_response(
            embed=build_embed(member, new_act, self.requester, refreshed=True),
            view=self,
        )

    @discord.ui.button(label="Lyrics", emoji="🎤", style=discord.ButtonStyle.grey, row=1)
    async def lyrics(self, interaction: discord.Interaction, button: discord.ui.Button):
        a       = self.activity
        query   = urllib.parse.quote(f"{a.title} {' '.join(a.artists)}")
        url     = GENIUS_SEARCH + query
        artists = ", ".join(a.artists)
        await interaction.response.send_message(
            embed=discord.Embed(
                description=(
                    f"**{a.title}** — *{artists}*\n\n"
                    f"[🔍 Search Genius for lyrics]({url})"
                ),
                color=discord.Color.from_rgb(255, 242, 0),
            ).set_footer(text="Powered by Genius  ·  Nexora"),
            ephemeral=True,
        )

    @discord.ui.button(label="Queue It  (0)", emoji="🎵", style=discord.ButtonStyle.blurple, row=1)
    async def queue_it(self, interaction: discord.Interaction, button: discord.ui.Button):
        uid = interaction.user.id
        if uid in self.queue_voters:
            return await interaction.response.send_message(
                "You already voted to queue this!", ephemeral=True
            )
        self.queue_voters.add(uid)
        count        = len(self.queue_voters)
        button.label = f"Queue It  ({count})"
        artists      = ", ".join(self.activity.artists)

        await interaction.response.edit_message(view=self)
        await interaction.followup.send(
            f"🎵 **{interaction.user.display_name}** wants to queue "
            f"**{self.activity.title}** by *{artists}*! "
            f"`{count}` vote{'s' if count != 1 else ''}",
        )

    @discord.ui.button(label="Share", emoji="📤", style=discord.ButtonStyle.grey, row=1)
    async def share(self, interaction: discord.Interaction, button: discord.ui.Button):
        a         = self.activity
        artists   = ", ".join(a.artists)
        _, cur, tot, rem, pct = build_progress(a)
        track_url = f"https://open.spotify.com/track/{a.track_id}" if a.track_id else None

        share_embed = discord.Embed(
            description=(
                f"🎵 **{self.target.display_name}** is listening to\n"
                f"### {f'[{a.title}]({track_url})' if track_url else a.title}\n"
                f"*{artists}*  ·  {a.album}\n\n"
                f"`{cur}` / `{tot}`  ·  **{pct}%**  ·  `{rem}` left\n"
                f"{f'[Open in Spotify]({track_url})' if track_url else ''}"
            ),
            color=discord.Color.from_rgb(30, 215, 96),
        )
        if a.album_cover_url:
            share_embed.set_thumbnail(url=a.album_cover_url)
        share_embed.set_footer(
            text=f"Shared by {interaction.user.display_name}  ·  Nexora",
            icon_url=interaction.user.display_avatar.url,
        )

        button.disabled = True
        button.label    = "Shared ✓"
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=share_embed)


# ── Cog ────────────────────────────────────────────────────────────────────────
class SpotifyStatus(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def cog_load(self):
        logger.info("SpotifyStatus loaded")

    @commands.hybrid_command(
        name="spotify",
        description="Show what someone is listening to on Spotify right now",
        aliases=["np", "nowplaying", "spt"],
    )
    @app_commands.describe(user="Who to check — leave blank for yourself")
    async def spotify(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        if not ctx.guild:
            return await ctx.send(
                embed=discord.Embed(description="❌ Server only.", color=discord.Color.red()),
                ephemeral=True,
            )

        await ctx.defer()

        target  = ctx.guild.get_member((user or ctx.author).id) or ctx.author
        is_self = target.id == ctx.author.id

        activity = next(
            (a for a in getattr(target, "activities", []) if isinstance(a, discord.Spotify)),
            None,
        )

        if not activity:
            return await ctx.send(embed=build_not_playing(target, is_self))

        await ctx.send(
            embed=build_embed(target, activity, ctx.author),
            view=SpotifyView(target, activity, ctx.author),
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(SpotifyStatus(bot))
    logger.info("Loaded SpotifyStatus")
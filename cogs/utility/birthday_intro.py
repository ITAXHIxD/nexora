"""
cogs/utility/birthday_intro.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FREE:
  • Auto-parse birthday from #introductions (with O(1) in-memory channel cache)
  • n!setbirthday  / /setbirthday   — multi-format, disambiguates on-the-spot + UI buttons
  • n!birthday     / /birthday      — interactive dashboard (Set/Edit, Customize Post, Server Setup)
  • n!birthdaylist / /birthdaylist  — upcoming birthdays in the server
  • n!editbirthday                  — fix a wrongly-parsed date
  • n!editprofile  / /editprofile   — fix name, age, pronouns
  • n!myprofile    / /myprofile     — view your full parsed profile + interactive controls
  • n!birthdayhelp                  — interactive command menu
  • n!introbdsetup (admin)          — interactive Server Setup UI or quick CLI setup
  • Daily 00:00 (Midnight) announcement in each server's configured UTC timezone + birthday role
  • Personal announcement message, embed style, live preview, DM wish preference, and 100-msg scan

PREMIUM:
  • n!birthdayscope                 — server-only OR all mutual servers
  • Larger n!scanintros runs (up to 1,000 messages)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import datetime
import inspect
import json
import logging
import os
import re
from typing import Dict, Optional, Set, Tuple

import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

CAKE = "🎂"
PARTY = "🎉"
BALLOON = "🎈"
GIFT = "🎁"
STAR = "⭐"
WAVE = "👋"
PENCIL = "📝"
CROWN = "👑"
LOCK = "🔒"
SPARKLE = "✨"
CHECK = "✅"
CROSS = "❌"
INFO = "ℹ️"
GEAR = "⚙️"
CALENDAR = "📅"

# ── Brand palette ──────────────────────────────────────────────────────────────
BRAND_COLOR = discord.Color.from_rgb(88, 101, 242)     # primary / info
FREE_COLOR = discord.Color.from_rgb(59, 165, 93)       # confirmations
PREMIUM_COLOR = discord.Color.from_rgb(255, 191, 71)   # gold — premium
TODAY_COLOR = discord.Color.from_rgb(255, 115, 179)    # festive birthday highlight
ERROR_COLOR = discord.Color.from_rgb(237, 66, 69)
WARN_COLOR = discord.Color.from_rgb(255, 172, 51)

# ── Common Server UTC Offsets (in minutes) ─────────────────────────────────────
SERVER_TIMEZONE_OPTIONS = [
    ("0", "UTC+00:00 (Midnight UTC — Default)", "🇬🇧"),
    ("330", "UTC+05:30 (IST — India)", "🇮🇳"),
    ("-300", "UTC-05:00 (EST — US/Canada East)", "🇺🇸"),
    ("-240", "UTC-04:00 (EDT — US East Daylight)", "🇺🇸"),
    ("-360", "UTC-06:00 (CST — US/Canada Central)", "🇺🇸"),
    ("-420", "UTC-07:00 (MST — US Mountain)", "🇺🇸"),
    ("-480", "UTC-08:00 (PST — US/Canada West)", "🇺🇸"),
    ("60", "UTC+01:00 (CET — Central Europe)", "🇪🇺"),
    ("120", "UTC+02:00 (EET — Eastern Europe)", "🇪🇺"),
    ("180", "UTC+03:00 (MSK / AST)", "🌍"),
    ("240", "UTC+04:00 (GST — Gulf)", "🇦🇪"),
    ("300", "UTC+05:00 (PKT)", "🇵🇰"),
    ("360", "UTC+06:00 (BST — Bangladesh)", "🇧🇩"),
    ("420", "UTC+07:00 (ICT — Thailand/Vietnam)", "🌏"),
    ("480", "UTC+08:00 (SGT / PHT / AWST)", "🇸🇬"),
    ("540", "UTC+09:00 (JST / KST — Japan/Korea)", "🇯🇵"),
    ("600", "UTC+10:00 (AEST — Australia East)", "🇦🇺"),
    ("720", "UTC+12:00 (NZST — New Zealand)", "🇳🇿"),
    ("-180", "UTC-03:00 (BRT — Brazil/Argentina)", "🇧🇷"),
]

# ── Regex patterns ─────────────────────────────────────────────────────────────
BIRTHDAY_RE = re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})(?:[\/\-\.](\d{2,4}))?\b")
NAME_RE = [
    re.compile(r"(?:name\s*[:\-–]\s*)([A-Za-z][\w\s]{0,30}?)(?:\s*[,\n]|$)", re.I),
    re.compile(r"(?:i'?m|i am|call me|known as)\s+([A-Za-z][\w]{1,20})", re.I),
    re.compile(r"(?:hi|hey|hello)[,!]?\s+(?:i'?m|i am)\s+([A-Za-z][\w]{1,20})", re.I),
]
AGE_RE = [
    re.compile(r"(?:age\s*[:\-–]\s*)(\d{1,2})", re.I),
    re.compile(r"\b(\d{1,2})\s*(?:years?\s*old|yo\b)", re.I),
    re.compile(r"(?:i'?m|i am)\s+(\d{1,2})(?:\s*years?\s*old)?", re.I),
]
PRONOUNS_RE = [
    re.compile(r"(?:pronouns?\s*[:\-–]\s*)([\w]+(?:\/[\w]+)+)", re.I),
    re.compile(r"\b(she\/her|he\/him|they\/them|she\/they|he\/they|any\/all|xe\/xem|ze\/zir)\b", re.I),
]


# ── Parse & Time Helpers ───────────────────────────────────────────────────────

def format_utc_offset(offset_minutes: int) -> str:
    sign = "+" if offset_minutes >= 0 else "-"
    total = abs(int(offset_minutes))
    h, m = divmod(total, 60)
    return f"UTC{sign}{h:02d}:{m:02d}"


def get_server_now(offset_minutes: int = 0) -> datetime.datetime:
    tz = datetime.timezone(datetime.timedelta(minutes=int(offset_minutes or 0)))
    return datetime.datetime.now(tz)


def try_parse_date(d, m, y=None):
    """Returns (month, day, year, ambiguous) or None."""
    d, m = int(d), int(m)
    year = int(y) if y else None
    if year and year < 100:
        year += 2000
    results = []
    try:
        datetime.date(year or 2000, m, d)
        results.append((m, d))
    except ValueError:
        pass
    try:
        datetime.date(year or 2000, d, m)
        results.append((d, m))
    except ValueError:
        pass
    if not results:
        return None
    mo, dy = results[0]
    return mo, dy, year, len(results) > 1


def parse_flexible_date_input(date_str: str, year: Optional[int] = None):
    """
    Parses flexible birthday input strings like '15/04', '04/15', '15-04-2001',
    'April 15', '15 April 2002', etc.
    Returns (month, day, yr, ambiguous, numeric_match) or None.
    """
    date_str = date_str.strip()
    m = re.match(r"^(\d{1,2})[\/\-\.](\d{1,2})(?:[\/\-\.](\d{2,4}))?$", date_str)
    if m:
        parsed = try_parse_date(m.group(1), m.group(2), m.group(3) or (str(year) if year else None))
        if not parsed:
            return None
        month, day, yr, ambiguous = parsed
        return month, day, yr, ambiguous, m

    # Text month formats
    cleaned = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", date_str, flags=re.I)
    tokens = cleaned.replace(",", " ").split()
    if len(tokens) >= 2:
        maybe_year = year
        if len(tokens) >= 3 and tokens[2].isdigit():
            maybe_year = int(tokens[2])
            if maybe_year < 100:
                maybe_year += 2000
        two_part = " ".join(tokens[:2])
        for fmt in ("%B %d", "%b %d", "%d %B", "%d %b"):
            try:
                pd = datetime.datetime.strptime(two_part, fmt)
                return pd.month, pd.day, maybe_year, False, None
            except ValueError:
                continue
    return None


def parse_name(t: str) -> Optional[str]:
    for p in NAME_RE:
        m = p.search(t)
        if m:
            n = m.group(1).strip().split()[0]
            if len(n) >= 2:
                return n.capitalize()
    return None


def parse_age(t: str) -> Optional[int]:
    for p in AGE_RE:
        m = p.search(t)
        if m:
            a = int(m.group(1))
            if 10 <= a <= 100:
                return a
    return None


def parse_pronouns(t: str) -> Optional[str]:
    for p in PRONOUNS_RE:
        m = p.search(t)
        if m:
            return m.group(1).lower()
    return None


def ordinal(n: int) -> str:
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10 if n % 100 not in (11, 12, 13) else 0, "th")


def month_name(m: int) -> str:
    return datetime.date(2000, int(m), 1).strftime("%B")


def next_birthday(month: int, day: int, offset_minutes: int = 0) -> datetime.datetime:
    now = get_server_now(offset_minutes)
    tz = now.tzinfo or datetime.timezone.utc
    try:
        c = datetime.datetime(now.year, int(month), int(day), 0, 0, tzinfo=tz)
    except ValueError:
        c = datetime.datetime(now.year, 3, 1, 0, 0, tzinfo=tz)
    if c.date() < now.date():
        try:
            c = datetime.datetime(now.year + 1, int(month), int(day), 0, 0, tzinfo=tz)
        except ValueError:
            c = datetime.datetime(now.year + 1, 3, 1, 0, 0, tzinfo=tz)
    return c


def days_until(month: int, day: int, offset_minutes: int = 0) -> int:
    today = get_server_now(offset_minutes).date()
    return (next_birthday(month, day, offset_minutes).date() - today).days


def is_today(month: int, day: int, offset_minutes: int = 0) -> bool:
    n = get_server_now(offset_minutes)
    return n.month == int(month) and n.day == int(day)


def safe_format_birthday_text(
    template: str,
    *,
    mention: str,
    name: str,
    server: str = "our server",
    age: Optional[int] = None,
) -> str:
    """
    Safely replaces {mention}, {user}, {name}, {server}, and {age} placeholders
    without throwing KeyError or ValueError on arbitrary user text.
    """
    age_str = ordinal(age) if age is not None else ""
    out = template
    replacements = {
        "{mention}": mention,
        "{user}": mention,
        "{name}": name,
        "{server}": server,
        "{age}": age_str,
    }
    for k, v in replacements.items():
        out = re.sub(re.escape(k), v, out, flags=re.IGNORECASE)
    return out.strip()


# ── Shared Embed Builders ──────────────────────────────────────────────────────

def base_embed(*, title=None, description=None, color=BRAND_COLOR, ctx: Optional[commands.Context] = None):
    embed = discord.Embed(
        title=title,
        description=description,
        color=color,
        timestamp=datetime.datetime.now(datetime.timezone.utc),
    )
    if ctx is not None:
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url,
        )
    return embed


def error_embed(text: str, ctx: Optional[commands.Context] = None):
    return base_embed(title=f"{CROSS} Something's not right", description=text, color=ERROR_COLOR, ctx=ctx)


def success_embed(title: str, description: str, ctx: Optional[commands.Context] = None):
    return base_embed(title=f"{CHECK} {title}", description=description, color=FREE_COLOR, ctx=ctx)


def premium_embed():
    return discord.Embed(
        title=f"{CROWN} Premium Feature",
        description=(
            f"This command is part of **Premium**.\n\n"
            f"Birthday setup, edits, privacy controls, and standard history scans are free. "
            f"Premium is reserved for server-scale extras:\n\n"
            f"{SPARKLE} Cross-server birthday broadcasting\n"
            f"{SPARKLE} Larger intro-history scans (up to 1,000 messages)\n\n"
            f"Ask a server admin or the bot owner about upgrading!"
        ),
        color=PREMIUM_COLOR,
    )


async def send_ui(destination, *, content=None, embed=None, view=None, ephemeral=False, **kwargs):
    """
    Universal sender supporting standard Discord Embeds + Views as well as
    Components V2 LayoutViews across Interactions, Contexts, and Messageables.
    """
    is_layout_view = hasattr(discord.ui, "LayoutView") and isinstance(view, discord.ui.LayoutView)

    send_kwargs = dict(kwargs)
    if is_layout_view:
        if embed is not None and hasattr(view, "set_card"):
            view.set_card(embed)
        send_kwargs.pop("content", None)
        send_kwargs.pop("embed", None)
        send_kwargs.pop("embeds", None)
        if view is not None:
            send_kwargs["view"] = view
    else:
        if content is not None:
            send_kwargs["content"] = content
        if embed is not None:
            send_kwargs["embed"] = embed
        if view is not None:
            send_kwargs["view"] = view

    if isinstance(destination, discord.Interaction):
        if destination.response.is_done():
            message = await destination.followup.send(ephemeral=ephemeral, **send_kwargs)
        else:
            await destination.response.send_message(ephemeral=ephemeral, **send_kwargs)
            try:
                message = await destination.original_response()
            except (discord.NotFound, discord.HTTPException):
                message = None
    elif isinstance(destination, commands.Context):
        interaction = destination.interaction
        if interaction is not None:
            if interaction.response.is_done():
                message = await interaction.followup.send(ephemeral=ephemeral, **send_kwargs)
            else:
                await interaction.response.send_message(ephemeral=ephemeral, **send_kwargs)
                try:
                    message = await interaction.original_response()
                except (discord.NotFound, discord.HTTPException):
                    message = None
        else:
            message = await destination.send(**send_kwargs)
    else:
        message = await destination.send(**send_kwargs)

    if view is not None and message is not None and hasattr(view, "message"):
        view.message = message
    return message


# ── Presets & Default Templates ────────────────────────────────────────────────

BIRTHDAY_WISH_PRESETS = {
    "sweet": (
        "Sweet & Kind",
        "Wishing you a birthday full of happiness, laughter, and all the little things "
        "that make you smile. Hope this year treats you wonderfully! 💛",
    ),
    "funny": (
        "Funny",
        "Congrats on completing another trip around the sun! 🎂 May your cake be huge, "
        "your responsibilities be tiny, and nobody expose your age in chat. 😂",
    ),
    "heartfelt": (
        "Heartfelt",
        "I hope this new year of your life brings you peace, good people, big wins, "
        "and plenty of reasons to be proud of yourself. Happy Birthday! 💖",
    ),
    "friendly": (
        "Friendly",
        "Happy Birthday! 🥳 Hope you have an awesome day, make some great memories, "
        "and get spoiled with all the good stuff!",
    ),
    "playful": (
        "Playful",
        "Birthday rules: cake is mandatory, chores are optional, and you're legally "
        "allowed to be the main character today. Have the best one! 🎉",
    ),
    "short": (
        "Short & Sweet",
        "Happy Birthday! 🎂 Hope your day is amazing!",
    ),
}

DEFAULT_BIRTHDAY_MESSAGE_TEXT = f"{PARTY} **Happy Birthday {{mention}}!** Help us celebrate and drop a birthday wish below! {CAKE}"
DEFAULT_BIRTHDAY_EMBED_TEXT = (
    f"Wishing {{mention}} the happiest of birthdays from everyone in **{{server}}**! "
    f"May your year ahead be filled with awesome memories, great vibes, and plenty of cake! {SPARKLE}"
)


def build_birthday_announcement_payload(
    *,
    member: discord.Member,
    guild: discord.Guild,
    doc: dict,
    settings: dict,
    now: datetime.datetime,
    is_prem: bool = False,
    ping_role: Optional[discord.Role] = None,
) -> Tuple[Optional[str], Optional[discord.Embed], discord.AllowedMentions]:
    """
    Builds a clean, non-repetitive (message_content, embed, allowed_mentions) tuple
    for a birthday announcement, ensuring member and role mentions always ping properly.
    """
    display = doc.get("name") or member.display_name
    month = int(doc.get("month") or now.month)
    day = int(doc.get("day") or now.day)
    bd_date_str = f"{month_name(month)} {ordinal(day)}"

    age_val: Optional[int] = None
    if doc.get("year"):
        try:
            age_val = now.year - int(doc["year"]) - ((now.month, now.day) < (month, day))
            if age_val <= 0 or age_val > 120:
                age_val = None
        except (TypeError, ValueError):
            age_val = None

    announcement_style = doc.get("announcement_style") or settings.get("default_style") or "both"
    if announcement_style not in {"embed", "message", "both"}:
        announcement_style = "both"

    normal_template = (
        doc.get("custom_message")
        or settings.get("server_message")
        or DEFAULT_BIRTHDAY_MESSAGE_TEXT
    )
    embed_template = (
        doc.get("custom_wish")
        or settings.get("server_embed_text")
        or DEFAULT_BIRTHDAY_EMBED_TEXT
    )

    normal_rendered = safe_format_birthday_text(
        normal_template,
        mention=member.mention,
        name=display,
        server=guild.name,
        age=age_val,
    )
    embed_rendered = safe_format_birthday_text(
        embed_template,
        mention=member.mention,
        name=display,
        server=guild.name,
        age=age_val,
    )

    # Ensure pings are always in message content so Discord triggers notifications
    ping_tokens = []
    if f"<@{member.id}>" not in normal_rendered and f"<@!{member.id}>" not in normal_rendered:
        ping_tokens.append(member.mention)
    if ping_role and ping_role.mention not in normal_rendered:
        ping_tokens.append(ping_role.mention)

    # Build rich celebratory Embed
    embed_desc_parts = [embed_rendered]
    if age_val is not None:
        embed_desc_parts.append(f"\n{STAR} Turning **{ordinal(age_val)}** today!")
    if doc.get("pronouns"):
        embed_desc_parts.append(f"🏳️‍🌈 **Pronouns:** `{doc['pronouns']}`")

    embed = discord.Embed(
        title=f"{CAKE} Happy Birthday, {display}! {PARTY}",
        description="\n".join(embed_desc_parts),
        color=PREMIUM_COLOR if is_prem else TODAY_COLOR,
        timestamp=now,
    )
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name=f"{CALENDAR} Birthday", value=f"**{bd_date_str}**", inline=True)
    embed.add_field(
        name=f"{GIFT} Send a Wish",
        value="Click **Send Birthday Wish** below!",
        inline=True,
    )
    offset_mins = int(settings.get("utc_offset_minutes", 0) or 0)
    embed.set_footer(
        text=f"{guild.name} • Birthday Celebration ({format_utc_offset(offset_mins)})",
        icon_url=guild.icon.url if guild.icon else None,
    )

    if announcement_style == "embed":
        only_pings = [member.mention]
        if ping_role:
            only_pings.append(ping_role.mention)
        message_content = f"{PARTY} " + " ".join(only_pings)
        message_embed = embed
    elif announcement_style == "message":
        extra_info = f"\n{STAR} Turning **{ordinal(age_val)}** today!" if age_val is not None else ""
        full_normal = (" ".join(ping_tokens) + " " + normal_rendered).strip() if ping_tokens else normal_rendered
        message_content = f"{full_normal}{extra_info}\n\n*Use the buttons below to send a birthday wish!*"
        message_embed = None
    else:
        message_content = (" ".join(ping_tokens) + "\n" + normal_rendered).strip() if ping_tokens else normal_rendered
        message_embed = embed

    allowed_mentions = discord.AllowedMentions(
        users=[member],
        roles=[ping_role] if ping_role else [],
        everyone=False,
        replied_user=False,
    )
    return message_content, message_embed, allowed_mentions


# ── Interactive Views & Modals ─────────────────────────────────────────────────

class AmbiguousDateView(discord.ui.View):
    """Ask user to pick which date interpretation (DD/MM vs MM/DD) is correct."""

    def __init__(self, user_id: int, opt_a: tuple, opt_b: tuple, timeout=120):
        super().__init__(timeout=timeout)
        self.user_id = user_id
        self.chosen = None
        self.opt_a = opt_a
        self.opt_b = opt_b

        for label, cid, style in [
            (f"{month_name(opt_a[0])} {opt_a[1]} (DD/MM)", "a", discord.ButtonStyle.blurple),
            (f"{month_name(opt_b[0])} {opt_b[1]} (MM/DD)", "b", discord.ButtonStyle.green),
        ]:
            btn = discord.ui.Button(label=label, custom_id=f"birthday-date-{cid}", style=style, emoji=CALENDAR)

            async def cb(i: discord.Interaction, _c=cid):
                self.chosen = _c
                self.stop()
                await i.response.defer()

            btn.callback = cb
            self.add_item(btn)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "Only the member setting this birthday can choose the date.", ephemeral=True
        )
        return False


class BirthdayAnnouncementView(discord.ui.View):
    """
    Persistent 24/7 birthday announcement buttons (Send Birthday Wish & View Wishers).
    Never times out so members across all timezones can wish the birthday person all day!
    """

    def __init__(self, cog, uid: int, guild_id: int, timeout: Optional[float] = None):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.uid = int(uid)
        self.guild_id = int(guild_id)
        self.wishers: Set[int] = cog.get_wishers_set(self.guild_id, self.uid)

        self.wish_btn = discord.ui.Button(
            label="Send Birthday Wish",
            style=discord.ButtonStyle.success,
            emoji=PARTY,
            custom_id=f"bday:wish:{self.guild_id}:{self.uid}",
        )
        self.wish_btn.callback = self._on_wish_click
        self.add_item(self.wish_btn)

        self.view_btn = discord.ui.Button(
            label="View Wishers",
            style=discord.ButtonStyle.secondary,
            emoji=GIFT,
            custom_id=f"bday:wishers:{self.guild_id}:{self.uid}",
        )
        self.view_btn.callback = self._on_wishers_click
        self.add_item(self.view_btn)

    async def deliver_wish(self, interaction: discord.Interaction, wish_type: str, message: str):
        """DM one selected birthday wish and report success/failure to the UI."""
        sender_id = interaction.user.id
        if sender_id == self.uid:
            return False, "❌ You can't send a birthday wish to yourself!"
        if sender_id in self.wishers:
            return False, "✅ You've already sent them a birthday wish today!"

        guild = self.cog.bot.get_guild(self.guild_id)
        if guild is None:
            return False, "❌ I couldn't find the server for this birthday wish."

        member = guild.get_member(self.uid)
        if member is None:
            try:
                member = await guild.fetch_member(self.uid)
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                return False, "❌ I couldn't find that member in the server."

        profile = await self.cog.get_user(self.uid, self.guild_id) or {}
        self.wishers.add(sender_id)

        if not profile.get("dm_notifications", True):
            return True, f"{PARTY} Your **{wish_type.lower()}** birthday wish was recorded! *(They have DMs paused, so it was logged on their card.)*"

        wish_embed = discord.Embed(
            title=f"{PARTY} You've Got a Birthday Wish!",
            description=(
                f"**{interaction.user.display_name}** ({interaction.user.mention}) from **{guild.name}** "
                f"sent you a **{wish_type}** birthday wish:\n\n"
                f"> {message}"
            ),
            color=TODAY_COLOR,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        wish_embed.set_thumbnail(url=interaction.user.display_avatar.url)
        wish_embed.set_footer(text=f"{guild.name} • Nexora Birthday System")

        try:
            await member.send(embed=wish_embed)
        except discord.Forbidden:
            return True, f"{PARTY} Your **{wish_type.lower()}** wish was recorded on the server card! *(Their DMs are closed.)*"
        except discord.HTTPException as exc:
            logger.warning("Birthday wish DM failed for user %s: %s", self.uid, exc)
            return True, f"{PARTY} Your **{wish_type.lower()}** wish was recorded!"

        return True, f"{PARTY} Your **{wish_type.lower()}** birthday wish was sent to **{member.display_name}**!"

    async def _on_wish_click(self, interaction: discord.Interaction):
        if interaction.user.id == self.uid:
            return await interaction.response.send_message(
                f"{CROSS} You can't wish yourself!", ephemeral=True
            )
        if interaction.user.id in self.wishers:
            return await interaction.response.send_message(
                f"{CHECK} You've already wished them from this birthday card!", ephemeral=True
            )

        picker_embed = discord.Embed(
            title=f"{CAKE} Send a Birthday Wish",
            description="Choose a wish preset from the dropdown below, or select **✍️ Write my own** to send a personal message!",
            color=TODAY_COLOR,
        )
        await interaction.response.send_message(
            embed=picker_embed,
            view=BirthdayWishPickerView(self, requester_id=interaction.user.id),
            ephemeral=True,
        )

    async def _on_wishers_click(self, interaction: discord.Interaction):
        count = len(self.wishers)
        if not count:
            return await interaction.response.send_message(
                "No wishes sent yet — click **🎉 Send Birthday Wish** to be the first!",
                ephemeral=True,
            )
        mentions = ", ".join(f"<@{w}>" for w in list(self.wishers)[:25])
        await interaction.response.send_message(
            f"🎊 **{count}** {'person has' if count == 1 else 'people have'} sent a birthday wish so far:\n{mentions}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


# Backward-compatible alias
WishView = BirthdayAnnouncementView


class BirthdayWishPickerView(discord.ui.View):
    """Ephemeral wish-type picker shown when the birthday button is clicked."""

    def __init__(self, announcement_view: BirthdayAnnouncementView, requester_id: int, timeout=120):
        super().__init__(timeout=timeout)
        self.announcement_view = announcement_view
        self.requester_id = requester_id
        self.add_item(BirthdayWishTypeSelect(self))

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requester_id:
            return True
        await interaction.response.send_message(
            "Only the person who opened this wish menu can use it.", ephemeral=True
        )
        return False


class BirthdayWishTypeSelect(discord.ui.Select):
    def __init__(self, picker: BirthdayWishPickerView):
        self.picker = picker
        options = []
        for key, emoji in [
            ("sweet", "💛"),
            ("funny", "😂"),
            ("heartfelt", "💖"),
            ("friendly", "🥳"),
            ("playful", "🎉"),
            ("short", "🎂"),
        ]:
            label, message = BIRTHDAY_WISH_PRESETS[key]
            options.append(
                discord.SelectOption(
                    label=label,
                    value=key,
                    description=message[:100],
                    emoji=emoji,
                )
            )
        options.append(
            discord.SelectOption(
                label="Write my own",
                value="custom",
                description="Type a personal birthday message yourself",
                emoji="✍️",
            )
        )
        super().__init__(
            placeholder="Choose a wish style…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"birthday-wish-type-{picker.requester_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        choice = self.values[0]
        announcement = self.picker.announcement_view
        if choice == "custom":
            await interaction.response.send_modal(
                BirthdayCustomWishModal(
                    announcement,
                    requester_id=self.picker.requester_id,
                )
            )
            return

        label, message = BIRTHDAY_WISH_PRESETS[choice]
        await interaction.response.defer(ephemeral=True, thinking=True)
        _, result = await announcement.deliver_wish(interaction, label, message)
        await interaction.followup.send(result, ephemeral=True)


class BirthdayCustomWishModal(discord.ui.Modal, title="Write a Birthday Wish"):
    message = discord.ui.TextInput(
        label="Your birthday message",
        placeholder="Write something kind, funny, or personal…",
        style=discord.TextStyle.paragraph,
        min_length=2,
        max_length=500,
        required=True,
    )

    def __init__(self, announcement_view: BirthdayAnnouncementView, requester_id: int):
        super().__init__(timeout=300)
        self.announcement_view = announcement_view
        self.requester_id = requester_id

    async def on_submit(self, interaction: discord.Interaction):
        if interaction.user.id != self.requester_id:
            return await interaction.response.send_message(
                "Only the person who opened this wish menu can submit it.", ephemeral=True
            )
        await interaction.response.defer(ephemeral=True, thinking=True)
        _, result = await self.announcement_view.deliver_wish(
            interaction, "Personal", str(self.message.value).strip()
        )
        await interaction.followup.send(result, ephemeral=True)


# ── User Interactive Setup Modals & Views ──────────────────────────────────────

class QuickSetBirthdayModal(discord.ui.Modal, title="🎂 Set or Edit Your Birthday"):
    date_input = discord.ui.TextInput(
        label="Birthday Date (Day & Month)",
        placeholder="e.g. April 15  |  15 April  |  15/04",
        max_length=32,
        required=True,
    )
    year_input = discord.ui.TextInput(
        label="Birth Year (Optional — for age display)",
        placeholder="e.g. 2003 (leave blank to hide age)",
        max_length=4,
        required=False,
    )
    name_input = discord.ui.TextInput(
        label="Preferred Name (Optional)",
        placeholder="e.g. Alex",
        max_length=32,
        required=False,
    )
    pronouns_input = discord.ui.TextInput(
        label="Pronouns (Optional)",
        placeholder="e.g. he/him, she/her, they/them",
        max_length=32,
        required=False,
    )

    def __init__(self, cog, existing: Optional[dict] = None):
        super().__init__(timeout=300)
        self.cog = cog
        if existing:
            if existing.get("month") and existing.get("day"):
                self.date_input.default = f"{month_name(existing['month'])} {existing['day']}"
            if existing.get("year"):
                self.year_input.default = str(existing["year"])
            if existing.get("name"):
                self.name_input.default = str(existing["name"])
            if existing.get("pronouns"):
                self.pronouns_input.default = str(existing["pronouns"])

    async def on_submit(self, interaction: discord.Interaction):
        yr_val = None
        if self.year_input.value and self.year_input.value.strip():
            raw_yr = self.year_input.value.strip()
            if not raw_yr.isdigit() or not (1920 <= int(raw_yr) <= datetime.datetime.now().year):
                return await interaction.response.send_message(
                    "❌ Please enter a valid 4-digit birth year (e.g. `2002`) or leave it blank.",
                    ephemeral=True,
                )
            yr_val = int(raw_yr)

        parsed = parse_flexible_date_input(self.date_input.value, yr_val)
        if not parsed:
            return await interaction.response.send_message(
                "❌ Couldn't understand that date format.\n"
                "**Try:** `April 15` • `15 April` • `15/04` • `15-04-2002`",
                ephemeral=True,
            )

        month, day, yr, _, _ = parsed
        existing = await self.cog.get_user(interaction.user.id, interaction.guild.id) or {}
        update = {
            **{k: existing.get(k) for k in ("custom_wish", "custom_message", "announcement_style", "scope", "dm_notifications", "name", "age", "pronouns") if k in existing},
            "month": month,
            "day": day,
            "year": yr,
            "source": "modal",
        }
        if self.name_input.value and self.name_input.value.strip():
            update["name"] = self.name_input.value.strip()
        if self.pronouns_input.value and self.pronouns_input.value.strip():
            update["pronouns"] = self.pronouns_input.value.strip().lower()

        await self.cog.upsert_user(interaction.user.id, interaction.guild.id, update)

        settings = await self.cog.get_settings(interaction.guild.id)
        offset = int(settings.get("utc_offset_minutes", 0) or 0)
        d_left = days_until(month, day, offset)
        status = f"{PARTY} **That's TODAY!**" if d_left == 0 else f"Coming up in **{d_left}** days!"

        embed = discord.Embed(
            title=f"{CAKE} Birthday Saved!",
            description=(
                f"**Date:** {month_name(month)} {ordinal(day)}" + (f", {yr}" if yr else "") + f"\n"
                f"**Countdown:** {status}\n"
                + (f"**Name:** {update['name']}\n" if update.get("name") else "")
                + (f"**Pronouns:** {update['pronouns']}\n" if update.get("pronouns") else "")
                + f"\n✨ Announcements send automatically at **00:00 Midnight ({format_utc_offset(offset)})**!"
            ),
            color=FREE_COLOR,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        await interaction.response.send_message(embed=embed, ephemeral=True)

        # If their birthday is today, trigger the birthday check right away so they get wished ASAP!
        if d_left == 0:
            asyncio.create_task(self.cog._run_birthday_check())


class BirthdayWishSetupView(discord.ui.View):
    """Interactive studio for customizing user birthday announcement format, message, embed, and DM notifications."""

    def __init__(
        self,
        cog,
        user_id: int,
        guild_id: int,
        user_mention: str,
        display_name: str,
        *,
        announcement_style: str = "both",
        custom_wish: Optional[str] = None,
        custom_message: Optional[str] = None,
        dm_notifications: bool = True,
        timeout=240,
    ):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.user_mention = user_mention
        self.display_name = display_name
        self.announcement_style = announcement_style if announcement_style in {"embed", "message", "both"} else "both"
        self.custom_wish = custom_wish
        self.custom_message = custom_message
        self.dm_notifications = dm_notifications
        self.message_style = self._get_message_style(custom_wish)
        self.add_item(BirthdayAnnouncementFormatSelect(self))
        self.add_item(BirthdayWishSetupSelect(self))

    @staticmethod
    def _get_message_style(custom_wish: Optional[str]) -> str:
        if not custom_wish:
            return "default"
        for key, (_, message) in BIRTHDAY_WISH_PRESETS.items():
            if custom_wish == message:
                return key
        return "custom"

    def format_label(self) -> str:
        return {
            "embed": "🖼️ Embed Card Only (with Ping)",
            "message": "💬 Plain Text Message Only",
            "both": "✨ Both Celebratory Message + Embed Card",
        }.get(self.announcement_style, "✨ Both Celebratory Message + Embed Card")

    def message_label(self) -> str:
        if self.message_style == "default":
            return "Default celebratory card text"
        if self.message_style == "custom":
            return "Custom card text"
        return BIRTHDAY_WISH_PRESETS[self.message_style][0]

    def normal_message_label(self) -> str:
        return "Custom message above embed" if self.custom_message else "Default celebratory ping message"

    def summary_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title="🎨 Customize Your Birthday Announcement",
            description=(
                "Personalize how Nexora announces your birthday at **00:00 Midnight**!\n"
                "You can use `{mention}`, `{name}`, `{age}`, and `{server}` in your custom texts."
            ),
            color=BRAND_COLOR,
        )
        embed.add_field(name="📐 Announcement Format", value=self.format_label(), inline=False)
        embed.add_field(name="💬 Message Text (Outside Embed)", value=self.normal_message_label(), inline=True)
        embed.add_field(name="🖼️ Embed Card Style", value=self.message_label(), inline=True)
        embed.add_field(
            name="📬 Wish DM Notifications",
            value="🟢 **Enabled**" if self.dm_notifications else "🔴 **Disabled**",
            inline=True,
        )
        embed.set_footer(text="Use the dropdowns and buttons below to customize or preview your birthday post")
        return embed

    def summary(self) -> str:
        return (
            "# 🎂 Birthday Announcement Settings\n\n"
            f"**Format:** {self.format_label()}\n"
            f"**Normal message:** {self.normal_message_label()}\n"
            f"**Embed card text:** {self.message_label()}\n"
            f"**Wish DMs:** {'Enabled ✅' if self.dm_notifications else 'Disabled ❌'}"
        )

    def refreshed(self):
        return BirthdayWishSetupView(
            self.cog,
            self.user_id,
            self.guild_id,
            self.user_mention,
            self.display_name,
            announcement_style=self.announcement_style,
            custom_wish=self.custom_wish,
            custom_message=self.custom_message,
            dm_notifications=self.dm_notifications,
            timeout=self.timeout,
        )

    @discord.ui.button(
        label="Customize Message + Embed",
        style=discord.ButtonStyle.primary,
        emoji="📝",
        row=2,
    )
    async def customize_birthday_texts(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        await interaction.response.send_modal(
            BirthdayAnnouncementTextsModal(
                self.cog,
                self.user_id,
                self.guild_id,
                self.user_mention,
                self.display_name,
                custom_message=self.custom_message,
                custom_wish=self.custom_wish,
            )
        )

    @discord.ui.button(
        label="Preview My Post",
        style=discord.ButtonStyle.secondary,
        emoji="👁️",
        row=2,
    )
    async def preview_birthday_post(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        doc = await self.cog.get_user(self.user_id, self.guild_id) or {}
        doc = {
            **doc,
            "announcement_style": self.announcement_style,
            "custom_wish": self.custom_wish,
            "custom_message": self.custom_message,
            "month": doc.get("month") or 1,
            "day": doc.get("day") or 1,
        }
        settings = await self.cog.get_settings(self.guild_id)
        now = get_server_now(int(settings.get("utc_offset_minutes", 0) or 0))
        is_prem = await self.cog.is_premium(self.guild_id)
        content, embed, _ = build_birthday_announcement_payload(
            member=interaction.user,
            guild=interaction.guild,
            doc=doc,
            settings=settings,
            now=now,
            is_prem=is_prem,
        )
        preview_header = "👀 **Live Preview of Your Birthday Announcement:**\n*(This is how it will appear at 00:00 Midnight)*\n\n"
        await interaction.response.send_message(
            content=preview_header + (content or ""),
            embed=embed,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )

    @discord.ui.button(
        label="Toggle Wish DMs",
        style=discord.ButtonStyle.secondary,
        emoji="📬",
        row=2,
    )
    async def toggle_wish_dms(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        self.dm_notifications = not self.dm_notifications
        await self.cog.upsert_user(
            self.user_id,
            self.guild_id,
            {"dm_notifications": self.dm_notifications},
        )
        refreshed = self.refreshed()
        await interaction.response.edit_message(embed=refreshed.summary_embed(), content=None, view=refreshed)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message(
            "Only the member who opened this settings menu can use it.", ephemeral=True
        )
        return False


class BirthdayAnnouncementTextsModal(discord.ui.Modal, title="Customize Birthday Texts"):
    """Edit the normal message and embed card description independently."""

    def __init__(
        self,
        cog,
        user_id: int,
        guild_id: int,
        user_mention: str,
        display_name: str,
        *,
        custom_message: Optional[str] = None,
        custom_wish: Optional[str] = None,
    ):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.user_mention = user_mention
        self.display_name = display_name
        self.normal_text = discord.ui.TextInput(
            label="Normal message text (Outside Embed)",
            placeholder="Placeholders: {mention}, {name}, {age}, {server}",
            default=custom_message or DEFAULT_BIRTHDAY_MESSAGE_TEXT,
            style=discord.TextStyle.paragraph,
            min_length=0,
            max_length=1500,
            required=False,
        )
        self.embed_text = discord.ui.TextInput(
            label="Embed card text (Inside Embed)",
            placeholder="Placeholders: {mention}, {name}, {age}, {server}",
            default=custom_wish or DEFAULT_BIRTHDAY_EMBED_TEXT,
            style=discord.TextStyle.paragraph,
            min_length=0,
            max_length=2000,
            required=False,
        )
        self.add_item(self.normal_text)
        self.add_item(self.embed_text)

    async def on_submit(self, interaction: discord.Interaction):
        normal_raw = str(self.normal_text.value).strip() or None
        embed_raw = str(self.embed_text.value).strip() or None
        guild_name = interaction.guild.name if interaction.guild else "Server"

        normal_preview = safe_format_birthday_text(
            normal_raw or DEFAULT_BIRTHDAY_MESSAGE_TEXT,
            mention=self.user_mention,
            name=self.display_name,
            server=guild_name,
        )
        embed_preview = safe_format_birthday_text(
            embed_raw or DEFAULT_BIRTHDAY_EMBED_TEXT,
            mention=self.user_mention,
            name=self.display_name,
            server=guild_name,
        )

        await self.cog.upsert_user(
            self.user_id,
            self.guild_id,
            {"custom_message": normal_raw, "custom_wish": embed_raw},
        )
        await interaction.response.send_message(
            "✅ **Birthday announcement texts saved!**\n\n"
            f"**Normal message preview:**\n{normal_preview}\n\n"
            f"**Embed card preview:**\n{embed_preview}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


class BirthdayAnnouncementFormatSelect(discord.ui.Select):
    def __init__(self, setup_view: BirthdayWishSetupView):
        self.setup_view = setup_view
        choices = [
            ("both", "Both message and embed", "Celebratory message + birthday embed card", "✨"),
            ("embed", "Embed only", "Ping + birthday card embed", "🖼️"),
            ("message", "Normal message only", "Plain text celebration without an embed", "💬"),
        ]
        options = [
            discord.SelectOption(
                label=label,
                value=value,
                description=description,
                emoji=emoji,
                default=value == setup_view.announcement_style,
            )
            for value, label, description, emoji in choices
        ]
        super().__init__(
            placeholder="Choose announcement format…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"birthday-announcement-format-{setup_view.user_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.setup_view
        view.announcement_style = self.values[0]
        await view.cog.upsert_user(
            view.user_id,
            view.guild_id,
            {"announcement_style": view.announcement_style},
        )
        refreshed = view.refreshed()
        await interaction.response.edit_message(embed=refreshed.summary_embed(), content=None, view=refreshed)


class BirthdayWishSetupSelect(discord.ui.Select):
    def __init__(self, setup_view: BirthdayWishSetupView):
        self.setup_view = setup_view
        options = [
            discord.SelectOption(
                label="Default embed card text",
                value="default",
                description="Use Nexora's standard birthday-card wording",
                emoji="🎂",
                default=setup_view.message_style == "default",
            )
        ]
        for key, emoji in [
            ("sweet", "💛"),
            ("funny", "😂"),
            ("heartfelt", "💖"),
            ("friendly", "🥳"),
            ("playful", "🎉"),
            ("short", "🎈"),
        ]:
            label, message = BIRTHDAY_WISH_PRESETS[key]
            options.append(
                discord.SelectOption(
                    label=label,
                    value=key,
                    description=message[:100],
                    emoji=emoji,
                    default=setup_view.message_style == key,
                )
            )
        options.append(
            discord.SelectOption(
                label="Write my own",
                value="custom",
                description="Enter a custom birthday message",
                emoji="✍️",
                default=setup_view.message_style == "custom",
            )
        )
        super().__init__(
            placeholder="Choose embed card text style…",
            min_values=1,
            max_values=1,
            options=options,
            custom_id=f"birthday-announcement-text-{setup_view.user_id}",
        )

    async def callback(self, interaction: discord.Interaction):
        view = self.setup_view
        choice = self.values[0]
        if choice == "custom":
            await interaction.response.send_modal(
                BirthdayWishSetupModal(
                    view.cog,
                    view.user_id,
                    view.guild_id,
                    view.user_mention,
                    view.display_name,
                )
            )
            return

        custom_wish = BIRTHDAY_WISH_PRESETS[choice][1] if choice in BIRTHDAY_WISH_PRESETS else None
        await view.cog.upsert_user(
            view.user_id,
            view.guild_id,
            {"custom_wish": custom_wish},
        )
        view.custom_wish = custom_wish
        view.message_style = choice
        refreshed = view.refreshed()
        await interaction.response.edit_message(embed=refreshed.summary_embed(), content=None, view=refreshed)


class BirthdayWishSetupModal(discord.ui.Modal, title="Custom Birthday Card Text"):
    message = discord.ui.TextInput(
        label="Your embed card text",
        placeholder="Use {mention}, {name}, {age}, or {server}",
        style=discord.TextStyle.paragraph,
        min_length=2,
        max_length=500,
        required=True,
    )

    def __init__(self, cog, user_id: int, guild_id: int, user_mention: str, display_name: str):
        super().__init__(timeout=300)
        self.cog = cog
        self.user_id = user_id
        self.guild_id = guild_id
        self.user_mention = user_mention
        self.display_name = display_name

    async def on_submit(self, interaction: discord.Interaction):
        raw_message = str(self.message.value).strip()
        guild_name = interaction.guild.name if interaction.guild else "Server"
        preview = safe_format_birthday_text(
            raw_message,
            mention=self.user_mention,
            name=self.display_name,
            server=guild_name,
        )
        await self.cog.upsert_user(
            self.user_id,
            self.guild_id,
            {"custom_wish": raw_message},
        )
        await interaction.response.send_message(
            f"✅ **Custom birthday card text saved!**\n\n**Preview:**\n{preview}",
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


# ── Admin Interactive Server Setup Dashboard ───────────────────────────────────

class ServerBirthdayMessageModal(discord.ui.Modal, title="⚙️ Server Default Birthday Message"):
    server_msg = discord.ui.TextInput(
        label="Default Message (Outside Embed)",
        placeholder="Placeholders: {mention}, {name}, {age}, {server}",
        style=discord.TextStyle.paragraph,
        max_length=1000,
        required=False,
    )
    server_emb = discord.ui.TextInput(
        label="Default Embed Description",
        placeholder="Placeholders: {mention}, {name}, {age}, {server}",
        style=discord.TextStyle.paragraph,
        max_length=1500,
        required=False,
    )

    def __init__(self, setup_view: "ServerBirthdaySetupView"):
        super().__init__(timeout=300)
        self.setup_view = setup_view
        self.server_msg.default = setup_view.settings.get("server_message") or DEFAULT_BIRTHDAY_MESSAGE_TEXT
        self.server_emb.default = setup_view.settings.get("server_embed_text") or DEFAULT_BIRTHDAY_EMBED_TEXT

    async def on_submit(self, interaction: discord.Interaction):
        msg_val = self.server_msg.value.strip() or None
        emb_val = self.server_emb.value.strip() or None
        await self.setup_view.cog.upsert_settings(
            self.setup_view.guild.id,
            {"server_message": msg_val, "server_embed_text": emb_val},
        )
        self.setup_view.settings["server_message"] = msg_val
        self.setup_view.settings["server_embed_text"] = emb_val
        await interaction.response.edit_message(
            embed=self.setup_view.build_embed(),
            view=self.setup_view,
        )


class ServerBirthdaySetupView(discord.ui.View):
    """
    User-friendly interactive Server Birthday Configuration Dashboard for Admins.
    Allows configuring Announce Channel, Intro Channel, Birthday Role, Ping Role,
    Server Midnight UTC Timezone, Default Message/Embed, and Testing live announcements!
    """

    def __init__(self, cog, guild: discord.Guild, requester_id: int, settings: dict, timeout=300):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild = guild
        self.requester_id = requester_id
        self.settings = dict(settings or {})
        self._populate_controls()

    def _get_guild_text_options(self, current_id: Optional[int]) -> list[discord.SelectOption]:
        options = [
            discord.SelectOption(
                label="None / Disabled",
                value="none",
                description="Clear this channel setting",
                emoji="🚫",
                default=(current_id is None),
            )
        ]
        channels = [
            ch for ch in self.guild.channels
            if isinstance(ch, discord.TextChannel) and ch.permissions_for(self.guild.me).send_messages
        ]
        channels.sort(key=lambda c: c.position)
        for ch in channels[:24]:
            options.append(
                discord.SelectOption(
                    label=f"#{ch.name}"[:100],
                    value=str(ch.id),
                    description=(ch.category.name if ch.category else f"ID: {ch.id}")[:100],
                    emoji="📢" if "announc" in ch.name.lower() or "bday" in ch.name.lower() or "birth" in ch.name.lower() else "💬",
                    default=(current_id == ch.id),
                )
            )
        return options

    def _populate_controls(self):
        self.clear_items()
        ann_cid = self.settings.get("announce_channel_id")
        intro_cid = self.settings.get("intro_channel_id")
        cur_offset = str(int(self.settings.get("utc_offset_minutes", 0) or 0))

        # Row 0: Announcement Channel (Server-Scoped)
        ann_select = discord.ui.Select(
            placeholder="📢 Select Birthday Announcement Channel…",
            options=self._get_guild_text_options(ann_cid),
            row=0,
        )

        async def on_ann_select(interaction: discord.Interaction):
            val = ann_select.values[0]
            cid = None if val == "none" else int(val)
            self.settings["announce_channel_id"] = cid
            await self.cog.upsert_settings(self.guild.id, {"announce_channel_id": cid})
            self._populate_controls()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

        ann_select.callback = on_ann_select
        self.add_item(ann_select)

        # Row 1: Intro Channel (Server-Scoped)
        intro_select = discord.ui.Select(
            placeholder="📥 Select Intro Auto-Scan Channel (Optional)…",
            options=self._get_guild_text_options(intro_cid),
            row=1,
        )

        async def on_intro_select(interaction: discord.Interaction):
            val = intro_select.values[0]
            cid = None if val == "none" else int(val)
            self.settings["intro_channel_id"] = cid
            await self.cog.upsert_settings(self.guild.id, {"intro_channel_id": cid})
            self._populate_controls()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

        intro_select.callback = on_intro_select
        self.add_item(intro_select)

        # Row 2: Role Selector (Birthday Role & Ping Role)
        roles = [
            r for r in self.guild.roles
            if not r.is_default() and not r.managed
        ]
        roles.sort(key=lambda r: r.position, reverse=True)
        role_options = [
            discord.SelectOption(
                label="Clear Roles (No Birthday/Ping Role)",
                value="clear",
                description="Remove configured birthday & ping roles",
                emoji="🚫",
            )
        ]
        for r in roles[:12]:
            role_options.append(
                discord.SelectOption(
                    label=f"🎂 Birthday Role: @{r.name}"[:100],
                    value=f"bday:{r.id}",
                    description="Grant this role for 24h on their birthday",
                    emoji="🎭",
                )
            )
            role_options.append(
                discord.SelectOption(
                    label=f"🔔 Ping Role: @{r.name}"[:100],
                    value=f"ping:{r.id}",
                    description="Mention this role in birthday announcements",
                    emoji="🔔",
                )
            )

        role_select = discord.ui.Select(
            placeholder="🎭 Configure Birthday Role or 🔔 Ping Role…",
            options=role_options[:25],
            row=2,
        )

        async def on_role_select(interaction: discord.Interaction):
            val = role_select.values[0]
            if val == "clear":
                self.settings["announce_role_id"] = None
                self.settings["ping_role_id"] = None
                await self.cog.upsert_settings(
                    self.guild.id, {"announce_role_id": None, "ping_role_id": None}
                )
            elif val.startswith("bday:"):
                rid = int(val.split(":")[1])
                self.settings["announce_role_id"] = rid
                await self.cog.upsert_settings(self.guild.id, {"announce_role_id": rid})
            elif val.startswith("ping:"):
                rid = int(val.split(":")[1])
                self.settings["ping_role_id"] = rid
                await self.cog.upsert_settings(self.guild.id, {"ping_role_id": rid})
            self._populate_controls()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

        role_select.callback = on_role_select
        self.add_item(role_select)

        # Row 3: Server UTC Timezone (00:00 Midnight Trigger)
        tz_options = []
        for mins_str, label, emoji in SERVER_TIMEZONE_OPTIONS:
            tz_options.append(
                discord.SelectOption(
                    label=label,
                    value=mins_str,
                    description="Send birthday wishes at 00:00 Midnight in this timezone",
                    emoji=emoji,
                    default=(mins_str == cur_offset),
                )
            )
        tz_select = discord.ui.Select(
            placeholder="🌍 Select Server 00:00 Midnight UTC Timezone…",
            options=tz_options,
            row=3,
        )

        async def on_tz_select(interaction: discord.Interaction):
            mins = int(tz_select.values[0])
            self.settings["utc_offset_minutes"] = mins
            await self.cog.upsert_settings(self.guild.id, {"utc_offset_minutes": mins})
            self._populate_controls()
            await interaction.response.edit_message(embed=self.build_embed(), view=self)

        tz_select.callback = on_tz_select
        self.add_item(tz_select)

        # Row 4: Action Buttons (Customize Default Text, Send Test Announcement, Scan Intros)
        btn_text = discord.ui.Button(
            label="Customize Default Message",
            emoji="📝",
            style=discord.ButtonStyle.primary,
            row=4,
        )

        async def on_text_click(interaction: discord.Interaction):
            await interaction.response.send_modal(ServerBirthdayMessageModal(self))

        btn_text.callback = on_text_click
        self.add_item(btn_text)

        btn_test = discord.ui.Button(
            label="Send Test Announcement",
            emoji="🧪",
            style=discord.ButtonStyle.success,
            row=4,
        )

        async def on_test_click(interaction: discord.Interaction):
            ann_id = self.settings.get("announce_channel_id")
            target_ch = self.guild.get_channel(int(ann_id)) if ann_id else interaction.channel
            if not target_ch:
                target_ch = interaction.channel

            ping_role_id = self.settings.get("ping_role_id")
            ping_role = self.guild.get_role(int(ping_role_id)) if ping_role_id else None
            offset = int(self.settings.get("utc_offset_minutes", 0) or 0)
            now = get_server_now(offset)
            user_doc = await self.cog.get_user(interaction.user.id, self.guild.id) or {
                "month": now.month,
                "day": now.day,
                "year": 2004,
            }
            content, embed, allowed_mentions = build_birthday_announcement_payload(
                member=interaction.user,
                guild=self.guild,
                doc=user_doc,
                settings=self.settings,
                now=now,
                is_prem=await self.cog.is_premium(self.guild.id),
                ping_role=ping_role,
            )
            try:
                await target_ch.send(
                    content=content,
                    embed=embed,
                    view=BirthdayAnnouncementView(self.cog, uid=interaction.user.id, guild_id=self.guild.id),
                    allowed_mentions=allowed_mentions,
                )
                await interaction.response.send_message(
                    f"✅ **Test birthday announcement sent to {target_ch.mention}!**",
                    ephemeral=True,
                )
            except discord.HTTPException as e:
                await interaction.response.send_message(
                    f"❌ Failed to send test announcement to {target_ch.mention}: `{e}`",
                    ephemeral=True,
                )

        btn_test.callback = on_test_click
        self.add_item(btn_test)

    def build_embed(self) -> discord.Embed:
        ann_cid = self.settings.get("announce_channel_id")
        intro_cid = self.settings.get("intro_channel_id")
        bday_rid = self.settings.get("announce_role_id")
        ping_rid = self.settings.get("ping_role_id")
        offset = int(self.settings.get("utc_offset_minutes", 0) or 0)
        server_now = get_server_now(offset)

        embed = discord.Embed(
            title=f"⚙️ Server Birthday Studio — {self.guild.name}",
            description=(
                "Configure automatic **00:00 Midnight** birthday announcements, role rewards, "
                "mentions, and `#introductions` auto-detection using the menus below."
            ),
            color=BRAND_COLOR,
            timestamp=datetime.datetime.now(datetime.timezone.utc),
        )
        embed.add_field(
            name="📢 Announcement Channel",
            value=f"<#{ann_cid}>" if ann_cid else "⚠️ *Not Set (Select below)*",
            inline=True,
        )
        embed.add_field(
            name="📥 Intro Auto-Scan Channel",
            value=f"<#{intro_cid}>" if intro_cid else "*Optional (Not Set)*",
            inline=True,
        )
        embed.add_field(
            name="🕛 Midnight Schedule",
            value=f"**00:00 ({format_utc_offset(offset)})**\n-# Server time now: `{server_now.strftime('%H:%M')}`",
            inline=True,
        )
        embed.add_field(
            name="🎭 24h Birthday Role",
            value=f"<@&{bday_rid}>" if bday_rid else "*None*",
            inline=True,
        )
        embed.add_field(
            name="🔔 Announcement Ping Role",
            value=f"<@&{ping_rid}> + `@BirthdayMember`" if ping_rid else "`@BirthdayMember` only",
            inline=True,
        )
        embed.add_field(
            name="📝 Custom Server Template",
            value="✅ Configured" if (self.settings.get("server_message") or self.settings.get("server_embed_text")) else "Default Celebratory Theme",
            inline=True,
        )
        embed.set_footer(text="Changes save automatically • Click 'Send Test Announcement' to test!")
        return embed

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.requester_id or interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator:
            return True
        await interaction.response.send_message(
            "❌ You need the **Manage Server** permission to configure server birthday settings.",
            ephemeral=True,
        )
        return False


class BirthdayUserDashboardView(discord.ui.View):
    """
    User-friendly action bar attached to /birthday, /setbirthday, and /myprofile.
    Lets members set/edit their birthday in 1 click, customize their post, or (for admins) open Server Setup!
    """

    def __init__(self, cog, user: discord.Member, guild: discord.Guild, is_today_bday: bool = False, target_uid: Optional[int] = None, timeout=240):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.user = user
        self.guild = guild
        self.target_uid = target_uid or user.id

        # If today is the target user's birthday, include the Send Birthday Wish button right at the top!
        if is_today_bday:
            wish_view = BirthdayAnnouncementView(cog, uid=self.target_uid, guild_id=guild.id)
            for item in wish_view.children:
                item.row = 0
                self.add_item(item)

        row_idx = 1 if is_today_bday else 0

        btn_set = discord.ui.Button(
            label="Set / Edit My Birthday",
            emoji="🎂",
            style=discord.ButtonStyle.primary,
            row=row_idx,
        )
        btn_set.callback = self._on_set_bday
        self.add_item(btn_set)

        btn_custom = discord.ui.Button(
            label="Customize My Post",
            emoji="✨",
            style=discord.ButtonStyle.secondary,
            row=row_idx,
        )
        btn_custom.callback = self._on_customize_post
        self.add_item(btn_custom)

        if user.guild_permissions.manage_guild or user.guild_permissions.administrator:
            btn_admin = discord.ui.Button(
                label="Server Setup",
                emoji="⚙️",
                style=discord.ButtonStyle.secondary,
                row=row_idx,
            )
            btn_admin.callback = self._on_server_setup
            self.add_item(btn_admin)

    async def _on_set_bday(self, interaction: discord.Interaction):
        existing = await self.cog.get_user(interaction.user.id, interaction.guild.id)
        await interaction.response.send_modal(QuickSetBirthdayModal(self.cog, existing=existing))

    async def _on_customize_post(self, interaction: discord.Interaction):
        profile = await self.cog.get_user(interaction.user.id, interaction.guild.id) or {}
        view = BirthdayWishSetupView(
            self.cog,
            interaction.user.id,
            interaction.guild.id,
            interaction.user.mention,
            interaction.user.display_name,
            announcement_style=profile.get("announcement_style", "both"),
            custom_wish=profile.get("custom_wish"),
            custom_message=profile.get("custom_message"),
            dm_notifications=profile.get("dm_notifications", True),
        )
        await interaction.response.send_message(
            embed=view.summary_embed(),
            view=view,
            ephemeral=True,
        )

    async def _on_server_setup(self, interaction: discord.Interaction):
        if not (interaction.user.guild_permissions.manage_guild or interaction.user.guild_permissions.administrator):
            return await interaction.response.send_message(
                "❌ You need the **Manage Server** permission to open Server Setup.",
                ephemeral=True,
            )
        settings = await self.cog.get_settings(interaction.guild.id)
        setup_view = ServerBirthdaySetupView(
            self.cog, interaction.guild, interaction.user.id, settings
        )
        await interaction.response.send_message(
            embed=setup_view.build_embed(),
            view=setup_view,
            ephemeral=True,
        )


class HelpView(discord.ui.View):
    def __init__(self, pages: dict, selected="home", timeout=180):
        super().__init__(timeout=timeout)
        self.pages = pages
        self.selected = selected
        self.select = discord.ui.Select(
            placeholder="Select a category from the menu below",
            custom_id="birthday-help-category",
            options=[
                discord.SelectOption(label="Home", value="home", emoji="🏠", description="Overview of the birthday system", default=(selected == "home")),
                discord.SelectOption(label="Free Commands", value="free", emoji="🆓", description="Available to everyone", default=(selected == "free")),
                discord.SelectOption(label="Premium Commands", value="premium", emoji=str(CROWN), description="Requires premium", default=(selected == "premium")),
                discord.SelectOption(label="Admin Setup", value="setup", emoji=str(GEAR), description="One-time server configuration", default=(selected == "setup")),
            ],
        )
        self.select.callback = self._select_callback
        self.add_item(self.select)

    async def _select_callback(self, interaction: discord.Interaction):
        value = self.select.values[0]
        new_view = HelpView(self.pages, selected=value, timeout=self.timeout)
        await interaction.response.edit_message(embed=self.pages[value], view=new_view)


# ── Cog ────────────────────────────────────────────────────────────────────────

class BirthdayIntro(commands.Cog):
    """Birthday system — 00:00 Midnight UTC/Server-Time Scheduler, Interactive Setup UI, O(1) Cached"""

    def __init__(self, bot):
        self.bot = bot
        self.col = None
        self.scol = None
        self.user_store_path = os.path.join("data", "birthday_data.json")
        self.settings_store_path = os.path.join("data", "birthday_settings.json")
        self.birthday_sent_path = os.path.join("data", "birthday_sent.json")
        self._startup_birthday_check_started = False
        self._birthday_check_lock = asyncio.Lock()

        # In-memory O(1) caches to eliminate per-message MongoDB & disk bottlenecks
        self._settings_cache: Dict[int, dict] = {}
        self._user_store_cache: Optional[dict] = None
        self._settings_store_cache: Optional[dict] = None
        self._wishers_by_day: Dict[str, Set[int]] = {}

    def get_wishers_set(self, guild_id: int, uid: int) -> Set[int]:
        today_str = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
        key = f"{today_str}:{guild_id}:{uid}"
        if key not in self._wishers_by_day:
            self._wishers_by_day[key] = set()
        return self._wishers_by_day[key]

    async def cog_load(self):
        mongo = getattr(self.bot, "mongo_db", None)
        if mongo is not None:
            self.col = mongo["birthday"]
            self.scol = mongo["birthday_settings"]
            # Pre-warm guild settings cache from MongoDB so on_message never blocks
            try:
                async for sdoc in self.scol.find({}):
                    if "_id" in sdoc:
                        self._settings_cache[int(sdoc["_id"])] = sdoc
            except Exception as e:
                logger.debug("Could not pre-warm birthday settings cache: %s", e)
        else:
            logger.warning("%s: mongo_db unavailable, using cached local JSON", self.__class__.__name__)
            raw = self._load_store(self.settings_store_path)
            for k, v in raw.items():
                if str(k).isdigit() and isinstance(v, dict):
                    self._settings_cache[int(k)] = v

        if self.bot.is_ready():
            self._ensure_daily_check_running()
            self._start_startup_birthday_check()
        logger.info("%s ready (00:00 Midnight scheduler active)", self.__class__.__name__)

    async def cog_unload(self):
        if self.daily_check.is_running():
            self.daily_check.cancel()
        if self.timezone_check.is_running():
            self.timezone_check.cancel()

    # ── Persistent Interaction Listener for 24/7 Wish Buttons ──────────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        if interaction.type != discord.InteractionType.component or not interaction.data:
            return
        custom_id = interaction.data.get("custom_id", "")
        if not custom_id.startswith("bday:"):
            return

        # If already handled by an active attached view, skip
        if interaction.response.is_done():
            return

        parts = custom_id.split(":")
        if len(parts) < 4:
            return
        action = parts[1]
        try:
            guild_id = int(parts[2])
            uid = int(parts[3])
        except ValueError:
            return

        view = BirthdayAnnouncementView(self, uid=uid, guild_id=guild_id)
        if action == "wish":
            await view._on_wish_click(interaction)
        elif action == "wishers":
            await view._on_wishers_click(interaction)

    # ── Storage helpers (O(1) Memory Cached) ───────────────────────────────────

    async def is_premium(self, guild_id: int) -> bool:
        result = self.bot.is_premium_guild(guild_id)
        if inspect.isawaitable(result):
            result = await result
        return bool(result)

    def _user_key(self, uid: int, guild_id: int) -> str:
        return f"{guild_id}:{uid}"

    async def get_user(self, uid: int, guild_id: int):
        key = self._user_key(uid, guild_id)
        if self.col is not None:
            doc = await self.col.find_one({"_id": key})
            if doc is not None:
                return doc
            return await self.col.find_one({"_id": uid, "guild_id": guild_id})
        data = self._load_store(self.user_store_path)
        scoped = data.get(key)
        if scoped is not None:
            return scoped
        legacy = data.get(str(uid))
        return legacy if legacy and legacy.get("guild_id") == guild_id else None

    async def get_settings(self, gid: int) -> dict:
        gid = int(gid)
        if gid in self._settings_cache:
            return self._settings_cache[gid]
        if self.scol is not None:
            doc = (await self.scol.find_one({"_id": gid})) or {}
            self._settings_cache[gid] = doc
            return doc
        data = self._load_store(self.settings_store_path)
        doc = data.get(str(gid), {})
        self._settings_cache[gid] = doc
        return doc

    async def upsert_user(self, uid: int, guild_id: int, data: dict):
        key = self._user_key(uid, guild_id)
        payload = {**data, "_id": key, "user_id": uid, "guild_id": guild_id}
        if self.col is not None:
            await self.col.update_one({"_id": key}, {"$set": payload}, upsert=True)
            await self.col.delete_one({"_id": uid, "guild_id": guild_id})
            return
        store = self._load_store(self.user_store_path)
        existing = store.get(key, store.get(str(uid), {}))
        store[key] = {**existing, **payload}
        legacy = store.get(str(uid))
        if legacy and legacy.get("guild_id") == guild_id:
            del store[str(uid)]
        self._save_store(self.user_store_path, store)

    async def upsert_settings(self, gid: int, data: dict):
        gid = int(gid)
        existing_cached = self._settings_cache.get(gid, {})
        merged = {**existing_cached, **data, "_id": gid}
        self._settings_cache[gid] = merged
        if self.scol is not None:
            await self.scol.update_one({"_id": gid}, {"$set": data}, upsert=True)
            return
        store = self._load_store(self.settings_store_path)
        existing = store.get(str(gid), {})
        store[str(gid)] = {**existing, **data, "_id": gid}
        self._save_store(self.settings_store_path, store)

    def _ensure_daily_check_running(self):
        if not self.daily_check.is_running():
            self.daily_check.start()
        if not self.timezone_check.is_running():
            self.timezone_check.start()

    def _load_store(self, path: str) -> dict:
        if path == self.user_store_path and self._user_store_cache is not None:
            return self._user_store_cache
        if path == self.settings_store_path and self._settings_store_cache is not None:
            return self._settings_store_cache

        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return {}
        res = data if isinstance(data, dict) else {}
        if path == self.user_store_path:
            self._user_store_cache = res
        elif path == self.settings_store_path:
            self._settings_store_cache = res
        return res

    def _save_store(self, path: str, payload: dict):
        if path == self.user_store_path:
            self._user_store_cache = payload
        elif path == self.settings_store_path:
            self._settings_store_cache = payload
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2, ensure_ascii=False)

    def _save_birthday_sent_log(self, payload: dict):
        """Atomically persist active birthday announcement records."""
        os.makedirs(os.path.dirname(self.birthday_sent_path), exist_ok=True)
        temp_path = self.birthday_sent_path + ".tmp"
        try:
            with open(temp_path, "w", encoding="utf-8") as fp:
                json.dump(payload, fp, indent=2, ensure_ascii=False)
            os.replace(temp_path, self.birthday_sent_path)
        finally:
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    def _load_birthday_sent_log(self, ref_date: datetime.date) -> dict:
        """Load the send ledger, keeping entries within 2 days of ref_date to support all UTC timezones."""
        if not os.path.exists(self.birthday_sent_path):
            return {}
        try:
            with open(self.birthday_sent_path, "r", encoding="utf-8") as fp:
                loaded = json.load(fp)
        except (OSError, json.JSONDecodeError):
            return {}
        if not isinstance(loaded, dict):
            return {}

        valid_dates = {
            (ref_date - datetime.timedelta(days=1)).isoformat(),
            ref_date.isoformat(),
            (ref_date + datetime.timedelta(days=1)).isoformat(),
        }
        current = {
            str(key): entry
            for key, entry in loaded.items()
            if isinstance(entry, dict) and entry.get("date") in valid_dates
        }
        if len(loaded) != len(current):
            try:
                self._save_birthday_sent_log(current)
            except OSError:
                pass
        return current

    def _has_sent_birthday_today(
        self,
        sent_log: dict,
        guild_id: int,
        user_id: int,
        target_date: datetime.date,
        doc: Optional[dict] = None,
    ) -> bool:
        date_str = target_date.isoformat()
        entry = sent_log.get(f"{guild_id}:{user_id}")
        if isinstance(entry, dict) and entry.get("date") == date_str:
            return True
        if isinstance(doc, dict):
            by_guild = doc.get("sent_dates_by_guild")
            if isinstance(by_guild, dict) and by_guild.get(str(guild_id)) == date_str:
                return True
            if int(doc.get("guild_id") or 0) == int(guild_id) and doc.get("last_notified_date") == date_str:
                return True
        return False

    def _record_birthday_sent(
        self, sent_log: dict, guild_id: int, user_id: int, now: datetime.datetime
    ):
        key = f"{guild_id}:{user_id}"
        sent_log[key] = {
            "guild_id": int(guild_id),
            "user_id": int(user_id),
            "date": now.date().isoformat(),
            "sent_at": now.isoformat(),
        }
        try:
            self._save_birthday_sent_log(sent_log)
        except OSError:
            logger.exception(
                "Birthday was announced to user %s in guild %s, but the send ledger could not be saved",
                user_id, guild_id,
            )

    async def _mark_birthday_sent(
        self, sent_log: dict, guild_id: int, user_id: int, now: datetime.datetime
    ):
        """Record birthday sent in both local JSON ledger and MongoDB so container restarts never re-send."""
        self._record_birthday_sent(sent_log, guild_id, user_id, now)
        if self.col is not None:
            date_str = now.date().isoformat()
            try:
                await self.col.update_many(
                    {
                        "$or": [
                            {"_id": f"{guild_id}:{user_id}"},
                            {"_id": int(user_id), "guild_id": int(guild_id)},
                            {"user_id": int(user_id), "guild_id": int(guild_id)},
                        ]
                    },
                    {
                        "$set": {
                            "last_notified_date": date_str,
                            "last_notified_year": now.year,
                            f"sent_dates_by_guild.{guild_id}": date_str,
                        }
                    },
                )
            except Exception as exc:
                logger.debug("Could not persist birthday sent date to MongoDB: %s", exc)

    def _normalize_birthday_doc(self, doc: dict) -> Optional[dict]:
        if not isinstance(doc, dict):
            return None
        try:
            raw_id = doc.get("user_id", doc.get("_id"))
            if isinstance(raw_id, str) and ":" in raw_id:
                raw_id = raw_id.split(":")[-1]
            uid = int(raw_id)
            month = int(doc["month"])
            day = int(doc["day"])
        except (KeyError, TypeError, ValueError):
            return None
        try:
            datetime.date(2000, month, day)
        except ValueError:
            return None
        normalized = dict(doc)
        normalized["_id"] = uid
        normalized["month"] = month
        normalized["day"] = day
        return normalized

    async def iter_birthdays(self, guild_id: Optional[int] = None):
        if self.col is not None:
            query = {
                "month": {"$exists": True, "$ne": None},
                "day": {"$exists": True, "$ne": None},
            }
            if guild_id is not None:
                query["guild_id"] = guild_id
            async for doc in self.col.find(query):
                normalized = self._normalize_birthday_doc(doc)
                if normalized is not None:
                    yield normalized
            return

        data = self._load_store(self.user_store_path)
        for doc in data.values():
            normalized = self._normalize_birthday_doc(doc)
            if normalized is None:
                continue
            if guild_id is not None and doc.get("guild_id") != guild_id:
                continue
            yield normalized

    def parse_intro(self, text: str) -> dict:
        result = {}
        m = BIRTHDAY_RE.search(text)
        if m:
            p = try_parse_date(m.group(1), m.group(2), m.group(3))
            if p:
                result.update(
                    birthday_month=p[0],
                    birthday_day=p[1],
                    birthday_year=p[2],
                    ambiguous=p[3],
                    raw_d=int(m.group(1)),
                    raw_m=int(m.group(2)),
                )
        result["name"] = parse_name(text)
        result["age"] = parse_age(text)
        result["pronouns"] = parse_pronouns(text)
        return result

    # ── 00:00 Midnight UTC & Server-Timezone Announcements ─────────────────────

    @tasks.loop(time=datetime.time(hour=0, minute=0, tzinfo=datetime.timezone.utc))
    async def daily_check(self):
        """Fires at exactly 00:00 Midnight UTC."""
        await self._run_birthday_check()

    @tasks.loop(minutes=15)
    async def timezone_check(self):
        """Fires every 15 minutes so servers with custom UTC offsets get their birthday announcement at 00:00 local server time."""
        await self._run_birthday_check()

    def _start_startup_birthday_check(self):
        if self._startup_birthday_check_started:
            return
        self._startup_birthday_check_started = True
        asyncio.create_task(self._startup_birthday_check())

    async def _startup_birthday_check(self):
        await self.bot.wait_until_ready()
        try:
            await self._run_birthday_check()
            logger.info("Startup birthday check completed")
        except Exception:
            logger.exception("Startup birthday check failed")

    async def _run_birthday_check(self):
        async with self._birthday_check_lock:
            await self._process_birthdays()

    async def _process_birthdays(self):
        utc_now = datetime.datetime.now(datetime.timezone.utc)
        sent_log = self._load_birthday_sent_log(utc_now.date())
        seen_pairs: Set[Tuple[int, int]] = set()
        stats = {
            "profiles": 0,
            "due_today": 0,
            "already_sent_today": 0,
            "missing_guild": 0,
            "missing_member": 0,
            "missing_channel": 0,
            "announced": 0,
            "failed_send": 0,
        }

        async for doc in self.iter_birthdays():
            stats["profiles"] += 1
            guild_id = int(doc.get("guild_id") or 0)
            uid = int(doc["_id"])
            pair = (guild_id, uid)
            if pair in seen_pairs:
                continue
            seen_pairs.add(pair)

            settings = await self.get_settings(guild_id) if guild_id else {}
            offset_mins = int(settings.get("utc_offset_minutes", 0) or 0)
            server_now = get_server_now(offset_mins)

            if int(doc["month"]) != server_now.month or int(doc["day"]) != server_now.day:
                continue
            stats["due_today"] += 1

            if self._has_sent_birthday_today(
                sent_log, guild_id, uid, server_now.date(), doc=doc
            ):
                stats["already_sent_today"] += 1
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                stats["missing_guild"] += 1
                continue

            member = guild.get_member(doc["_id"])
            if member is None:
                try:
                    member = await guild.fetch_member(doc["_id"])
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    stats["missing_member"] += 1
                    continue

            channel_id = settings.get("announce_channel_id")
            if not channel_id:
                stats["missing_channel"] += 1
                continue

            try:
                channel_id = int(channel_id)
            except (TypeError, ValueError):
                stats["missing_channel"] += 1
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                    stats["missing_channel"] += 1
                    continue

            # Optional 24h birthday role
            role_id = settings.get("announce_role_id")
            try:
                role = guild.get_role(int(role_id)) if role_id else None
            except (TypeError, ValueError):
                role = None
            if role:
                try:
                    await member.add_roles(role, reason="Birthday Celebration")
                    asyncio.create_task(self._drop_role(member, role))
                except (discord.Forbidden, discord.HTTPException):
                    pass

            ping_role_id = settings.get("ping_role_id")
            try:
                ping_role = guild.get_role(int(ping_role_id)) if ping_role_id else None
            except (TypeError, ValueError):
                ping_role = None

            is_prem = await self.is_premium(guild.id)
            message_content, message_embed, allowed_mentions = build_birthday_announcement_payload(
                member=member,
                guild=guild,
                doc=doc,
                settings=settings,
                now=server_now,
                is_prem=is_prem,
                ping_role=ping_role,
            )

            try:
                await channel.send(
                    content=message_content,
                    embed=message_embed,
                    view=BirthdayAnnouncementView(self, uid=doc["_id"], guild_id=guild.id),
                    allowed_mentions=allowed_mentions,
                )
            except discord.HTTPException as exc:
                stats["failed_send"] += 1
                logger.warning(
                    "Birthday announcement failed for user %s in guild %s, channel %s: %s",
                    doc["_id"], guild.id, channel_id, exc,
                )
                continue

            await self._mark_birthday_sent(sent_log, guild.id, doc["_id"], server_now)
            stats["announced"] += 1

            # Cross-server mutual broadcast (Premium)
            if doc.get("scope") == "mutual" and is_prem:
                for other_guild in self.bot.guilds:
                    if other_guild.id == guild.id:
                        continue
                    other_member = other_guild.get_member(doc["_id"])
                    if other_member is None:
                        try:
                            other_member = await other_guild.fetch_member(doc["_id"])
                        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                            continue
                    other_settings = await self.get_settings(other_guild.id)
                    other_offset = int(other_settings.get("utc_offset_minutes", 0) or 0)
                    other_now = get_server_now(other_offset)
                    if self._has_sent_birthday_today(
                        sent_log, other_guild.id, doc["_id"], other_now.date(), doc=doc
                    ):
                        continue
                    other_channel_id = other_settings.get("announce_channel_id")
                    if not other_channel_id:
                        continue
                    try:
                        other_channel_id = int(other_channel_id)
                        other_channel = other_guild.get_channel(other_channel_id) or await self.bot.fetch_channel(other_channel_id)
                        other_ping_role_id = other_settings.get("ping_role_id")
                        other_ping_role = other_guild.get_role(int(other_ping_role_id)) if other_ping_role_id else None

                        c_content, c_embed, c_mentions = build_birthday_announcement_payload(
                            member=other_member,
                            guild=other_guild,
                            doc=doc,
                            settings=other_settings,
                            now=other_now,
                            is_prem=True,
                            ping_role=other_ping_role,
                        )
                        await other_channel.send(
                            content=c_content,
                            embed=c_embed,
                            view=BirthdayAnnouncementView(self, uid=doc["_id"], guild_id=other_guild.id),
                            allowed_mentions=c_mentions,
                        )
                        await self._mark_birthday_sent(sent_log, other_guild.id, doc["_id"], other_now)
                    except Exception as exc:
                        logger.warning(
                            "Cross-server birthday announcement failed for user %s in guild %s: %s",
                            doc["_id"], other_guild.id, exc,
                        )

        if stats["announced"] > 0 or stats["failed_send"] > 0:
            logger.info(
                "Birthday check summary: scanned=%(profiles)s, due_today=%(due_today)s, "
                "already_sent_today=%(already_sent_today)s, announced=%(announced)s",
                stats,
            )

    @daily_check.before_loop
    async def _before(self):
        await self.bot.wait_until_ready()

    @timezone_check.before_loop
    async def _before_tz(self):
        await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        self._ensure_daily_check_running()
        self._start_startup_birthday_check()

    async def _drop_role(self, member, role, delay=86400):
        await asyncio.sleep(delay)
        try:
            await member.remove_roles(role, reason="Birthday expired")
        except Exception:
            pass

    # ── Fast O(1) Cached Intro Listener ────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot or not msg.guild:
            return
        # Fast O(1) memory check: only fetch from DB if not cached yet
        s = self._settings_cache.get(msg.guild.id)
        if s is None:
            s = await self.get_settings(msg.guild.id)
        intro_cid = s.get("intro_channel_id")
        if not intro_cid or msg.channel.id != int(intro_cid):
            return

        p = self.parse_intro(msg.content)
        if not any([p.get("birthday_month"), p.get("name"), p.get("age"), p.get("pronouns")]):
            return

        uid = msg.author.id
        was_ambiguous = False

        if p.get("ambiguous") and p.get("birthday_month"):
            was_ambiguous = True
            rd, rm, ry = p["raw_d"], p["raw_m"], p.get("birthday_year")
            opt_a, opt_b = (rm, rd, ry), (rd, rm, ry)
            view = AmbiguousDateView(user_id=uid, opt_a=opt_a, opt_b=opt_b)
            amb_embed = base_embed(
                title=f"{PENCIL} Which date is your birthday?",
                description=f"`{opt_a[1]}/{opt_a[0]}` could be read two ways — tap the correct one below!",
                color=WARN_COLOR,
            )
            try:
                dm = await send_ui(msg.author, embed=amb_embed, view=view)
                await view.wait()
                chosen = opt_b if view.chosen == "b" else opt_a
                p["birthday_month"], p["birthday_day"] = chosen[0], chosen[1]
                was_ambiguous = view.chosen is None
                if dm:
                    await dm.delete()
            except discord.Forbidden:
                pass

        existing = await self.get_user(uid, msg.guild.id) or {}
        update = {
            "guild_id": msg.guild.id,
            "month": p.get("birthday_month") or existing.get("month"),
            "day": p.get("birthday_day") or existing.get("day"),
            "year": p.get("birthday_year") or existing.get("year"),
            "name": p.get("name") or existing.get("name"),
            "age": p.get("age") or existing.get("age"),
            "pronouns": p.get("pronouns") or existing.get("pronouns"),
            "last_notified_year": existing.get("last_notified_year"),
            "source": "intro",
            "custom_wish": existing.get("custom_wish"),
            "custom_message": existing.get("custom_message"),
            "announcement_style": existing.get("announcement_style", "both"),
            "scope": existing.get("scope", "server"),
            "dm_notifications": existing.get("dm_notifications", True),
        }
        await self.upsert_user(uid, msg.guild.id, update)
        try:
            await msg.add_reaction(CAKE)
        except discord.Forbidden:
            pass

        lines = []
        if update.get("name"):
            lines.append(f"👤 **Name:** {update['name']}")
        if update.get("month"):
            bd = f"{month_name(update['month'])} {update['day']}"
            if update.get("year"):
                bd += f", {update['year']}"
            if was_ambiguous:
                bd += "  *(guessed — please confirm)*"
            lines.append(f"{CAKE} **Birthday:** {bd}")
        if update.get("age"):
            lines.append(f"🔢 **Age:** {update['age']}")
        if update.get("pronouns"):
            lines.append(f"🏳️‍🌈 **Pronouns:** {update['pronouns']}")

        if lines:
            note = (
                f"\n\nAnything wrong? You can fix or customize it anytime in **{msg.guild.name}** using `/birthday`!"
            )
            try:
                intro_embed = base_embed(
                    title=f"{WAVE} Here's what I picked up from your intro!",
                    description="\n".join(lines) + note,
                    color=FREE_COLOR,
                )
                intro_embed.set_footer(text="Your birthday will be announced automatically at 00:00 Midnight 🎉")
                await send_ui(msg.author, embed=intro_embed)
            except discord.Forbidden:
                pass

    # ══════════════════════════════════════════════════════════════════════════
    # HELP MENU
    # ══════════════════════════════════════════════════════════════════════════

    def _build_help_pages(self, ctx: commands.Context) -> dict:
        home = base_embed(
            title=f"{CAKE} Nexora Birthday Studio",
            description=(
                "Celebrate every member automatically at **00:00 Midnight** in your server's timezone!\n\n"
                f"🎂 **Quick Interactive Setup:** Run `/birthday` to open buttons for **Set/Edit Birthday**, **Customize My Post**, and **Server Setup**!\n"
                f"{INFO} **Free Commands:** Available to everyone\n"
                f"{CROWN} **Premium Commands:** Cross-server reach & 1,000-message scans\n"
                f"{GEAR} **Admin Setup:** Interactive Server Setup Studio\n"
            ),
            color=BRAND_COLOR,
            ctx=ctx,
        )

        free = base_embed(
            title="🆓 Free Commands",
            description=(
                "Available to every member, no premium required:\n\n"
                "`/setbirthday <date> [year]` — set your birthday (or use the interactive modal on `/birthday`)\n"
                "`/birthday [user]` — view birthday card + interactive setup & customization buttons\n"
                "`/birthdaylist [limit]` — see upcoming birthdays in this server\n"
                "`/editprofile [name] [age] [pronouns]` — update your profile details\n"
                "`/myprofile` — view everything saved about you + customize your post\n"
                "`n!birthdaywish [message]` — customize your announcement format, message & embed\n"
                "`n!birthdaynotify <true|false>` — choose whether wishes send you a DM\n"
                "`n!introbdsetup` *(admin)* — open the interactive Server Birthday Setup Studio"
            ),
            color=FREE_COLOR,
            ctx=ctx,
        )

        premium = base_embed(
            title=f"{CROWN} Premium Commands",
            description=(
                "For cross-server reach and high-volume administration:\n\n"
                "`n!birthdayscope <server|mutual>` — announce in this server only, "
                "or every mutual server\n"
                "`n!scanintros [limit]` *(admin, up to 1,000)* — bulk-import older intros\n\n"
                "Your birthday, profile, custom announcement text, and DM preference are 100% free."
            ),
            color=PREMIUM_COLOR,
            ctx=ctx,
        )

        setup = base_embed(
            title=f"{GEAR} Admin Setup",
            description=(
                "**Option 1 — Interactive Setup Dashboard (Recommended):**\n"
                "• Run `/birthday` and click **⚙️ Server Setup**, OR run `n!introbdsetup` with no arguments.\n"
                "• Pick your **Announcement Channel**, **Intro Channel**, **24h Birthday Role**, **Ping Role**, and **00:00 Midnight Timezone**, then click **🧪 Send Test Announcement**!\n\n"
                "**Option 2 — Quick Command Setup:**\n"
                "`n!introbdsetup #intros #birthdays [@BirthdayRole] [@PingRole]`"
            ),
            color=BRAND_COLOR,
            ctx=ctx,
        )

        return {"home": home, "free": free, "premium": premium, "setup": setup}

    @commands.command(name="birthdayhelp", aliases=["bdayhelp"])
    @commands.guild_only()
    async def birthdayhelp(self, ctx: commands.Context):
        """FREE — Interactive help menu for the birthday system."""
        pages = self._build_help_pages(ctx)
        view = HelpView(pages, selected="home")
        await send_ui(ctx, embed=pages["home"], view=view)

    # ══════════════════════════════════════════════════════════════════════════
    # FREE COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.hybrid_command(name="setbirthday", description="Set your birthday — accepts most date formats")
    @app_commands.describe(
        date="Your birthday, e.g. 15/04  |  04/15  |  15-04-2001  |  April 15",
        year="Birth year (optional, only if not included in date)",
    )
    @commands.guild_only()
    @commands.cooldown(1, 15, commands.BucketType.user)
    async def setbirthday(self, ctx: commands.Context, date: str, year: Optional[int] = None):
        """FREE — Set your birthday. Works as n!setbirthday or /setbirthday."""
        parsed = parse_flexible_date_input(date, year)
        if not parsed:
            return await send_ui(
                ctx,
                embed=error_embed(
                    "Couldn't understand that date format.\n\n"
                    "**Accepted formats:** `April 15` • `15 April` • `15/04` • `04/15` • `15-04-2001`",
                    ctx=ctx,
                ),
                ephemeral=True,
            )

        month, day, yr, ambiguous, numeric_match = parsed

        if ambiguous and numeric_match:
            d_val, m_val = int(numeric_match.group(1)), int(numeric_match.group(2))
            opt_a = (m_val, d_val, yr)  # DD/MM
            opt_b = (d_val, m_val, yr)  # MM/DD
            view = AmbiguousDateView(user_id=ctx.author.id, opt_a=opt_a, opt_b=opt_b)
            amb_embed = base_embed(
                title=f"{PENCIL} Which date is your birthday?",
                description=f"`{opt_a[1]}/{opt_a[0]}` could be read two ways — tap the correct one below!",
                color=WARN_COLOR,
                ctx=ctx,
            )
            await send_ui(ctx, embed=amb_embed, view=view, ephemeral=True)
            await view.wait()
            if view.chosen is None:
                return
            chosen = opt_b if view.chosen == "b" else opt_a
            month, day = chosen[0], chosen[1]

        existing = await self.get_user(ctx.author.id, ctx.guild.id) or {}
        await self.upsert_user(
            ctx.author.id,
            ctx.guild.id,
            {
                **{
                    k: existing.get(k)
                    for k in ("custom_wish", "custom_message", "announcement_style", "scope", "dm_notifications", "name", "age", "pronouns")
                    if k in existing
                },
                "month": month,
                "day": day,
                "year": yr,
            },
        )

        settings = await self.get_settings(ctx.guild.id)
        offset = int(settings.get("utc_offset_minutes", 0) or 0)
        d_left = days_until(month, day, offset)
        status = f"{PARTY} **That's TODAY!**" if d_left == 0 else f"Coming up in **{d_left}** days!"

        embed = success_embed(
            "Birthday Set!",
            f"**{month_name(month)} {ordinal(day)}**" + (f", {yr}" if yr else "") + f"\n{status}\n\n"
            f"✨ Your birthday will be announced at **00:00 Midnight ({format_utc_offset(offset)})**.\n"
            f"Use the buttons below to customize your birthday message & embed!",
            ctx=ctx,
        )
        embed.title = f"{CAKE} Birthday Set!"
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        dash_view = BirthdayUserDashboardView(
            self, ctx.author, ctx.guild, is_today_bday=(d_left == 0), target_uid=ctx.author.id
        )
        await send_ui(ctx, embed=embed, view=dash_view)

        if d_left == 0:
            asyncio.create_task(self._run_birthday_check())

    @commands.hybrid_command(name="birthday", description="View your or another user's birthday and open setup controls")
    @app_commands.describe(user="User to check (leave blank for yourself)")
    @commands.guild_only()
    async def birthday(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """FREE — Check birthday info + interactive setup buttons"""
        target = user or ctx.author
        data = await self.get_user(target.id, ctx.guild.id)
        settings = await self.get_settings(ctx.guild.id)
        offset = int(settings.get("utc_offset_minutes", 0) or 0)

        if not data or not data.get("month"):
            name = "You haven't" if target == ctx.author else f"{target.mention} hasn't"
            empty_embed = base_embed(
                title=f"{CAKE} Birthday Not Set Yet",
                description=(
                    f"{name} set a birthday in **{ctx.guild.name}** yet!\n\n"
                    f"Click **🎂 Set / Edit My Birthday** below (or use `/setbirthday`) to set it in seconds."
                ),
                color=BRAND_COLOR,
                ctx=ctx,
            )
            dash_view = BirthdayUserDashboardView(
                self, ctx.author, ctx.guild, is_today_bday=False, target_uid=target.id
            )
            return await send_ui(ctx, embed=empty_embed, view=dash_view)

        today = is_today(data["month"], data["day"], offset)
        d_left = days_until(data["month"], data["day"], offset)
        bd_str = f"{month_name(data['month'])} {ordinal(data['day'])}" + (f", {data['year']}" if data.get("year") else "")
        next_dt = next_birthday(data["month"], data["day"], offset)

        embed = base_embed(
            title=f"{CAKE + ' ' if today else '🎈 '}{target.display_name}'s Birthday",
            description=(
                f"{PARTY} **It's {target.mention}'s birthday TODAY!** Click below to send them a wish!"
                if today
                else f"Celebrated at **00:00 Midnight ({format_utc_offset(offset)})**"
            ),
            color=TODAY_COLOR if today else BRAND_COLOR,
            ctx=ctx,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name=f"{CALENDAR} Date", value=f"**{bd_str}**", inline=True)
        embed.add_field(
            name="⏳ Countdown",
            value=f"{PARTY} **TODAY!**" if today else f"**{d_left}** days ({discord.utils.format_dt(next_dt, 'R')})",
            inline=True,
        )
        if data.get("year"):
            now = get_server_now(offset)
            age = now.year - int(data["year"]) - ((now.month, now.day) < (int(data["month"]), int(data["day"])))
            if 0 < age < 120:
                embed.add_field(name=f"{CAKE} Age", value=f"**{age}**" + (" (Today!)" if today else ""), inline=True)
        embed.add_field(
            name="📆 Next Celebration",
            value=discord.utils.format_dt(next_dt, "D"),
            inline=True,
        )
        if data.get("pronouns"):
            embed.add_field(name="🏳️‍🌈 Pronouns", value=data["pronouns"], inline=True)

        dash_view = BirthdayUserDashboardView(
            self, ctx.author, ctx.guild, is_today_bday=today, target_uid=target.id
        )
        await send_ui(ctx, embed=embed, view=dash_view)

    @commands.hybrid_command(name="birthdaylist", description="View upcoming birthdays in this server")
    @app_commands.describe(limit="How many to show (max 25)")
    @commands.guild_only()
    async def birthdaylist(self, ctx: commands.Context, limit: int = 10):
        """FREE — List upcoming birthdays"""
        limit = 10 if limit is None else max(1, min(int(limit), 25))
        settings = await self.get_settings(ctx.guild.id)
        offset = int(settings.get("utc_offset_minutes", 0) or 0)
        upcoming = []

        async for doc in self.iter_birthdays(ctx.guild.id):
            if doc.get("month") is None or doc.get("day") is None:
                continue
            member = ctx.guild.get_member(int(doc["_id"]))
            if member is None:
                continue
            try:
                days = days_until(int(doc["month"]), int(doc["day"]), offset)
            except Exception as e:
                logger.error("Skipping invalid birthday document %s: %s", doc, e)
                continue
            upcoming.append((days, member, doc))

        upcoming.sort(key=lambda x: x[0])
        if not upcoming:
            dash_view = BirthdayUserDashboardView(self, ctx.author, ctx.guild)
            return await send_ui(
                ctx,
                embed=base_embed(
                    title="📭 No Birthdays Set Yet",
                    description="Click **🎂 Set / Edit My Birthday** below or use `/setbirthday` to be the first!",
                    color=BRAND_COLOR,
                    ctx=ctx,
                ),
                view=dash_view,
            )

        lines = []
        for idx, (d, member, doc) in enumerate(upcoming[:limit], start=1):
            display = doc.get("name") or member.display_name
            bd_str = f"{month_name(doc['month'])} {ordinal(doc['day'])}"
            badge = f"{CAKE} **TODAY!** {PARTY}" if d == 0 else f"in **{d}** days"
            lines.append(f"`{idx:02d}.` {'🎂' if d == 0 else '🎈'} {member.mention} (**{display}**) — **{bd_str}** • {badge}")

        embed = base_embed(
            title=f"{PARTY} Upcoming Birthdays — {ctx.guild.name}",
            description="\n".join(lines),
            color=BRAND_COLOR,
            ctx=ctx,
        )
        embed.set_footer(
            text=f"Showing {min(len(upcoming), limit)} of {len(upcoming)} • Announced at 00:00 ({format_utc_offset(offset)})"
        )
        await send_ui(ctx, embed=embed, allowed_mentions=discord.AllowedMentions.none())

    @commands.command(name="editbirthday")
    @commands.guild_only()
    async def editbirthday(self, ctx: commands.Context, month: int, day: int, year: Optional[int] = None):
        """FREE — Correct your birthday date."""
        if not (1 <= month <= 12):
            return await send_ui(ctx, embed=error_embed("Month must be between 1 and 12.", ctx=ctx), ephemeral=True)
        try:
            datetime.date(year or 2000, month, day)
        except ValueError:
            return await send_ui(ctx, embed=error_embed("That date doesn't exist.", ctx=ctx), ephemeral=True)
        await self.upsert_user(ctx.author.id, ctx.guild.id, {"month": month, "day": day, "year": year})
        settings = await self.get_settings(ctx.guild.id)
        offset = int(settings.get("utc_offset_minutes", 0) or 0)
        d_left = days_until(month, day, offset)
        await send_ui(
            ctx,
            embed=success_embed(
                "Birthday Updated!",
                f"**{month_name(month)} {ordinal(day)}{', ' + str(year) if year else ''}**\n"
                f"{'🎉 Today!' if d_left == 0 else f'In **{d_left}** days!'}",
                ctx=ctx,
            ),
            ephemeral=True,
        )
        if d_left == 0:
            asyncio.create_task(self._run_birthday_check())

    @commands.hybrid_command(name="editprofile", description="Fix your name, age, or pronouns")
    @app_commands.describe(name="Your display name", age="Your age", pronouns="Your pronouns (e.g. she/her)")
    @commands.guild_only()
    async def editprofile(self, ctx: commands.Context, name: Optional[str] = None, age: Optional[int] = None, pronouns: Optional[str] = None):
        """FREE — Update your intro profile fields."""
        if not any([name, age, pronouns]):
            return await send_ui(ctx, embed=error_embed("Provide at least one field to update.", ctx=ctx), ephemeral=True)
        update = {}
        lines = []
        if name:
            update["name"] = name.strip()
            lines.append(f"👤 Name → **{name}**")
        if age:
            update["age"] = age
            lines.append(f"🔢 Age → **{age}**")
        if pronouns:
            update["pronouns"] = pronouns.lower().strip()
            lines.append(f"🏳️‍🌈 Pronouns → **{pronouns}**")
        await self.upsert_user(ctx.author.id, ctx.guild.id, update)
        await send_ui(ctx, embed=success_embed("Profile Updated", "\n".join(lines), ctx=ctx), ephemeral=True)

    @commands.hybrid_command(name="myprofile", description="View your full birthday profile and customization options")
    @commands.guild_only()
    async def myprofile(self, ctx: commands.Context):
        """FREE — View everything the bot has stored for you."""
        data = await self.get_user(ctx.author.id, ctx.guild.id)
        settings = await self.get_settings(ctx.guild.id)
        offset = int(settings.get("utc_offset_minutes", 0) or 0)
        dash_view = BirthdayUserDashboardView(self, ctx.author, ctx.guild)

        if not data:
            return await send_ui(
                ctx,
                embed=error_embed(
                    "No profile found yet. Click **🎂 Set / Edit My Birthday** below or post in the intro channel!",
                    ctx=ctx,
                ),
                view=dash_view,
                ephemeral=True,
            )

        embed = base_embed(title=f"👤 {ctx.author.display_name}'s Birthday Profile", color=BRAND_COLOR, ctx=ctx)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        if data.get("name"):
            embed.add_field(name="👤 Name", value=data["name"], inline=True)
        if data.get("pronouns"):
            embed.add_field(name="🏳️‍🌈 Pronouns", value=data["pronouns"], inline=True)
        if data.get("age"):
            embed.add_field(name="🔢 Age", value=str(data["age"]), inline=True)
        if data.get("month") and data.get("day"):
            bd = f"{month_name(data['month'])} {ordinal(data['day'])}" + (f", {data['year']}" if data.get("year") else "")
            days_left = days_until(data["month"], data["day"], offset)
            status = f"{PARTY} **TODAY!**" if days_left == 0 else f"in **{days_left}** days"
            embed.add_field(name=f"{CAKE} Birthday", value=f"**{bd}** ({status})", inline=False)
        else:
            embed.add_field(name=f"{CAKE} Birthday", value="Not set — click **Set / Edit My Birthday** below", inline=False)

        style_map = {"both": "✨ Message + Embed", "embed": "🖼️ Embed Only", "message": "💬 Message Only"}
        embed.add_field(
            name="🎨 Post Style",
            value=style_map.get(data.get("announcement_style", "both"), "✨ Message + Embed"),
            inline=True,
        )
        premium_active = await self.is_premium(ctx.guild.id)
        scope_text = "All mutual servers" if data.get("scope") == "mutual" and premium_active else "This server only"
        embed.add_field(name="🌐 Scope", value=scope_text, inline=True)
        embed.add_field(
            name="📬 Wish DMs",
            value=f"{CHECK} On" if data.get("dm_notifications", True) else f"{CROSS} Off",
            inline=True,
        )
        if data.get("custom_wish"):
            embed.add_field(name=f"{SPARKLE} Custom Embed Text", value=data["custom_wish"][:300], inline=False)
        if data.get("custom_message"):
            embed.add_field(name="💬 Custom Message Text", value=data["custom_message"][:300], inline=False)
        embed.set_footer(text=f"Source: {data.get('source', 'manual')} • Use the buttons below to edit or customize")
        await send_ui(ctx, embed=embed, view=dash_view, ephemeral=True)

    @commands.command(name="introbdsetup", aliases=["bdaysetup", "birthdaysetup"])
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def introbdsetup(
        self,
        ctx: commands.Context,
        intro_channel: Optional[discord.TextChannel] = None,
        announce_channel: Optional[discord.TextChannel] = None,
        birthday_role: Optional[discord.Role] = None,
        ping_role: Optional[discord.Role] = None,
    ):
        """
        FREE (admin) — Open the interactive Server Birthday Setup Studio
        (or pass channels/roles directly).
        """
        if intro_channel is None and announce_channel is None:
            settings = await self.get_settings(ctx.guild.id)
            setup_view = ServerBirthdaySetupView(self, ctx.guild, ctx.author.id, settings)
            return await send_ui(ctx, embed=setup_view.build_embed(), view=setup_view)

        # If only one channel was passed, treat it as announce_channel unless both were given
        if intro_channel is not None and announce_channel is None:
            announce_channel = intro_channel
            intro_channel = None

        update_payload = {
            "announce_channel_id": announce_channel.id if announce_channel else None,
            "intro_channel_id": intro_channel.id if intro_channel else None,
            "announce_role_id": birthday_role.id if birthday_role else None,
            "ping_role_id": ping_role.id if ping_role else None,
        }
        await self.upsert_settings(ctx.guild.id, update_payload)
        settings = await self.get_settings(ctx.guild.id)
        setup_view = ServerBirthdaySetupView(self, ctx.guild, ctx.author.id, settings)
        await send_ui(ctx, embed=setup_view.build_embed(), view=setup_view)

    # ══════════════════════════════════════════════════════════════════════════
    # CUSTOMIZATION & PREMIUM COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.command(name="birthdaywish", aliases=["bdaywish"])
    @commands.guild_only()
    async def birthdaywish(self, ctx: commands.Context, *, message: Optional[str] = None):
        """FREE — Choose format and customize birthday announcement text."""
        if message is None or not message.strip():
            profile = await self.get_user(ctx.author.id, ctx.guild.id) or {}
            view = BirthdayWishSetupView(
                self,
                ctx.author.id,
                ctx.guild.id,
                ctx.author.mention,
                ctx.author.display_name,
                announcement_style=profile.get("announcement_style", "both"),
                custom_wish=profile.get("custom_wish"),
                custom_message=profile.get("custom_message"),
                dm_notifications=profile.get("dm_notifications", True),
            )
            await send_ui(ctx, embed=view.summary_embed(), view=view, ephemeral=True)
            return

        message = message.strip()
        if len(message) > 500:
            return await send_ui(ctx, embed=error_embed("Max 500 characters.", ctx=ctx), ephemeral=True)
        preview = safe_format_birthday_text(
            message,
            mention=ctx.author.mention,
            name=ctx.author.display_name,
            server=ctx.guild.name,
        )
        await self.upsert_user(ctx.author.id, ctx.guild.id, {"custom_wish": message})
        embed = success_embed("Custom Embed Text Saved!", f"**Embed preview:**\n{preview}", ctx=ctx)
        embed.title = f"{SPARKLE} Custom Embed Text Saved!"
        embed.set_footer(text="Run n!birthdaywish without text (or /birthday) to customize all announcement options")
        await send_ui(ctx, embed=embed, ephemeral=True)

    @commands.command(name="birthdayscope")
    @commands.guild_only()
    async def birthdayscope(self, ctx: commands.Context, scope: str):
        """PREMIUM — Control where your birthday announcement gets sent"""
        if not await self.is_premium(ctx.guild.id):
            return await send_ui(ctx, embed=premium_embed(), ephemeral=True)
        await self.upsert_user(ctx.author.id, ctx.guild.id, {"scope": scope})
        label = "all mutual servers" if scope == "mutual" else "this server only"
        embed = base_embed(
            title="🌐 Announcement Scope Updated",
            description=f"Your birthday will be announced in **{label}**.",
            color=PREMIUM_COLOR,
            ctx=ctx,
        )
        if scope == "mutual":
            embed.set_footer(text="Only servers that have an announce channel configured will receive it")
        await send_ui(ctx, embed=embed, ephemeral=True)

    @commands.command(name="birthdaynotify")
    @commands.guild_only()
    async def birthdaynotify(self, ctx: commands.Context, enabled: bool):
        """FREE — Control whether you get DMs when people wish you."""
        await self.upsert_user(ctx.author.id, ctx.guild.id, {"dm_notifications": enabled})
        embed = base_embed(
            title="📬 Notification Preference Updated",
            description=f"DM notifications are now **{'enabled ✅' if enabled else 'disabled ❌'}**.",
            color=FREE_COLOR,
            ctx=ctx,
        )
        await send_ui(ctx, embed=embed, ephemeral=True)

    @commands.command(name="scanintros")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def scanintros(self, ctx: commands.Context, limit: int = 100):
        """FREE — Import recent intro data; premium raises the scan limit."""
        s = await self.get_settings(ctx.guild.id)
        if not s.get("intro_channel_id"):
            return await send_ui(ctx, embed=error_embed("Configure an intro channel in `/birthday` ➔ **⚙️ Server Setup** first.", ctx=ctx))
        channel = ctx.guild.get_channel(int(s["intro_channel_id"]))
        if not channel:
            return await send_ui(ctx, embed=error_embed("Intro channel not found — please update it in **⚙️ Server Setup**.", ctx=ctx))
        await ctx.defer()
        scan_cap = 1000 if await self.is_premium(ctx.guild.id) else 100
        limit = max(10, min(limit, scan_cap))
        imported = 0
        skipped = 0
        async for msg in channel.history(limit=limit):
            if msg.author.bot:
                continue
            p = self.parse_intro(msg.content)
            if not any([p.get("birthday_month"), p.get("name"), p.get("age"), p.get("pronouns")]):
                skipped += 1
                continue
            ex = await self.get_user(msg.author.id, ctx.guild.id) or {}
            await self.upsert_user(
                msg.author.id,
                ctx.guild.id,
                {
                    "source": "scan",
                    "month": p.get("birthday_month") or ex.get("month"),
                    "day": p.get("birthday_day") or ex.get("day"),
                    "year": p.get("birthday_year") or ex.get("year"),
                    "name": p.get("name") or ex.get("name"),
                    "age": p.get("age") or ex.get("age"),
                    "pronouns": p.get("pronouns") or ex.get("pronouns"),
                },
            )
            imported += 1
        embed = base_embed(
            title=f"{PENCIL} Intro Scan Complete",
            description=f"{CHECK} Imported **{imported}** profiles.\n⏭️ Skipped **{skipped}** messages.",
            color=FREE_COLOR,
            ctx=ctx,
        )
        embed.set_footer(text=f"Scanned last {limit} messages in #{channel.name}")
        await send_ui(ctx, embed=embed)

    # ── Error handlers ─────────────────────────────────────────────────────────

    @setbirthday.error
    async def _setbirthday_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await send_ui(
                ctx,
                embed=base_embed(
                    title="⏳ Slow down",
                    description=f"Wait **{error.retry_after:.0f}s** before setting your birthday again.",
                    color=WARN_COLOR,
                    ctx=ctx,
                ),
                ephemeral=True,
            )

    @introbdsetup.error
    @scanintros.error
    async def _admin_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await send_ui(
                ctx,
                embed=error_embed("You need the **Manage Server** permission to do that.", ctx=ctx),
                ephemeral=True,
            )


async def setup(bot):
    await bot.add_cog(BirthdayIntro(bot))
    logger.debug("Loaded BirthdayIntro")

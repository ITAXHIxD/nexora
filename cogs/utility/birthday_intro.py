"""
cogs/utility/birthday_intro.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FREE:
  • Auto-parse birthday from #introductions
  • n!setbirthday  / /setbirthday   — multi-format, disambiguates on-the-spot
  • n!birthday     / /birthday
  • n!birthdaylist / /birthdaylist
  • n!editbirthday / /editbirthday  — fix a wrongly-parsed date
  • n!editprofile  / /editprofile   — fix name, age, pronouns
  • n!myprofile    / /myprofile     — view your full parsed profile
  • n!birthdayhelp / /birthdayhelp  — interactive command menu
  • n!introbdsetup (admin)          — one-time channel setup
  • Daily 9 AM announcement + optional birthday role
  • Personal announcement message, DM wish preference, and a 100-message intro scan

PREMIUM:
  • n!birthdayscope  / /birthdayscope  — server-only OR all mutual servers
  • Larger n!scanintros runs (up to 1,000 messages)

Design note: birthday setup, corrections, personal messages, and privacy
controls are free. Premium is reserved for cross-server reach and larger
administrative operations.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import datetime
import inspect
import json
import logging
import os
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

logger = logging.getLogger(__name__)

CAKE = "🎂"; PARTY = "🎉"; BALLOON = "🎈"; GIFT = "🎁"
STAR = "⭐"; WAVE = "👋"; PENCIL = "📝"; CROWN = "👑"; LOCK = "🔒"; SPARKLE = "✨"
CHECK = "✅"; CROSS = "❌"; INFO = "ℹ️"; GEAR = "⚙️"; CALENDAR = "📅"

# ── Brand palette (keep every embed in the cog visually consistent) ────────────
BRAND_COLOR   = discord.Color.from_rgb(88, 101, 242)    # primary / info
FREE_COLOR    = discord.Color.from_rgb(59, 165, 93)     # confirmations
PREMIUM_COLOR = discord.Color.from_rgb(255, 191, 71)    # gold — premium only
TODAY_COLOR   = discord.Color.from_rgb(255, 145, 60)    # birthday-today highlight
ERROR_COLOR   = discord.Color.from_rgb(237, 66, 69)
WARN_COLOR    = discord.Color.from_rgb(255, 172, 51)

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

# ── Parse helpers ──────────────────────────────────────────────────────────────

def try_parse_date(d, m, y=None):
    """Returns (month, day, year, ambiguous) or None"""
    d, m = int(d), int(m)
    year = int(y) if y else None
    if year and year < 100:
        year += 2000
    results = []
    try:
        datetime.date(year or 2000, m, d); results.append((m, d))
    except ValueError:
        pass
    try:
        datetime.date(year or 2000, d, m); results.append((d, m))
    except ValueError:
        pass
    if not results:
        return None
    mo, dy = results[0]
    return mo, dy, year, len(results) > 1


def parse_name(t):
    for p in NAME_RE:
        m = p.search(t)
        if m:
            n = m.group(1).strip().split()[0]
            if len(n) >= 2:
                return n.capitalize()
    return None


def parse_age(t):
    for p in AGE_RE:
        m = p.search(t)
        if m:
            a = int(m.group(1))
            if 10 <= a <= 100:
                return a
    return None


def parse_pronouns(t):
    for p in PRONOUNS_RE:
        m = p.search(t)
        if m:
            return m.group(1).lower()
    return None


def ordinal(n):
    return f"{n}" + {1: "st", 2: "nd", 3: "rd"}.get(n % 10 if n % 100 not in (11, 12, 13) else 0, "th")


def month_name(m):
    return datetime.date(2000, m, 1).strftime("%B")


def next_birthday(month, day):
    now = datetime.datetime.now(datetime.timezone.utc)
    try:
        c = datetime.datetime(now.year, month, day, tzinfo=datetime.timezone.utc)
    except ValueError:
        c = datetime.datetime(now.year, 3, 1, tzinfo=datetime.timezone.utc)
    if c.date() < now.date():
        try:
            c = datetime.datetime(now.year + 1, month, day, tzinfo=datetime.timezone.utc)
        except ValueError:
            c = datetime.datetime(now.year + 1, 3, 1, tzinfo=datetime.timezone.utc)
    return c


def days_until(month, day):
    today = datetime.datetime.now(datetime.timezone.utc).date()
    return (next_birthday(month, day).date() - today).days


def is_today(month, day):
    n = datetime.datetime.now(datetime.timezone.utc)
    return n.month == month and n.day == day


# ── Shared embed styling ────────────────────────────────────────────────────────

def base_embed(*, title=None, description=None, color=BRAND_COLOR, ctx: Optional[commands.Context] = None):
    """Every embed in this cog goes through here so the bot has one consistent look."""
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


# ── Modern Discord UI (Components V2) ─────────────────────────────────────────
# Components V2 is supported by discord.py 2.6+ and replaces the old embed-only
# presentation with composable containers, text displays, sections and action rows.

HAS_COMPONENTS_V2 = hasattr(discord.ui, "LayoutView") and hasattr(discord.ui, "Container")
if not HAS_COMPONENTS_V2:
    raise RuntimeError(
        "BirthdayIntro Components V2 UI requires discord.py 2.6+; "
        "please upgrade discord.py before loading this cog."
    )


class BirthdayLayoutView(discord.ui.LayoutView):
    """Reusable Components V2 card shell."""

    def __init__(self, *, color=BRAND_COLOR, timeout=180):
        super().__init__(timeout=timeout)
        self._color = color
        self.container = discord.ui.Container(accent_colour=color)
        self.add_item(self.container)

    def set_card(self, embed: discord.Embed):
        """Render an existing Embed's information as a Components V2 card."""
        self.container.clear_items()

        title = embed.title or ""
        description = embed.description or ""
        body = f"# {title}" if title else ""
        if description:
            body = f"{body}\n\n{description}" if body else description

        thumbnail_url = getattr(getattr(embed, "thumbnail", None), "url", None)
        if thumbnail_url:
            section = discord.ui.Section(
                discord.ui.TextDisplay(body[:4000] or "\u200b"),
                accessory=discord.ui.Thumbnail(thumbnail_url),
            )
            self.container.add_item(section)
        else:
            self.container.add_item(discord.ui.TextDisplay(body[:4000] or "\u200b"))

        fields = getattr(embed, "fields", None) or []
        for field in fields:
            self.container.add_item(
                discord.ui.TextDisplay(
                    f"**{field.name}**\n{field.value}"[:4000]
                )
            )

        footer = getattr(embed, "footer", None)
        footer_text = getattr(footer, "text", None)
        if footer_text:
            self.container.add_item(discord.ui.Separator(spacing=discord.SeparatorSpacing.small))
            self.container.add_item(discord.ui.TextDisplay(f"-# {footer_text}"))
        return self


class V2CardView(BirthdayLayoutView):
    def __init__(self, embed: discord.Embed, *, timeout=180):
        color = getattr(embed, "color", None) or BRAND_COLOR
        super().__init__(color=color, timeout=timeout)
        self.set_card(embed)


async def send_ui(destination, *, embed=None, view=None, ephemeral=False, **kwargs):
    """Send a Components V2 card safely to interactions, command contexts, or channels."""
    if view is None:
        view = V2CardView(embed) if embed is not None else None
    elif embed is not None and hasattr(view, "set_card"):
        view.set_card(embed)

    # Components V2 LayoutView messages cannot contain legacy content/embeds.
    kwargs.pop("content", None)
    kwargs.pop("embed", None)
    kwargs.pop("embeds", None)

    # Interaction responses/followups support ephemeral messages. A normal
    # Messageable (text channel, member DM, or user DM) does not.
    if isinstance(destination, discord.Interaction):
        if destination.response.is_done():
            message = await destination.followup.send(
                view=view, ephemeral=ephemeral, **kwargs
            )
        else:
            await destination.response.send_message(
                view=view, ephemeral=ephemeral, **kwargs
            )
            try:
                message = await destination.original_response()
            except (discord.NotFound, discord.HTTPException):
                message = None

    elif isinstance(destination, commands.Context):
        interaction = destination.interaction
        if interaction is not None:
            if interaction.response.is_done():
                message = await interaction.followup.send(
                    view=view, ephemeral=ephemeral, **kwargs
                )
            else:
                await interaction.response.send_message(
                    view=view, ephemeral=ephemeral, **kwargs
                )
                try:
                    message = await interaction.original_response()
                except (discord.NotFound, discord.HTTPException):
                    message = None
        else:
            # Prefix commands cannot be ephemeral; send normally and don't
            # pass the unsupported ephemeral keyword to Context.send().
            message = await destination.send(view=view, **kwargs)

    else:
        # Channels and user/member DMs are regular Messageable destinations.
        # Deliberately omit ephemeral here, including for scheduled broadcasts.
        message = await destination.send(view=view, **kwargs)

    if view is not None and message is not None and hasattr(view, "message"):
        view.message = message
    return message



class AmbiguousDateView(BirthdayLayoutView):
    """Ask user to pick which date interpretation is correct."""

    def __init__(self, user_id: int, opt_a: tuple, opt_b: tuple, timeout=120):
        super().__init__(color=WARN_COLOR, timeout=timeout)
        self.user_id = user_id
        self.chosen = None
        self.opt_a = opt_a
        self.opt_b = opt_b
        self._build()

    def _build(self):
        self.container.clear_items()
        self.container.add_item(
            discord.ui.TextDisplay(
                f"# {PENCIL} Which date is your birthday?\n\n"
                f"`{self.opt_a[1]}/{self.opt_a[0]}` could be read two ways — tap the correct one."
            )
        )
        row = discord.ui.ActionRow()
        for label, cid, style in [
            (f"{month_name(self.opt_a[0])} {self.opt_a[1]}", "a", discord.ButtonStyle.blurple),
            (f"{month_name(self.opt_b[0])} {self.opt_b[1]}", "b", discord.ButtonStyle.green),
        ]:
            btn = discord.ui.Button(label=label, custom_id=f"birthday-date-{cid}", style=style, emoji=CALENDAR)

            async def cb(i: discord.Interaction, _btn: discord.ui.Button, _c=cid):
                self.chosen = _c
                self.stop()
                await i.response.defer()

            btn.callback = cb
            row.add_item(btn)
        self.container.add_item(row)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id == self.user_id:
            return True
        await interaction.response.send_message("Only the member setting this birthday can choose the date.", ephemeral=True)
        return False

    async def on_timeout(self):
        for item in self.container.children:
            if isinstance(item, discord.ui.ActionRow):
                for child in item.children:
                    child.disabled = True


class WishView(BirthdayLayoutView):
    def __init__(self, cog, uid: int, guild_id: int, *, title=None, description=None, color=TODAY_COLOR, timeout=300):
        super().__init__(color=color, timeout=timeout)
        self.cog = cog
        self.uid = uid
        self.guild_id = guild_id
        self.wishers = set()
        self._title = title or f"{CAKE} Birthday Wishes"
        self._description = description or "Send them a birthday wish below!"
        self._build()

    def _build(self):
        self.container.clear_items()
        self.container.add_item(
            discord.ui.TextDisplay(f"# {self._title}\n\n{self._description}")
        )
        row = discord.ui.ActionRow()
        wish_btn = discord.ui.Button(
            label="Send Birthday Wish",
            style=discord.ButtonStyle.green,
            emoji=PARTY,
            custom_id=f"birthday-wish-{self.uid}",
        )
        view_btn = discord.ui.Button(
            label="View Wishers",
            style=discord.ButtonStyle.secondary,
            emoji=GIFT,
            custom_id=f"birthday-wishers-{self.uid}",
        )

        async def wish_callback(interaction: discord.Interaction):
            if interaction.user.id == self.uid:
                return await interaction.response.send_message(
                    f"{CROSS} You can't wish yourself!", ephemeral=True
                )
            if interaction.user.id in self.wishers:
                return await interaction.response.send_message(
                    f"{CHECK} You've already wished them!", ephemeral=True
                )
            self.wishers.add(interaction.user.id)
            member = interaction.guild.get_member(self.uid) if interaction.guild else None
            profile = await self.cog.get_user(self.uid, self.guild_id)
            if member and profile and profile.get("dm_notifications", True):
                try:
                    wish_embed = discord.Embed(
                        title=f"{PARTY} You've got a birthday wish!",
                        description=(
                            f"**{interaction.user.display_name}** from **{interaction.guild.name}** "
                            f"wishes you a Happy Birthday! {CAKE}"
                        ),
                        color=FREE_COLOR,
                    )
                    wish_embed.set_thumbnail(url=interaction.user.display_avatar.url)
                    await send_ui(member, embed=wish_embed)
                except discord.Forbidden:
                    pass
            await interaction.response.send_message(f"{PARTY} Wish sent!", ephemeral=True)

        async def wishers_callback(interaction: discord.Interaction):
            c = len(self.wishers)
            text = (
                f"🎊 **{c}** {'person has' if c == 1 else 'people have'} wished them so far!"
                if c else "No wishes yet — be the first! 🎉"
            )
            await interaction.response.send_message(text, ephemeral=True)

        wish_btn.callback = wish_callback
        view_btn.callback = wishers_callback
        row.add_item(wish_btn)
        row.add_item(view_btn)
        self.container.add_item(row)

    async def on_timeout(self):
        for item in self.container.children:
            if isinstance(item, discord.ui.ActionRow):
                for child in item.children:
                    child.disabled = True


class BirthdayAnnouncementView(discord.ui.View):
    """Legacy View for a classic embed announcement with real mention pings."""

    def __init__(self, cog, uid: int, guild_id: int, timeout=300):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.uid = uid
        self.guild_id = guild_id
        self.wishers = set()

    @discord.ui.button(
        label="Send Birthday Wish",
        style=discord.ButtonStyle.green,
        emoji=PARTY,
    )
    async def send_birthday_wish(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if interaction.user.id == self.uid:
            return await interaction.response.send_message(
                f"{CROSS} You can't wish yourself!", ephemeral=True
            )
        if interaction.user.id in self.wishers:
            return await interaction.response.send_message(
                f"{CHECK} You've already wished them!", ephemeral=True
            )

        self.wishers.add(interaction.user.id)
        member = interaction.guild.get_member(self.uid) if interaction.guild else None
        profile = await self.cog.get_user(self.uid, self.guild_id)
        if member and profile and profile.get("dm_notifications", True):
            try:
                wish_embed = discord.Embed(
                    title=f"{PARTY} You've got a birthday wish!",
                    description=(
                        f"**{interaction.user.display_name}** from **{interaction.guild.name}** "
                        f"wishes you a Happy Birthday! {CAKE}"
                    ),
                    color=FREE_COLOR,
                )
                wish_embed.set_thumbnail(url=interaction.user.display_avatar.url)
                await send_ui(member, embed=wish_embed)
            except discord.Forbidden:
                pass
            except discord.HTTPException:
                logger.warning("Could not DM birthday wish to user %s", self.uid, exc_info=True)

        await interaction.response.send_message(
            f"{PARTY} Wish sent!", ephemeral=True
        )

    @discord.ui.button(
        label="View Wishers",
        style=discord.ButtonStyle.secondary,
        emoji=GIFT,
    )
    async def view_birthday_wishers(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        count = len(self.wishers)
        message = (
            f"🎊 **{count}** {'person has' if count == 1 else 'people have'} wished them so far!"
            if count else "No wishes yet — be the first! 🎉"
        )
        await interaction.response.send_message(message, ephemeral=True)


class HelpView(BirthdayLayoutView):
    def __init__(self, pages: dict, selected="home", timeout=180):
        super().__init__(color=BRAND_COLOR, timeout=timeout)
        self.pages = pages
        self.selected = selected
        self._build()

    def _build(self):
        self.container.clear_items()
        self.set_card(self.pages[self.selected])
        row = discord.ui.ActionRow()
        select = discord.ui.Select(
            placeholder="Select a category from the menu below",
            custom_id="birthday-help-category",
            options=[
                discord.SelectOption(label="Home", value="home", emoji="🏠", description="Overview of the birthday system"),
                discord.SelectOption(label="Free Commands", value="free", emoji="🆓", description="Available to everyone"),
                discord.SelectOption(label="Premium Commands", value="premium", emoji=str(CROWN), description="Requires premium"),
                discord.SelectOption(label="Admin Setup", value="setup", emoji=str(GEAR), description="One-time server configuration"),
            ],
        )
        select.callback = self._select_callback
        row.add_item(select)
        self.container.add_item(row)

    async def _select_callback(self, interaction: discord.Interaction):
        # Locate the selected value from the dispatched component.
        select = next((c for c in self._walk_action_rows() if isinstance(c, discord.ui.Select)), None)
        value = select.values[0] if select else "home"
        new_view = HelpView(self.pages, selected=value, timeout=self.timeout)
        await interaction.response.edit_message(view=new_view)

    def _walk_action_rows(self):
        for item in self.container.children:
            if isinstance(item, discord.ui.ActionRow):
                yield from item.children

    async def on_timeout(self):
        for item in self.container.children:
            if isinstance(item, discord.ui.ActionRow):
                for child in item.children:
                    child.disabled = True


# ── Cog ────────────────────────────────────────────────────────────────────────

class BirthdayIntro(commands.Cog):
    """Birthday system — free + premium, MongoDB, prefix + slash"""

    def __init__(self, bot):
        self.bot = bot
        self.col = None
        self.scol = None
        self.user_store_path = os.path.join("data", "birthday_data.json")
        self.settings_store_path = os.path.join("data", "birthday_settings.json")
        self.birthday_sent_path = os.path.join("data", "birthday_sent.json")
        self._startup_birthday_check_started = False
        self._birthday_check_lock = asyncio.Lock()

    async def cog_load(self):
        mongo = getattr(self.bot, "mongo_db", None)
        if mongo is not None:
            self.col = mongo["birthday"]
            self.scol = mongo["birthday_settings"]
        else:
            logger.warning("%s: mongo_db unavailable", self.__class__.__name__)
        if self.bot.is_ready():
            self._ensure_daily_check_running()
            self._start_startup_birthday_check()
        logger.info("%s ready", self.__class__.__name__)

    async def cog_unload(self):
        if self.daily_check.is_running():
            self.daily_check.cancel()

    # ── Storage helpers ────────────────────────────────────────────────────────

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
            # Legacy records are read only in their original server and are
            # migrated to a server-scoped key on their next update.
            return await self.col.find_one({"_id": uid, "guild_id": guild_id})
        data = self._load_store(self.user_store_path)
        scoped = data.get(key)
        if scoped is not None:
            return scoped
        legacy = data.get(str(uid))
        return legacy if legacy and legacy.get("guild_id") == guild_id else None

    async def get_settings(self, gid: int):
        if self.scol is not None:
            return (await self.scol.find_one({"_id": gid})) or {}
        data = self._load_store(self.settings_store_path)
        return data.get(str(gid), {})

    async def upsert_user(self, uid: int, guild_id: int, data: dict):
        key = self._user_key(uid, guild_id)
        payload = {**data, "_id": key, "user_id": uid, "guild_id": guild_id}
        if self.col is not None:
            await self.col.update_one({"_id": key}, {"$set": payload}, upsert=True)
            # Remove the exact legacy record after its server-scoped replacement
            # exists, preventing a duplicate birthday announcement.
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

    def _load_store(self, path: str) -> dict:
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r", encoding="utf-8") as fp:
                data = json.load(fp)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to read %s: %s", path, exc)
            return {}
        return data if isinstance(data, dict) else {}

    def _save_store(self, path: str, payload: dict):
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fp:
            json.dump(payload, fp, indent=2, ensure_ascii=False)

    def _save_birthday_sent_log(self, payload: dict):
        """Atomically persist only today's birthday announcement records."""
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

    def _load_birthday_sent_log(self, today: datetime.date) -> dict:
        """Load today's send ledger and purge every record from another date."""
        if not os.path.exists(self.birthday_sent_path):
            return {}

        try:
            with open(self.birthday_sent_path, "r", encoding="utf-8") as fp:
                loaded = json.load(fp)
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning(
                "Could not read birthday send ledger %s (%s); treating it as empty",
                self.birthday_sent_path, exc,
            )
            return {}

        if not isinstance(loaded, dict):
            logger.warning("Birthday send ledger is not a JSON object; treating it as empty")
            return {}

        today_key = today.isoformat()
        current = {
            str(key): entry
            for key, entry in loaded.items()
            if isinstance(entry, dict) and entry.get("date") == today_key
        }
        removed = len(loaded) - len(current)
        if removed:
            try:
                self._save_birthday_sent_log(current)
                logger.info(
                    "Birthday send ledger: removed %s stale record(s); keeping %s from %s",
                    removed, len(current), today_key,
                )
            except OSError:
                logger.exception("Could not prune stale birthday send ledger entries")
        return current

    def _has_sent_birthday_today(
        self, sent_log: dict, guild_id: int, user_id: int, today: datetime.date
    ) -> bool:
        entry = sent_log.get(f"{guild_id}:{user_id}")
        return isinstance(entry, dict) and entry.get("date") == today.isoformat()

    def _record_birthday_sent(
        self, sent_log: dict, guild_id: int, user_id: int, now: datetime.datetime
    ):
        """Record a successful announcement so restarts won't send it twice today."""
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
            # The Discord send already succeeded; make the persistence failure
            # prominent so it can be fixed before a restart causes a duplicate.
            logger.exception(
                "Birthday was announced to user %s in guild %s, but the send ledger could not be saved",
                user_id, guild_id,
            )

    def _normalize_birthday_doc(self, doc: dict) -> Optional[dict]:
        if not isinstance(doc, dict):
            return None
        try:
            uid = int(doc.get("user_id", doc["_id"]))
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
                result.update(birthday_month=p[0], birthday_day=p[1],
                              birthday_year=p[2], ambiguous=p[3],
                              raw_d=int(m.group(1)), raw_m=int(m.group(2)))
        result["name"] = parse_name(text)
        result["age"] = parse_age(text)
        result["pronouns"] = parse_pronouns(text)
        return result

    # ── Daily announcement ─────────────────────────────────────────────────────

    @tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=datetime.timezone.utc))
    async def daily_check(self):
        await self._run_birthday_check()

    def _start_startup_birthday_check(self):
        """Schedule one birthday scan after the bot becomes ready."""
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
        # Serialize the startup scan with the scheduled daily scan.
        async with self._birthday_check_lock:
            await self._process_birthdays()

    async def _process_birthdays(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        # A persistent daily ledger prevents duplicate wishes across restarts.
        # Any record whose date isn't today is purged before scanning birthdays.
        sent_log = self._load_birthday_sent_log(now.date())
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
            if int(doc["month"]) != now.month or int(doc["day"]) != now.day:
                continue
            stats["due_today"] += 1

            guild_id = int(doc.get("guild_id") or 0)
            if self._has_sent_birthday_today(
                sent_log, guild_id, doc["_id"], now.date()
            ):
                stats["already_sent_today"] += 1
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                stats["missing_guild"] += 1
                logger.warning(
                    "Birthday due for user %s, but guild %s is not available in the bot cache",
                    doc["_id"], guild_id,
                )
                continue

            # get_member() only checks cache. Fetch from Discord when the
            # member cache doesn't contain this user, especially after startup.
            member = guild.get_member(doc["_id"])
            if member is None:
                try:
                    member = await guild.fetch_member(doc["_id"])
                except discord.NotFound:
                    stats["missing_member"] += 1
                    logger.warning(
                        "Birthday due for user %s in guild %s, but member was not found",
                        doc["_id"], guild.id,
                    )
                    continue
                except (discord.Forbidden, discord.HTTPException) as exc:
                    stats["missing_member"] += 1
                    logger.warning(
                        "Could not fetch birthday member %s in guild %s: %s",
                        doc["_id"], guild.id, exc,
                    )
                    continue

            settings = await self.get_settings(guild.id)
            channel_id = settings.get("announce_channel_id")
            if not channel_id:
                stats["missing_channel"] += 1
                logger.warning(
                    "Birthday due for user %s in guild %s, but no announcement channel is configured; "
                    "run /introbdsetup",
                    doc["_id"], guild.id,
                )
                continue

            try:
                channel_id = int(channel_id)
            except (TypeError, ValueError):
                stats["missing_channel"] += 1
                logger.warning(
                    "Birthday announcement channel ID %r is invalid in guild %s; run /introbdsetup",
                    channel_id, guild.id,
                )
                continue

            channel = guild.get_channel(channel_id)
            if channel is None:
                try:
                    channel = await self.bot.fetch_channel(channel_id)
                except (discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                    stats["missing_channel"] += 1
                    logger.warning(
                        "Could not resolve birthday announcement channel %s in guild %s: %s",
                        channel_id, guild.id, exc,
                    )
                    continue

            role_id = settings.get("announce_role_id")
            try:
                role = guild.get_role(int(role_id)) if role_id else None
            except (TypeError, ValueError):
                role = None
            if role:
                try:
                    await member.add_roles(role, reason="Birthday")
                    asyncio.create_task(self._drop_role(member, role))
                except discord.Forbidden:
                    logger.warning(
                        "Missing permission to grant birthday role %s in guild %s",
                        role.id, guild.id,
                    )
                except discord.HTTPException as exc:
                    logger.warning(
                        "Could not grant birthday role %s in guild %s: %s",
                        role.id, guild.id, exc,
                    )

            ping_role_id = settings.get("ping_role_id")
            try:
                ping_role = guild.get_role(int(ping_role_id)) if ping_role_id else None
            except (TypeError, ValueError):
                ping_role = None
            if ping_role_id and ping_role is None:
                logger.warning(
                    "Configured birthday ping role %r was not found in guild %s",
                    ping_role_id, guild.id,
                )

            display = doc.get("name") or member.display_name
            age_line, pronoun_line = "", ""
            if doc.get("year"):
                try:
                    age = now.year - int(doc["year"]) - (
                        (now.month, now.day) < (int(doc["month"]), int(doc["day"]))
                    )
                    age_line = f"\nTurning **{ordinal(age)}** today! {STAR}"
                except (TypeError, ValueError):
                    logger.warning("Invalid birth year for user %s; omitting age", doc["_id"])
            if doc.get("pronouns"):
                pronoun_line = f"\n*({doc['pronouns']})*"

            is_prem = await self.is_premium(guild.id)
            template = doc.get("custom_wish") or f"{PARTY} It's {{mention}}'s birthday today! Wish them well! {CAKE}"
            try:
                rendered = template.format(mention=member.mention, name=display)
            except (IndexError, KeyError, ValueError) as exc:
                logger.warning("Invalid custom birthday template for %s: %s", doc["_id"], exc)
                rendered = f"{PARTY} It's {member.mention}'s birthday today! Wish them well! {CAKE}"
            desc = rendered + age_line + pronoun_line + "\n\n*Click below to send a wish!*"

            # Use a classic Discord message here: plain message content is
            # where actual mention notifications are generated, while the embed
            # carries the birthday card. Components V2 layouts cannot share a
            # message with legacy embeds, so use a normal View for these buttons.
            embed = discord.Embed(
                title=f"{CAKE} Happy Birthday, {display}! {CAKE}",
                description=desc,
                color=PREMIUM_COLOR if is_prem else TODAY_COLOR,
                timestamp=now,
            )
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"{guild.name} • Birthday System")
            ping_text = " ".join(
                mention for mention in (
                    member.mention,
                    ping_role.mention if ping_role else None,
                ) if mention
            )
            allowed_mentions = discord.AllowedMentions(
                users=[member],
                roles=[ping_role] if ping_role else [],
                everyone=False,
                replied_user=False,
            )

            try:
                await channel.send(
                    content=ping_text,
                    embed=embed,
                    view=BirthdayAnnouncementView(self, uid=doc["_id"], guild_id=guild.id),
                    allowed_mentions=allowed_mentions,
                )
            except discord.HTTPException as exc:
                stats["failed_send"] += 1
                logger.warning(
                    "Birthday announcement failed for user %s in guild %s, channel %s: %s",
                    doc["_id"], guild.id, channel_id, exc,
                )
                # No daily ledger entry was written, so the next check can retry.
                continue

            # Mark only after Discord accepted the announcement. The ledger is
            # written to disk, so a restart on the same day won't wish them twice.
            self._record_birthday_sent(sent_log, guild.id, doc["_id"], now)
            stats["announced"] += 1

            if doc.get("scope") == "mutual" and await self.is_premium(guild.id):
                for other_guild in self.bot.guilds:
                    if other_guild.id == guild.id:
                        continue
                    other_member = other_guild.get_member(doc["_id"])
                    if other_member is None:
                        try:
                            other_member = await other_guild.fetch_member(doc["_id"])
                        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                            continue
                    if self._has_sent_birthday_today(
                        sent_log, other_guild.id, doc["_id"], now.date()
                    ):
                        continue
                    other_settings = await self.get_settings(other_guild.id)
                    other_channel_id = other_settings.get("announce_channel_id")
                    if not other_channel_id:
                        continue
                    try:
                        other_channel_id = int(other_channel_id)
                        other_channel = other_guild.get_channel(other_channel_id)
                        if other_channel is None:
                            other_channel = await self.bot.fetch_channel(other_channel_id)

                        other_ping_role_id = other_settings.get("ping_role_id")
                        try:
                            other_ping_role = (
                                other_guild.get_role(int(other_ping_role_id))
                                if other_ping_role_id else None
                            )
                        except (TypeError, ValueError):
                            other_ping_role = None

                        cross_embed = discord.Embed(
                            title=f"{CAKE} Happy Birthday, {display}! {CAKE}",
                            description=desc,
                            color=PREMIUM_COLOR,
                            timestamp=now,
                        )
                        cross_embed.set_thumbnail(url=other_member.display_avatar.url)
                        cross_embed.set_footer(text=f"{other_guild.name} • Birthday System • Premium")
                        cross_ping_text = " ".join(
                            mention for mention in (
                                other_member.mention,
                                other_ping_role.mention if other_ping_role else None,
                            ) if mention
                        )
                        cross_allowed_mentions = discord.AllowedMentions(
                            users=[other_member],
                            roles=[other_ping_role] if other_ping_role else [],
                            everyone=False,
                            replied_user=False,
                        )
                        await other_channel.send(
                            content=cross_ping_text,
                            embed=cross_embed,
                            view=BirthdayAnnouncementView(
                                self, uid=doc["_id"], guild_id=guild.id
                            ),
                            allowed_mentions=cross_allowed_mentions,
                        )
                        self._record_birthday_sent(
                            sent_log, other_guild.id, doc["_id"], now
                        )
                    except (TypeError, ValueError, discord.NotFound, discord.Forbidden, discord.HTTPException) as exc:
                        logger.warning(
                            "Cross-server birthday announcement failed for user %s in guild %s: %s",
                            doc["_id"], other_guild.id, exc,
                        )

        logger.info(
            "Birthday check summary: scanned=%(profiles)s, due_today=%(due_today)s, "
            "already_sent_today=%(already_sent_today)s, announced=%(announced)s, "
            "missing_guild=%(missing_guild)s, missing_member=%(missing_member)s, "
            "missing_channel=%(missing_channel)s, failed_send=%(failed_send)s",
            stats,
        )

    @daily_check.before_loop
    async def _before(self):
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

    # ── Intro listener ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot or not msg.guild:
            return
        s = await self.get_settings(msg.guild.id)
        if not s.get("intro_channel_id") or msg.channel.id != s["intro_channel_id"]:
            return

        p = self.parse_intro(msg.content)
        if not any([p.get("birthday_month"), p.get("name"), p.get("age"), p.get("pronouns")]):
            return

        uid = msg.author.id
        was_ambiguous = False

        # Date confirmation is a basic correctness feature, available to everyone.
        if p.get("ambiguous") and p.get("birthday_month"):
            was_ambiguous = True
            rd, rm, ry = p["raw_d"], p["raw_m"], p.get("birthday_year")
            opt_a, opt_b = (rm, rd, ry), (rd, rm, ry)  # DD/MM, MM/DD
            view = AmbiguousDateView(user_id=uid, opt_a=opt_a, opt_b=opt_b)
            try:
                dm = await send_ui(msg.author, view=view)
                await view.wait()
                chosen = opt_b if view.chosen == "b" else opt_a
                p["birthday_month"], p["birthday_day"] = chosen[0], chosen[1]
                was_ambiguous = view.chosen is None
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
            # Preserve premium fields
            "custom_wish": existing.get("custom_wish"),
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
                f"\n\nAnything wrong? Everyone can fix it — no premium needed:\n"
                f"`/editbirthday` to correct the date • `/editprofile` to correct name/age/pronouns"
            )
            try:
                intro_embed = base_embed(
                    title=f"{WAVE} Here's what I picked up from your intro!",
                    description="\n".join(lines) + note,
                    color=FREE_COLOR,
                )
                intro_embed.set_footer(text="Your birthday will be announced automatically 🎉")
                await send_ui(msg.author, embed=intro_embed)
            except discord.Forbidden:
                pass

    # ══════════════════════════════════════════════════════════════════════════
    # HELP MENU
    # ══════════════════════════════════════════════════════════════════════════

    def _build_help_pages(self, ctx: commands.Context) -> dict:
        home = base_embed(
            title=f"{CAKE} Birthday System",
            description=(
                "Select a category from the menu below to view available commands.\n\n"
                f"{CALENDAR} **Birthday Setup**\n"
                f"{INFO} **Free Commands**\n"
                f"{CROWN} **Premium Commands**\n"
                f"{GEAR} **Admin Setup**\n"
            ),
            color=BRAND_COLOR, ctx=ctx,
        )

        free = base_embed(
            title=f"🆓 Free Commands",
            description=(
                "Available to every member, no premium required:\n\n"
                "`/setbirthday <date>` — set your birthday (accepts most formats)\n"
                "`/birthday [user]` — view your or someone else's birthday\n"
                "`/birthdaylist [limit]` — see upcoming birthdays in this server\n"
                "`/editbirthday <month> <day> [year]` — fix a wrong date\n"
                "`/editprofile [name] [age] [pronouns]` — fix your parsed info\n"
                "`/myprofile` — view everything saved about you\n"
                "`/birthdaywish <message>` — personalise your announcement\n"
                "`/birthdaynotify <true|false>` — choose whether wishes send you a DM\n"
                "`/scanintros [limit]` *(admin, up to 100)* — import recent intros"
            ),
            color=FREE_COLOR, ctx=ctx,
        )

        premium = base_embed(
            title=f"{CROWN} Premium Commands",
            description=(
                "For reach and high-volume administration, not everyday setup:\n\n"
                "`/birthdayscope <server|mutual>` — announce in this server only, "
                "or every mutual server\n"
                "`/scanintros [limit]` *(admin, up to 1,000)* — bulk-import older intros\n\n"
                "Your birthday, profile, announcement text, and DM preference remain free."
            ),
            color=PREMIUM_COLOR, ctx=ctx,
        )

        setup = base_embed(
            title=f"{GEAR} Admin Setup",
            description=(
                "One-time configuration for server staff:\n\n"
                "`/introbdsetup <intro_channel> <announce_channel> [birthday_role] [ping_role]`\n"
                "— tells the bot where to read intros from, where to post birthday "
                "announcements, optionally which role to grant for the day, and which role "
                "to ping in birthday announcements. The birthday person is pinged too.\n\n"
                "Once set up, the bot auto-detects birthdays, names, ages, and "
                "pronouns from new messages in the intro channel — nothing else "
                "to configure."
            ),
            color=BRAND_COLOR, ctx=ctx,
        )

        return {"home": home, "free": free, "premium": premium, "setup": setup}

    @commands.hybrid_command(name="birthdayhelp", description="View all birthday commands in an interactive menu")
    @commands.guild_only()
    async def birthdayhelp(self, ctx: commands.Context):
        """FREE — Interactive help menu for the birthday system."""
        pages = self._build_help_pages(ctx)
        view = HelpView(pages, selected="home")
        await send_ui(ctx, view=view)

    # ══════════════════════════════════════════════════════════════════════════
    # FREE COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.hybrid_command(name="setbirthday", description="Set your birthday — accepts most date formats")
    @app_commands.describe(
        date="Your birthday, e.g. 15/04  |  04/15  |  15-04-2001  |  April 15",
        year="Birth year (optional, only if not included in date)",
    )
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def setbirthday(self, ctx: commands.Context, date: str, year: Optional[int] = None):
        """FREE — Set your birthday. Works as n!setbirthday or /setbirthday."""
        date = date.strip()
        month = day = yr = None
        ambiguous = False
        numeric_match = None

        m = re.match(r"^(\d{1,2})[\/\-\.](\d{1,2})(?:[\/\-\.](\d{2,4}))?$", date)
        if m:
            numeric_match = m
            parsed = try_parse_date(m.group(1), m.group(2), m.group(3) or (str(year) if year else None))
            if not parsed:
                return await send_ui(ctx, embed=error_embed(
                    "That date doesn't exist — double check the day and month.", ctx=ctx
                ), ephemeral=True)
            month, day, yr, ambiguous = parsed
        else:
            for fmt in ["%B %d", "%b %d", "%d %B", "%d %b"]:
                try:
                    parts = date.split()[:2]
                    pd = datetime.datetime.strptime(" ".join(parts), fmt)
                    month, day, yr, ambiguous = pd.month, pd.day, year, False
                    break
                except ValueError:
                    continue
            else:
                return await send_ui(ctx, embed=error_embed(
                    "Couldn't understand that date format.\n\n"
                    "**Accepted formats:** `15/04` • `04/15` • `15-04-2001` • `April 15` • `15 April`",
                    ctx=ctx,
                ), ephemeral=True)

        if ambiguous and numeric_match:
            d_val, m_val = int(numeric_match.group(1)), int(numeric_match.group(2))
            opt_a = (m_val, d_val, yr)  # DD/MM
            opt_b = (d_val, m_val, yr)  # MM/DD
            view = AmbiguousDateView(user_id=ctx.author.id, opt_a=opt_a, opt_b=opt_b)
            reply = await send_ui(ctx, view=view, ephemeral=True)
            await view.wait()
            if view.chosen is None:
                return  # timed out, view is already disabled
            chosen = opt_b if view.chosen == "b" else opt_a
            month, day = chosen[0], chosen[1]

        existing = await self.get_user(ctx.author.id, ctx.guild.id) or {}
        await self.upsert_user(ctx.author.id, ctx.guild.id, {
            **{k: existing.get(k) for k in ("custom_wish", "scope", "dm_notifications", "name", "age", "pronouns") if k in existing},
            "month": month,
            "day": day,
            "year": yr,
        })

        d_left = days_until(month, day)
        status = f"{PARTY} That's today!" if d_left == 0 else f"Coming up in **{d_left}** days!"

        embed = success_embed(
            "Birthday Set!",
            f"**{month_name(month)} {day}**" + (f", {yr}" if yr else "") + f"\n{status}\n\n"
            f"Made a typo? Just run `/editbirthday` any time.",
            ctx=ctx,
        )
        embed.title = f"{CAKE} Birthday Set!"
        await send_ui(ctx, embed=embed)

    @commands.hybrid_command(name="birthday", description="View your or another user's birthday")
    @app_commands.describe(user="User to check (leave blank for yourself)")
    @commands.guild_only()
    async def birthday(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """FREE — Check birthday info"""
        target = user or ctx.author
        data = await self.get_user(target.id, ctx.guild.id)

        if not data or not data.get("month"):
            name = "You haven't" if target == ctx.author else f"{target.mention} hasn't"
            return await send_ui(ctx, embed=error_embed(
                f"{name} set a birthday yet.\nUse `/setbirthday` to add one!", ctx=ctx
            ))

        today = is_today(data["month"], data["day"])
        d_left = days_until(data["month"], data["day"])
        bd_str = f"{month_name(data['month'])} {data['day']}" + (f", {data['year']}" if data.get("year") else "")

        embed = base_embed(
            title=f"{CAKE + ' ' if today else ''}{target.display_name}'s Birthday",
            color=TODAY_COLOR if today else BRAND_COLOR,
            ctx=ctx,
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name=f"{CALENDAR} Date", value=bd_str, inline=True)
        embed.add_field(name="⏳ Days Away", value=f"{PARTY} **TODAY!**" if today else f"{d_left} days", inline=True)
        if data.get("year"):
            now = datetime.datetime.now(datetime.timezone.utc)
            age = now.year - data["year"] - ((now.month, now.day) < (data["month"], data["day"]))
            embed.add_field(name=f"{CAKE} Age", value=str(age) + (" today!" if today else ""), inline=True)
        embed.add_field(
            name="📆 Next Birthday",
            value=discord.utils.format_dt(next_birthday(data["month"], data["day"]), "D"),
            inline=True,
        )
        if data.get("pronouns"):
            embed.add_field(name="🏳️‍🌈 Pronouns", value=data["pronouns"], inline=True)
        await send_ui(ctx, embed=embed if not today else None, view=WishView(self, uid=target.id, guild_id=ctx.guild.id, title=embed.title, description=embed.description, color=TODAY_COLOR) if today else None)

    @commands.hybrid_command(name="birthdaylist", description="View upcoming birthdays in this server")
    @app_commands.describe(limit="How many to show (max 25)")
    @commands.guild_only()
    async def birthdaylist(self, ctx: commands.Context, limit: int = 10):
        """FREE — List upcoming birthdays"""
        limit = 10 if limit is None else max(1, min(int(limit), 25))
        upcoming = []

        async for doc in self.iter_birthdays(ctx.guild.id):
            if doc.get("month") is None or doc.get("day") is None:
                continue
            member = ctx.guild.get_member(int(doc["_id"]))
            if member is None:
                continue
            try:
                days = days_until(int(doc["month"]), int(doc["day"]))
            except Exception as e:
                logger.error(f"Skipping invalid birthday document {doc}: {e}")
                continue
            upcoming.append((days, member, doc))

        upcoming.sort(key=lambda x: x[0])
        if not upcoming:
            return await send_ui(ctx, embed=base_embed(
                title="📭 No birthdays yet",
                description="Members can add theirs any time with `/setbirthday`.",
                color=BRAND_COLOR, ctx=ctx,
            ))

        lines = []
        for d, member, doc in upcoming[:limit]:
            display = doc.get("name") or member.display_name
            bd_str = f"{month_name(doc['month'])} {doc['day']}"
            lines.append(f"{'🎂' if d == 0 else '🎈'} **{display}** — {bd_str} — {'🎉 **TODAY!**' if d == 0 else f'in **{d}** days'}")

        embed = base_embed(
            title=f"{PARTY} Upcoming Birthdays — {ctx.guild.name}",
            description="\n".join(lines),
            color=BRAND_COLOR, ctx=ctx,
        )
        embed.set_footer(text=f"Showing {min(len(upcoming), limit)} of {len(upcoming)}")
        await send_ui(ctx, embed=embed)

    @commands.hybrid_command(name="editbirthday", description="Fix your birthday date if it was parsed wrong")
    @app_commands.describe(month="Month (1-12)", day="Day (1-31)", year="Year (optional)")
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
        d_left = days_until(month, day)
        await send_ui(ctx, embed=success_embed(
            "Birthday Updated!",
            f"**{month_name(month)} {day}{', ' + str(year) if year else ''}**\n"
            f"{'🎉 Today!' if d_left == 0 else f'In **{d_left}** days!'}",
            ctx=ctx,
        ), ephemeral=True)

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
            update["name"] = name.strip(); lines.append(f"👤 Name → **{name}**")
        if age:
            update["age"] = age; lines.append(f"🔢 Age → **{age}**")
        if pronouns:
            update["pronouns"] = pronouns.lower().strip(); lines.append(f"🏳️‍🌈 Pronouns → **{pronouns}**")
        await self.upsert_user(ctx.author.id, ctx.guild.id, update)
        await send_ui(ctx, embed=success_embed("Profile Updated", "\n".join(lines), ctx=ctx), ephemeral=True)

    @commands.hybrid_command(name="myprofile", description="View your full birthday profile")
    @commands.guild_only()
    async def myprofile(self, ctx: commands.Context):
        """FREE — View everything the bot has stored for you."""
        data = await self.get_user(ctx.author.id, ctx.guild.id)
        if not data:
            return await send_ui(ctx, embed=error_embed(
                "No profile found yet. Post in the intro channel or use `/setbirthday`!", ctx=ctx
            ), ephemeral=True)

        embed = base_embed(title=f"👤 {ctx.author.display_name}'s Profile", color=BRAND_COLOR, ctx=ctx)
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        if data.get("name"):
            embed.add_field(name="👤 Name", value=data["name"], inline=True)
        if data.get("pronouns"):
            embed.add_field(name="🏳️‍🌈 Pronouns", value=data["pronouns"], inline=True)
        if data.get("age"):
            embed.add_field(name="🔢 Age", value=str(data["age"]), inline=True)
        if data.get("month") and data.get("day"):
            bd = f"{month_name(data['month'])} {data['day']}" + (f", {data['year']}" if data.get("year") else "")
            days_left = days_until(data["month"], data["day"])
            status = f"{PARTY} TODAY!" if days_left == 0 else f"in {days_left} days"
            embed.add_field(name=f"{CAKE} Birthday", value=f"{bd}\n{status}", inline=False)
        else:
            embed.add_field(name=f"{CAKE} Birthday", value="Not set — use `/setbirthday`", inline=False)

        premium_active = await self.is_premium(ctx.guild.id)
        scope_text = "All mutual servers" if data.get("scope") == "mutual" and premium_active else "This server only"
        if data.get("scope") == "mutual" and not premium_active:
            scope_text += " (cross-server is inactive)"
        embed.add_field(
            name="🌐 Announcement Scope",
            value=scope_text,
            inline=True,
        )
        embed.add_field(
            name="📬 Wish DMs",
            value=f"{CHECK} On" if data.get("dm_notifications", True) else f"{CROSS} Off",
            inline=True,
        )
        if data.get("custom_wish"):
            embed.add_field(name=f"{SPARKLE} Custom Wish", value=data["custom_wish"], inline=False)
        embed.set_footer(text=f"Source: {data.get('source', 'manual')} • Use /editprofile or /editbirthday to change any of this")
        await send_ui(ctx, embed=embed, ephemeral=True)

    @commands.hybrid_command(name="introbdsetup", description="Admin: configure intro & announcement channels")
    @app_commands.describe(
        intro_channel="The #introductions channel to watch",
        announce_channel="Channel for birthday announcements",
        birthday_role="Role to give members on their birthday (optional)",
        ping_role="Role to ping in the birthday announcement (optional)",
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def introbdsetup(
        self,
        ctx: commands.Context,
        intro_channel: discord.TextChannel,
        announce_channel: discord.TextChannel,
        birthday_role: Optional[discord.Role] = None,
        ping_role: Optional[discord.Role] = None,
    ):
        """FREE (admin) — Set up birthday scanning, announcements, and pings."""
        await self.upsert_settings(ctx.guild.id, {
            "intro_channel_id": intro_channel.id,
            "announce_channel_id": announce_channel.id,
            "announce_role_id": birthday_role.id if birthday_role else None,
            "ping_role_id": ping_role.id if ping_role else None,
        })
        embed = base_embed(title=f"{GIFT} Birthday System Configured!", color=FREE_COLOR, ctx=ctx)
        embed.add_field(name="📥 Intro Channel", value=intro_channel.mention, inline=True)
        embed.add_field(name="📢 Announce Channel", value=announce_channel.mention, inline=True)
        embed.add_field(name="🎭 Birthday Role", value=birthday_role.mention if birthday_role else "None", inline=True)
        embed.add_field(name="🔔 Ping Role", value=ping_role.mention if ping_role else "None", inline=True)
        embed.add_field(name=f"{INFO} Auto-detected from intros", value="Name • Birthday • Age • Pronouns", inline=False)
        tier = f"{CROWN} Premium active" if await self.is_premium(ctx.guild.id) else f"{LOCK} Free tier — see `/birthdayhelp` to compare"
        embed.add_field(name="💎 Tier", value=tier, inline=False)
        embed.set_footer(text="Members can now just chat in the intro channel — nothing else to configure")
        await send_ui(ctx, embed=embed)

    # ══════════════════════════════════════════════════════════════════════════
    # PREMIUM COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.hybrid_command(name="birthdaywish", description="Set a personal birthday announcement message")
    @app_commands.describe(message="Your message. Use {mention} for your ping, {name} for display name")
    @commands.guild_only()
    async def birthdaywish(self, ctx: commands.Context, *, message: str):
        """FREE — Customize the message shown on your birthday announcement."""
        if len(message) > 200:
            return await send_ui(ctx, embed=error_embed("Max 200 characters.", ctx=ctx), ephemeral=True)
        try:
            preview = message.format(mention=ctx.author.mention, name=ctx.author.display_name)
        except (IndexError, KeyError, ValueError):
            return await send_ui(ctx, embed=error_embed(
                "Use only `{mention}` and `{name}` placeholders in birthday wishes.", ctx=ctx
            ), ephemeral=True)
        await self.upsert_user(ctx.author.id, ctx.guild.id, {"custom_wish": message})
        embed = success_embed("Custom Wish Saved!", f"**Preview:**\n{preview}", ctx=ctx)
        embed.title = f"{SPARKLE} Custom Wish Saved!"
        embed.set_footer(text="This will appear in your birthday announcement")
        await send_ui(ctx, embed=embed, ephemeral=True)

    @commands.hybrid_command(name="birthdayscope", description="Premium — Choose where your birthday gets announced")
    @app_commands.describe(scope="server = this server only | mutual = all mutual servers with the bot")
    @app_commands.choices(scope=[
        app_commands.Choice(name="This server only", value="server"),
        app_commands.Choice(name="All mutual servers", value="mutual"),
    ])
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
            color=PREMIUM_COLOR, ctx=ctx,
        )
        if scope == "mutual":
            embed.set_footer(text="Only servers that have an announce channel configured will receive it")
        await send_ui(ctx, embed=embed, ephemeral=True)

    @commands.hybrid_command(name="birthdaynotify", description="Choose whether birthday wishes send you a DM")
    @app_commands.describe(enabled="True = receive DMs when someone wishes you, False = no DMs")
    @commands.guild_only()
    async def birthdaynotify(self, ctx: commands.Context, enabled: bool):
        """FREE — Control whether you get DMs when people wish you."""
        await self.upsert_user(ctx.author.id, ctx.guild.id, {"dm_notifications": enabled})
        embed = base_embed(
            title="📬 Notification Preference Updated",
            description=f"DM notifications are now **{'enabled ✅' if enabled else 'disabled ❌'}**.",
            color=FREE_COLOR, ctx=ctx,
        )
        await send_ui(ctx, embed=embed, ephemeral=True)

    @commands.hybrid_command(name="scanintros", description="Admin: scan past intro messages")
    @app_commands.describe(limit="Messages to scan (free: 100; premium: 1,000)")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def scanintros(self, ctx: commands.Context, limit: int = 100):
        """FREE — Import recent intro data; premium raises the scan limit."""
        s = await self.get_settings(ctx.guild.id)
        if not s.get("intro_channel_id"):
            return await send_ui(ctx, embed=error_embed("Run `/introbdsetup` first.", ctx=ctx))
        channel = ctx.guild.get_channel(s["intro_channel_id"])
        if not channel:
            return await send_ui(ctx, embed=error_embed("Intro channel not found — please re-run `/introbdsetup`.", ctx=ctx))
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
            await self.upsert_user(msg.author.id, ctx.guild.id, {
                "source": "scan",
                "month": p.get("birthday_month") or ex.get("month"),
                "day": p.get("birthday_day") or ex.get("day"),
                "year": p.get("birthday_year") or ex.get("year"),
                "name": p.get("name") or ex.get("name"),
                "age": p.get("age") or ex.get("age"),
                "pronouns": p.get("pronouns") or ex.get("pronouns"),
            })
            imported += 1
        embed = base_embed(
            title=f"{PENCIL} Scan Complete",
            description=f"{CHECK} Imported **{imported}** profiles.\n⏭️ Skipped **{skipped}** messages.",
            color=PREMIUM_COLOR, ctx=ctx,
        )
        embed.set_footer(text=f"Scanned last {limit} messages in #{channel.name}")
        await send_ui(ctx, embed=embed)

    # ── Error handlers ─────────────────────────────────────────────────────────

    @setbirthday.error
    async def _setbirthday_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await send_ui(ctx, embed=base_embed(
                title="⏳ Slow down",
                description=f"Wait **{error.retry_after:.0f}s** before setting your birthday again.",
                color=WARN_COLOR, ctx=ctx,
            ), ephemeral=True)

    @introbdsetup.error
    @scanintros.error
    async def _admin_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await send_ui(ctx, embed=error_embed("You need the **Manage Server** permission to do that.", ctx=ctx), ephemeral=True)


async def setup(bot):
    await bot.add_cog(BirthdayIntro(bot))
    logger.debug("Loaded BirthdayIntro")

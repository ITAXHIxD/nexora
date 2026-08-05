"""
cogs/utility/birthday_intro.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
FREE:
  • Auto-parse birthday from #introductions
  • n!setbirthday / /setbirthday  (multi-format, disambiguates on-the-spot)
  • n!birthday [user] / /birthday
  • n!birthdaylist / /birthdaylist
  • n!introbdsetup (admin)
  • Daily 9 AM announcement

PREMIUM:
  • n!editbirthday / /editbirthday    — fix parsed date
  • n!editprofile / /editprofile      — fix name, age, pronouns
  • n!myprofile / /myprofile          — view full parsed profile
  • n!birthdaywish / /birthdaywish    — custom announcement message
  • n!birthdayscope / /birthdayscope  — server-only OR all mutual servers
  • n!birthdaynotify / /birthdaynotify— toggle DM notifications
  • n!scanintros / /scanintros (admin)— backfill old intro messages
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

CAKE="🎂"; PARTY="🎉"; BALLOON="🎈"; GIFT="🎁"
STAR="⭐"; WAVE="👋"; PENCIL="📝"; CROWN="👑"; LOCK="🔒"; SPARKLE="✨"

# ── Regex patterns ─────────────────────────────────────────────────────────────
BIRTHDAY_RE   = re.compile(r"\b(\d{1,2})[\/\-\.](\d{1,2})(?:[\/\-\.](\d{2,4}))?\b")
NAME_RE       = [
    re.compile(r"(?:name\s*[:\-–]\s*)([A-Za-z][\w\s]{0,30}?)(?:\s*[,\n]|$)", re.I),
    re.compile(r"(?:i'?m|i am|call me|known as)\s+([A-Za-z][\w]{1,20})", re.I),
    re.compile(r"(?:hi|hey|hello)[,!]?\s+(?:i'?m|i am)\s+([A-Za-z][\w]{1,20})", re.I),
]
AGE_RE        = [
    re.compile(r"(?:age\s*[:\-–]\s*)(\d{1,2})", re.I),
    re.compile(r"\b(\d{1,2})\s*(?:years?\s*old|yo\b)", re.I),
    re.compile(r"(?:i'?m|i am)\s+(\d{1,2})(?:\s*years?\s*old)?", re.I),
]
PRONOUNS_RE   = [
    re.compile(r"(?:pronouns?\s*[:\-–]\s*)([\w]+(?:\/[\w]+)+)", re.I),
    re.compile(r"\b(she\/her|he\/him|they\/them|she\/they|he\/they|any\/all|xe\/xem|ze\/zir)\b", re.I),
]

# ── Parse helpers ──────────────────────────────────────────────────────────────

def try_parse_date(d, m, y=None):
    """Returns (month, day, year, ambiguous) or None"""
    d, m = int(d), int(m)
    year = int(y) if y else None
    if year and year < 100: year += 2000
    results = []
    try:    datetime.date(year or 2000, m, d); results.append((m, d))
    except: pass
    try:    datetime.date(year or 2000, d, m); results.append((d, m))
    except: pass
    if not results: return None
    mo, dy = results[0]
    return mo, dy, year, len(results) > 1

def parse_name(t):
    for p in NAME_RE:
        m = p.search(t)
        if m:
            n = m.group(1).strip().split()[0]
            if len(n) >= 2: return n.capitalize()
    return None

def parse_age(t):
    for p in AGE_RE:
        m = p.search(t)
        if m:
            a = int(m.group(1))
            if 10 <= a <= 100: return a
    return None

def parse_pronouns(t):
    for p in PRONOUNS_RE:
        m = p.search(t)
        if m: return m.group(1).lower()
    return None

def ordinal(n):
    return f"{n}" + {1:"st",2:"nd",3:"rd"}.get(n%10 if n%100 not in(11,12,13) else 0,"th")

def month_name(m): return datetime.date(2000, m, 1).strftime("%B")

def next_birthday(month, day):
    now = datetime.datetime.now(datetime.timezone.utc)
    try:    c = datetime.datetime(now.year, month, day, tzinfo=datetime.timezone.utc)
    except: c = datetime.datetime(now.year, 3, 1,     tzinfo=datetime.timezone.utc)
    if c.date() < now.date():
        try:    c = datetime.datetime(now.year+1, month, day, tzinfo=datetime.timezone.utc)
        except: c = datetime.datetime(now.year+1, 3, 1,     tzinfo=datetime.timezone.utc)
    return c

def days_until(month, day):
    today = datetime.datetime.now(datetime.timezone.utc).date()
    return (next_birthday(month, day).date() - today).days

def is_today(month, day):
    n = datetime.datetime.now(datetime.timezone.utc)
    return n.month == month and n.day == day

def premium_embed():
    return discord.Embed(
        title=f"{CROWN} Premium Feature",
        description=(
            f"**This feature requires premium.**\n\n"
            f"{SPARKLE} **Free:** Set birthday, view birthdays, daily announcements\n"
            f"{CROWN} **Premium:** Edit profile, custom wish message, cross-server scope, "
            f"scan intros, DM notification controls\n\n"
            f"Ask a server admin or the bot owner about upgrading!"
        ),
        color=discord.Color.gold()
    )

# ── Views ──────────────────────────────────────────────────────────────────────

class AmbiguousDateView(discord.ui.View):
    """Ask user to pick which date interpretation is correct"""
    def __init__(self, opt_a: tuple, opt_b: tuple, timeout=120):
        super().__init__(timeout=timeout)
        self.chosen = None
        for label, cid, style in [
            (f"{month_name(opt_a[0])} {opt_a[1]}", "a", discord.ButtonStyle.blurple),
            (f"{month_name(opt_b[0])} {opt_b[1]}", "b", discord.ButtonStyle.green),
        ]:
            btn = discord.ui.Button(label=label, custom_id=cid, style=style)
            async def cb(i, _c=cid): self.chosen = _c; self.stop(); await i.response.defer()
            btn.callback = cb
            self.add_item(btn)


class WishView(discord.ui.View):
    def __init__(self, uid: int, timeout=300):
        super().__init__(timeout=timeout)
        self.uid     = uid
        self.wishers = set()

    @discord.ui.button(label="🎉 Send Birthday Wish!", style=discord.ButtonStyle.green)
    async def wish(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id == self.uid:
            return await interaction.response.send_message("❌ Can't wish yourself!", ephemeral=True)
        if interaction.user.id in self.wishers:
            return await interaction.response.send_message("✅ Already wished!", ephemeral=True)
        self.wishers.add(interaction.user.id)
        member = interaction.guild.get_member(self.uid)
        if member:
            try:
                await member.send(embed=discord.Embed(
                    title=f"{PARTY} Birthday Wish!",
                    description=f"**{interaction.user.display_name}** from **{interaction.guild.name}** wishes you a Happy Birthday! {CAKE}",
                    color=discord.Color.gold()
                ).set_thumbnail(url=interaction.user.display_avatar.url))
            except discord.Forbidden: pass
        await interaction.response.send_message(f"{PARTY} Wish sent!", ephemeral=True)

    @discord.ui.button(label="🎁 View Wishers", style=discord.ButtonStyle.blurple)
    async def wishers_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        c = len(self.wishers)
        await interaction.response.send_message(
            f"🎊 **{c}** person(s) wished them!" if c else "No wishes yet — be first! 🎉",
            ephemeral=True
        )

# ── Cog ────────────────────────────────────────────────────────────────────────

class BirthdayIntro(commands.Cog):
    """Birthday system — free + premium, MongoDB, prefix + slash"""

    def __init__(self, bot):
        self.bot  = bot
        self.col  = None
        self.scol = None
        self.user_store_path = os.path.join("data", "birthday_data.json")
        self.settings_store_path = os.path.join("data", "birthday_settings.json")

    async def cog_load(self):
        if self.bot.mongo_db is not None:
            self.col  = self.bot.mongo_db["birthday"]
            self.scol = self.bot.mongo_db["birthday_settings"]
        else:
            logger.warning("%s: mongo_db unavailable", self.__class__.__name__)
        if self.bot.is_ready():
            self._ensure_daily_check_running()
        logger.info("%s ready", self.__class__.__name__)

    async def cog_unload(self):
        if self.daily_check.is_running():
            self.daily_check.cancel()

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def is_premium(self, guild_id: int) -> bool:
        result = self.bot.is_premium_guild(guild_id)
        if inspect.isawaitable(result):
            result = await result
        return bool(result)

    async def get_user(self, uid: int):
        if self.col is not None:
            return await self.col.find_one({"_id": uid})
        data = self._load_store(self.user_store_path)
        return data.get(str(uid))

    async def get_settings(self, gid: int):
        if self.scol is not None:
            return (await self.scol.find_one({"_id": gid})) or {}
        data = self._load_store(self.settings_store_path)
        return data.get(str(gid), {})

    async def upsert_user(self, uid: int, data: dict):
        if self.col is not None:
            await self.col.update_one({"_id": uid}, {"$set": data}, upsert=True)
            return
        store = self._load_store(self.user_store_path)
        existing = store.get(str(uid), {})
        store[str(uid)] = {**existing, **data, "_id": uid}
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

    def _normalize_birthday_doc(self, doc: dict) -> Optional[dict]:
        if not isinstance(doc, dict):
            return None

        try:
            uid = int(doc["_id"])
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
        result["name"]     = parse_name(text)
        result["age"]      = parse_age(text)
        result["pronouns"] = parse_pronouns(text)
        return result

    # ── Daily announcement ─────────────────────────────────────────────────────

    @tasks.loop(time=datetime.time(hour=9, minute=0, tzinfo=datetime.timezone.utc))
    async def daily_check(self):
        now = datetime.datetime.now(datetime.timezone.utc)
        async for doc in self.iter_birthdays():
            if not is_today(doc["month"], doc["day"]): continue
            if doc.get("last_notified_year") == now.year: continue
            await self.upsert_user(doc["_id"], {"last_notified_year": now.year})

            guild  = self.bot.get_guild(doc.get("guild_id", 0))
            if not guild: continue
            member = guild.get_member(doc["_id"])
            if not member: continue
            settings = await self.get_settings(guild.id)
            channel  = guild.get_channel(settings.get("announce_channel_id", 0))
            if not channel: continue

            # Birthday role
            role = guild.get_role(settings.get("announce_role_id", 0))
            if role:
                try: await member.add_roles(role, reason="Birthday"); asyncio.create_task(self._drop_role(member, role))
                except discord.Forbidden: pass

            display = doc.get("name") or member.display_name
            age_line, pronoun_line = "", ""
            if doc.get("year"):
                age = now.year - doc["year"] - ((now.month, now.day) < (doc["month"], doc["day"]))
                age_line = f"\nTurning **{ordinal(age)}** today! {STAR}"
            if doc.get("pronouns"):
                pronoun_line = f"\n*({doc['pronouns']})*"

            # Custom wish (premium) or default
            template = doc.get("custom_wish") or f"{PARTY} It's {{mention}}'s birthday today! Wish them well! {CAKE}"
            try:
                rendered = template.format(mention=member.mention, name=display)
            except (IndexError, KeyError, ValueError) as exc:
                logger.warning("Invalid custom birthday template for %s: %s", doc["_id"], exc)
                rendered = f"{PARTY} It's {member.mention}'s birthday today! Wish them well! {CAKE}"
            desc = rendered + age_line + pronoun_line + "\n\n*Click below to send a wish!*"

            embed = discord.Embed(title=f"{CAKE} Happy Birthday, {display}! {CAKE}", description=desc,
                                  color=discord.Color.gold(), timestamp=now)
            embed.set_thumbnail(url=member.display_avatar.url)
            embed.set_footer(text=f"{guild.name} • Birthday System")

            try: await channel.send(embed=embed, view=WishView(uid=doc["_id"]))
            except discord.Forbidden: pass

            # Cross-server scope (premium)
            if doc.get("scope") == "mutual" and await self.is_premium(guild.id):
                for og in self.bot.guilds:
                    if og.id == guild.id: continue
                    om = og.get_member(doc["_id"])
                    if not om: continue
                    os_ = await self.get_settings(og.id)
                    och = og.get_channel(os_.get("announce_channel_id", 0))
                    if not och: continue
                    try:
                        ce = discord.Embed(title=f"{CAKE} Happy Birthday, {display}! {CAKE}",
                                           description=desc, color=discord.Color.gold(), timestamp=now)
                        ce.set_thumbnail(url=member.display_avatar.url)
                        ce.set_footer(text=f"Cross-server • {CROWN} Premium")
                        await och.send(embed=ce, view=WishView(uid=doc["_id"]))
                    except discord.Forbidden: pass

    @daily_check.before_loop
    async def _before(self): await self.bot.wait_until_ready()

    @commands.Cog.listener()
    async def on_ready(self):
        self._ensure_daily_check_running()

    async def _drop_role(self, member, role, delay=86400):
        await asyncio.sleep(delay)
        try: await member.remove_roles(role, reason="Birthday expired")
        except: pass

    # ── Intro listener ─────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, msg: discord.Message):
        if msg.author.bot or not msg.guild: return
        s = await self.get_settings(msg.guild.id)
        if not s.get("intro_channel_id") or msg.channel.id != s["intro_channel_id"]: return

        p = self.parse_intro(msg.content)
        if not any([p.get("birthday_month"), p.get("name"), p.get("age"), p.get("pronouns")]): return

        uid = msg.author.id

        # Ambiguous date — DM confirmation (premium only, free gets DD/MM default)
        if p.get("ambiguous") and p.get("birthday_month") and await self.is_premium(msg.guild.id):
            rd, rm, ry = p["raw_d"], p["raw_m"], p.get("birthday_year")
            opt_a, opt_b = (rm, rd, ry), (rd, rm, ry)   # DD/MM, MM/DD
            view = AmbiguousDateView(opt_a=opt_a, opt_b=opt_b)
            try:
                dm = await msg.author.send(embed=discord.Embed(
                    title=f"{PENCIL} Which date is your birthday?",
                    description=f"`{rd}/{rm}` could be two different dates — tap the correct one:",
                    color=discord.Color.orange()
                ), view=view)
                await view.wait()
                chosen = opt_b if view.chosen == "b" else opt_a
                p["birthday_month"], p["birthday_day"] = chosen[0], chosen[1]
                await dm.delete()
            except discord.Forbidden: pass

        existing = await self.get_user(uid) or {}
        update   = {
            "guild_id":           msg.guild.id,
            "month":              p.get("birthday_month") or existing.get("month"),
            "day":                p.get("birthday_day")   or existing.get("day"),
            "year":               p.get("birthday_year")  or existing.get("year"),
            "name":               p.get("name")           or existing.get("name"),
            "age":                p.get("age")            or existing.get("age"),
            "pronouns":           p.get("pronouns")       or existing.get("pronouns"),
            "last_notified_year": existing.get("last_notified_year"),
            "source":             "intro",
            # Preserve premium fields
            "custom_wish":        existing.get("custom_wish"),
            "scope":              existing.get("scope", "server"),
            "dm_notifications":   existing.get("dm_notifications", True),
        }
        await self.upsert_user(uid, update)
        try: await msg.add_reaction(CAKE)
        except discord.Forbidden: pass

        lines = []
        if update.get("name"):     lines.append(f"👤 **Name:** {update['name']}")
        if update.get("month"):
            bd = f"{month_name(update['month'])} {update['day']}"
            if update.get("year"): bd += f", {update['year']}"
            lines.append(f"{CAKE} **Birthday:** {bd}")
        if update.get("age"):      lines.append(f"🔢 **Age:** {update['age']}")
        if update.get("pronouns"): lines.append(f"🏳️‍🌈 **Pronouns:** {update['pronouns']}")

        if lines:
            note = (f"\n\n{CROWN} *Premium users: use `n!editbirthday` or `/editbirthday` to fix anything!*"
                    if await self.is_premium(msg.guild.id)
                    else f"\n\n*Use `n!setbirthday` to manually correct your birthday if needed.*")
            try:
                await msg.author.send(embed=discord.Embed(
                    title=f"{WAVE} Here's what I noted from your intro!",
                    description="\n".join(lines) + note,
                    color=discord.Color.green()
                ).set_footer(text="Your birthday will be announced automatically 🎉"))
            except discord.Forbidden: pass

    # ══════════════════════════════════════════════════════════════════════════
    # FREE COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.hybrid_command(name="setbirthday", description="Set your birthday — accepts most date formats")
    @app_commands.describe(
        date="Your birthday, e.g. 15/04  |  04/15  |  15-04-2001  |  April 15",
        year="Birth year (optional, only if not included in date)"
    )
    @commands.guild_only()
    @commands.cooldown(1, 30, commands.BucketType.user)
    async def setbirthday(self, ctx: commands.Context, date: str, year: Optional[int] = None):
        """FREE — Set your birthday. Works as n!setbirthday or /setbirthday."""
        date = date.strip()
        month = day = yr = None

        # Try numeric formats: 15/04, 04/15, 15/04/2001
        m = re.match(r"^(\d{1,2})[\/\-\.](\d{1,2})(?:[\/\-\.](\d{2,4}))?$", date)
        if m:
            parsed = try_parse_date(m.group(1), m.group(2), m.group(3) or (str(year) if year else None))
            if not parsed:
                return await ctx.send(embed=discord.Embed(
                    description="❌ That date doesn't exist. Check your day and month.",
                    color=discord.Color.red()
                ), ephemeral=True)
            month, day, yr, ambiguous = parsed
        else:
            # Try written formats: "April 15", "15 April", "Apr 15"
            for fmt in ["%B %d", "%b %d", "%d %B", "%d %b"]:
                try:
                    parts = date.split()[:2]
                    pd = datetime.datetime.strptime(" ".join(parts), fmt)
                    month, day, yr, ambiguous = pd.month, pd.day, year, False
                    break
                except ValueError: continue
            else:
                return await ctx.send(embed=discord.Embed(
                    description=(
                        "❌ Couldn't understand that date format.\n\n"
                        "**Accepted formats:**\n"
                        "`15/04` `04/15` `15-04-2001` `April 15` `15 April`"
                    ),
                    color=discord.Color.red()
                ), ephemeral=True)

        # If date is ambiguous ask right here in the channel (ephemeral)
        if ambiguous:
            d_val, m_val = int(m.group(1)), int(m.group(2))
            opt_a = (m_val, d_val, yr)   # DD/MM
            opt_b = (d_val, m_val, yr)   # MM/DD
            view  = AmbiguousDateView(opt_a=opt_a, opt_b=opt_b)
            reply = await ctx.send(embed=discord.Embed(
                title=f"{PENCIL} Which date is correct?",
                description=f"`{d_val}/{m_val}` could be two different dates — pick yours:",
                color=discord.Color.orange()
            ), view=view, ephemeral=True)
            await view.wait()
            chosen = opt_b if view.chosen == "b" else opt_a
            month, day = chosen[0], chosen[1]

        existing = await self.get_user(ctx.author.id) or {}
        await self.upsert_user(ctx.author.id, {
            **{k: existing.get(k) for k in ("custom_wish","scope","dm_notifications","name","age","pronouns") if existing.get(k)},
            "_id":      ctx.author.id,
            "guild_id": ctx.guild.id,
            "month":    month,
            "day":      day,
            "year":     yr,
        })

        d_left = days_until(month, day)
        status = "🎉 That's today!" if d_left == 0 else f"Coming up in **{d_left}** days!"

        embed = discord.Embed(
            title=f"{CAKE} Birthday Set!",
            description=(
                f"**{month_name(month)} {day}**"
                + (f", {yr}" if yr else "")
                + f"\n{status}"
            ),
            color=discord.Color.green()
        )

    @commands.hybrid_command(name="birthday", description="View your or another user's birthday")
    @app_commands.describe(user="User to check (leave blank for yourself)")
    @commands.guild_only()
    async def birthday(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """FREE — Check birthday info"""
        target = user or ctx.author
        data   = await self.get_user(target.id)

        if not data or not data.get("month"):
            name = "You haven't" if target == ctx.author else f"{target.mention} hasn't"
            return await ctx.send(embed=discord.Embed(
                description=f"❌ {name} set a birthday yet.\nUse `n!setbirthday` or `/setbirthday`!",
                color=discord.Color.red()
            ))

        today  = is_today(data["month"], data["day"])
        d_left = days_until(data["month"], data["day"])
        bd_str = f"{month_name(data['month'])} {data['day']}" + (f", {data['year']}" if data.get("year") else "")

        embed = discord.Embed(
            title=f"{CAKE + ' ' if today else ''}{target.display_name}'s Birthday",
            color=discord.Color.gold() if today else discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="📅 Date",          value=bd_str,                                              inline=True)
        embed.add_field(name="⏳ Days Away",     value="🎉 **TODAY!**" if today else f"{d_left} days",        inline=True)
        if data.get("year"):
            now = datetime.datetime.now(datetime.timezone.utc)
            age = now.year - data["year"] - ((now.month, now.day) < (data["month"], data["day"]))
            embed.add_field(name=f"{CAKE} Age",  value=str(age) + (" today!" if today else ""),              inline=True)
        embed.add_field(name="📆 Next Birthday", value=discord.utils.format_dt(next_birthday(data["month"], data["day"]), "D"), inline=True)
        if data.get("pronouns"):
            embed.add_field(name="🏳️‍🌈 Pronouns", value=data["pronouns"], inline=True)
        embed.set_footer(text="Birthday System")
        await ctx.send(embed=embed, view=WishView(uid=target.id) if today else None)

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
            return await ctx.send(embed=discord.Embed(
                description=f"📭 No birthdays yet! Members can use `n!setbirthday` or `/setbirthday`.",
                color=discord.Color.blue()
            ))
        lines = []
        for d, member, doc in upcoming[:limit]:
            display = doc.get("name") or member.display_name
            bd_str  = f"{month_name(doc['month'])} {doc['day']}"
            lines.append(f"{'🎂' if d==0 else '🎈'} **{display}** — {bd_str} — {'🎉 **TODAY!**' if d==0 else f'in **{d}** days'}")
        embed = discord.Embed(
            title=f"{PARTY} Upcoming Birthdays — {ctx.guild.name}",
            description="\n".join(lines),
            color=discord.Color.gold(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Showing {min(len(upcoming),limit)} of {len(upcoming)}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="introbdsetup", description="Admin: configure intro & announcement channels")
    @app_commands.describe(
        intro_channel="The #introductions channel to watch",
        announce_channel="Channel for birthday announcements",
        birthday_role="Role to give members on their birthday (optional)"
    )
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def introbdsetup(self, ctx: commands.Context, intro_channel: discord.TextChannel, announce_channel: discord.TextChannel, birthday_role: Optional[discord.Role] = None):
        """FREE (admin) — Set up the birthday system"""
        await self.upsert_settings(ctx.guild.id, {
            "intro_channel_id":    intro_channel.id,
            "announce_channel_id": announce_channel.id,
            "announce_role_id":    birthday_role.id if birthday_role else None,
        })
        embed = discord.Embed(title=f"{GIFT} Birthday System Configured!", color=discord.Color.green(), timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.add_field(name="📥 Intro Channel",    value=intro_channel.mention,                               inline=True)
        embed.add_field(name="📢 Announce Channel", value=announce_channel.mention,                            inline=True)
        embed.add_field(name="🎭 Birthday Role",    value=birthday_role.mention if birthday_role else "None",  inline=True)
        embed.add_field(name="ℹ️ Auto-parsed",      value="Name • Birthday • Age • Pronouns",                  inline=False)
        tier = f"{CROWN} Premium active" if await self.is_premium(ctx.guild.id) else f"{LOCK} Free tier"
        embed.add_field(name="💎 Tier", value=tier, inline=False)
        await ctx.send(embed=embed)

    # ══════════════════════════════════════════════════════════════════════════
    # PREMIUM COMMANDS
    # ══════════════════════════════════════════════════════════════════════════

    @commands.hybrid_command(name="editbirthday", description=f"{CROWN} Premium — Fix your birthday date")
    @app_commands.describe(month="Month (1-12)", day="Day (1-31)", year="Year (optional)")
    @commands.guild_only()
    async def editbirthday(self, ctx: commands.Context, month: int, day: int, year: Optional[int] = None):
        """PREMIUM — Correct your birthday date"""
        if not await self.is_premium(ctx.guild.id):
            return await ctx.send(embed=premium_embed(), ephemeral=True)
        if not (1 <= month <= 12):
            return await ctx.send(embed=discord.Embed(description="❌ Month must be 1–12.", color=discord.Color.red()), ephemeral=True)
        try: datetime.date(year or 2000, month, day)
        except ValueError:
            return await ctx.send(embed=discord.Embed(description="❌ That date doesn't exist.", color=discord.Color.red()), ephemeral=True)
        await self.upsert_user(ctx.author.id, {"month": month, "day": day, "year": year, "guild_id": ctx.guild.id})
        d_left = days_until(month, day)
        await ctx.send(embed=discord.Embed(
            title=f"{CAKE} Birthday Updated!",
            description=f"**{month_name(month)} {day}{', '+str(year) if year else ''}**\n{'🎉 Today!' if d_left==0 else f'In **{d_left}** days!'}",
            color=discord.Color.green()
        ), ephemeral=True)

    @commands.hybrid_command(name="editprofile", description=f"{CROWN} Premium — Update name, age, or pronouns")
    @app_commands.describe(name="Your display name", age="Your age", pronouns="Your pronouns (e.g. she/her)")
    @commands.guild_only()
    async def editprofile(self, ctx: commands.Context, name: Optional[str] = None, age: Optional[int] = None, pronouns: Optional[str] = None):
        """PREMIUM — Update your intro profile fields"""
        if not await self.is_premium(ctx.guild.id):
            return await ctx.send(embed=premium_embed(), ephemeral=True)
        if not any([name, age, pronouns]):
            return await ctx.send(embed=discord.Embed(description="❌ Provide at least one field.", color=discord.Color.red()), ephemeral=True)
        update = {"guild_id": ctx.guild.id}
        lines  = []
        if name:     update["name"]     = name.strip();             lines.append(f"👤 Name → **{name}**")
        if age:      update["age"]      = age;                      lines.append(f"🔢 Age → **{age}**")
        if pronouns: update["pronouns"] = pronouns.lower().strip(); lines.append(f"🏳️‍🌈 Pronouns → **{pronouns}**")
        await self.upsert_user(ctx.author.id, update)
        await ctx.send(embed=discord.Embed(title="✅ Profile Updated", description="\n".join(lines), color=discord.Color.green()), ephemeral=True)

    @commands.hybrid_command(name="myprofile", description=f"{CROWN} Premium — View your full birthday profile")
    @commands.guild_only()
    async def myprofile(self, ctx: commands.Context):
        """PREMIUM — View everything the bot has stored for you"""
        if not await self.is_premium(ctx.guild.id):
            return await ctx.send(embed=premium_embed(), ephemeral=True)
        data = await self.get_user(ctx.author.id)
        if not data:
            return await ctx.send(embed=discord.Embed(
                description="❌ No profile found. Post in #introductions or use `n!setbirthday`!",
                color=discord.Color.red()
            ), ephemeral=True)
        embed = discord.Embed(title=f"👤 {ctx.author.display_name}'s Profile", color=discord.Color.blue(), timestamp=datetime.datetime.now(datetime.timezone.utc))
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        if data.get("name"):     embed.add_field(name="👤 Name",      value=data["name"],     inline=True)
        if data.get("pronouns"): embed.add_field(name="🏳️‍🌈 Pronouns", value=data["pronouns"], inline=True)
        if data.get("age"):      embed.add_field(name="🔢 Age",        value=str(data["age"]), inline=True)
        if data.get("month") and data.get("day"):
            bd = f"{month_name(data['month'])} {data['day']}" + (f", {data['year']}" if data.get("year") else "")
            days_left = days_until(data["month"], data["day"])
            birthday_status = "🎉 TODAY!" if days_left == 0 else f"in {days_left} days"
            embed.add_field(name=f"{CAKE} Birthday", value=f"{bd}\n{birthday_status}", inline=False)
        else:
            embed.add_field(name=f"{CAKE} Birthday", value="Not set — use `n!setbirthday`", inline=False)
        embed.add_field(name="🌐 Scope",           value="All mutual servers" if data.get("scope")=="mutual" else "This server only", inline=True)
        embed.add_field(name="📬 DM Notifications",value="✅ On" if data.get("dm_notifications",True) else "❌ Off",                   inline=True)
        if data.get("custom_wish"):
            embed.add_field(name=f"{SPARKLE} Custom Wish", value=data["custom_wish"], inline=False)
        embed.set_footer(text=f"Source: {data.get('source','manual')} • Use commands to edit")
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="birthdaywish", description=f"{CROWN} Premium — Set a custom birthday announcement message")
    @app_commands.describe(message="Your message. Use {mention} for your ping, {name} for display name")
    @commands.guild_only()
    async def birthdaywish(self, ctx: commands.Context, *, message: str):
        """PREMIUM — Customize the message shown on your birthday announcement"""
        if not await self.is_premium(ctx.guild.id):
            return await ctx.send(embed=premium_embed(), ephemeral=True)
        if len(message) > 200:
            return await ctx.send(embed=discord.Embed(description="❌ Max 200 characters.", color=discord.Color.red()), ephemeral=True)
        try:
            preview = message.format(mention=ctx.author.mention, name=ctx.author.display_name)
        except (IndexError, KeyError, ValueError):
            return await ctx.send(embed=discord.Embed(
                description="❌ Use only `{mention}` and `{name}` placeholders in birthday wishes.",
                color=discord.Color.red()
            ), ephemeral=True)
        await self.upsert_user(ctx.author.id, {"custom_wish": message, "guild_id": ctx.guild.id})
        await ctx.send(embed=discord.Embed(
            title=f"{SPARKLE} Custom Wish Saved!",
            description=f"**Preview:**\n{preview}",
            color=discord.Color.green()
        ).set_footer(text="This will appear in your birthday announcement"), ephemeral=True)

    @commands.hybrid_command(name="birthdayscope", description=f"{CROWN} Premium — Choose where your birthday gets announced")
    @app_commands.describe(scope="server = this server only | mutual = all mutual servers with the bot")
    @app_commands.choices(scope=[
        app_commands.Choice(name="This server only", value="server"),
        app_commands.Choice(name="All mutual servers", value="mutual"),
    ])
    @commands.guild_only()
    async def birthdayscope(self, ctx: commands.Context, scope: str):
        """PREMIUM — Control where your birthday announcement gets sent"""
        if not await self.is_premium(ctx.guild.id):
            return await ctx.send(embed=premium_embed(), ephemeral=True)
        await self.upsert_user(ctx.author.id, {"scope": scope, "guild_id": ctx.guild.id})
        label = "all mutual servers" if scope == "mutual" else "this server only"
        embed = discord.Embed(
            title="🌐 Announcement Scope Updated",
            description=f"Your birthday will be announced in **{label}**.",
            color=discord.Color.green()
        )
        if scope == "mutual":
            embed.set_footer(text="Only servers that have an announce channel set up will receive it")
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="birthdaynotify", description=f"{CROWN} Premium — Toggle birthday DM notifications")
    @app_commands.describe(enabled="True = receive DMs when someone wishes you, False = no DMs")
    @commands.guild_only()
    async def birthdaynotify(self, ctx: commands.Context, enabled: bool):
        """PREMIUM — Control whether you get DMs when people wish you"""
        if not await self.is_premium(ctx.guild.id):
            return await ctx.send(embed=premium_embed(), ephemeral=True)
        await self.upsert_user(ctx.author.id, {"dm_notifications": enabled, "guild_id": ctx.guild.id})
        await ctx.send(embed=discord.Embed(
            description=f"📬 DM notifications **{'✅ enabled' if enabled else '❌ disabled'}**.",
            color=discord.Color.green()
        ), ephemeral=True)

    @commands.hybrid_command(name="scanintros", description=f"{CROWN} Premium (admin) — Scan past intro messages")
    @app_commands.describe(limit="Messages to scan (max 200, default 100)")
    @commands.guild_only()
    @commands.has_permissions(manage_guild=True)
    async def scanintros(self, ctx: commands.Context, limit: int = 100):
        """PREMIUM (admin) — Retroactively import data from old intro messages"""
        if not await self.is_premium(ctx.guild.id):
            return await ctx.send(embed=premium_embed(), ephemeral=True)
        s = await self.get_settings(ctx.guild.id)
        if not s.get("intro_channel_id"):
            return await ctx.send(embed=discord.Embed(description="❌ Run `n!introbdsetup` first.", color=discord.Color.red()))
        channel = ctx.guild.get_channel(s["intro_channel_id"])
        if not channel:
            return await ctx.send(embed=discord.Embed(description="❌ Intro channel not found.", color=discord.Color.red()))
        await ctx.defer()
        limit    = max(10, min(limit, 200))
        imported = 0; skipped = 0
        async for msg in channel.history(limit=limit):
            if msg.author.bot: continue
            p = self.parse_intro(msg.content)
            if not any([p.get("birthday_month"), p.get("name"), p.get("age"), p.get("pronouns")]):
                skipped += 1; continue
            ex = await self.get_user(msg.author.id) or {}
            await self.upsert_user(msg.author.id, {
                "guild_id": ctx.guild.id, "source": "scan",
                "month":    p.get("birthday_month") or ex.get("month"),
                "day":      p.get("birthday_day")   or ex.get("day"),
                "year":     p.get("birthday_year")  or ex.get("year"),
                "name":     p.get("name")           or ex.get("name"),
                "age":      p.get("age")            or ex.get("age"),
                "pronouns": p.get("pronouns")       or ex.get("pronouns"),
            })
            imported += 1
        await ctx.send(embed=discord.Embed(
            title=f"{PENCIL} Scan Complete",
            description=f"✅ Imported **{imported}** profiles.\n⏭️ Skipped **{skipped}** messages.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        ).set_footer(text=f"Scanned last {limit} messages in #{channel.name}"))

    # ── Error handlers ─────────────────────────────────────────────────────────

    @setbirthday.error
    async def _setbirthday_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send(embed=discord.Embed(
                description=f"⏳ Wait **{error.retry_after:.0f}s** before setting again.",
                color=discord.Color.orange()
            ), ephemeral=True)

    @introbdsetup.error
    @scanintros.error
    async def _admin_error(self, ctx, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send(embed=discord.Embed(description="❌ You need **Manage Server** permission.", color=discord.Color.red()), ephemeral=True)


async def setup(bot):
    await bot.add_cog(BirthdayIntro(bot))
    logger.info("Loaded BirthdayIntro")

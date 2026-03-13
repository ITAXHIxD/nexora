"""
cogs/core/help.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
/help                    → main menu with categories
/help <command>          → detailed command info + suggestions
n!help <command>         → same as above (hybrid)
Search button            → fuzzy search with suggestions

AUTO-SYNC: on cog_load, every registered bot command that is NOT
already in COMMAND_DATA gets a stub entry automatically.
This means newly added commands are always searchable without
editing this file. Just add a proper entry to COMMAND_DATA
whenever you want full docs for a new command.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

# used to detect cog category from file path
import os

logger = logging.getLogger(__name__)

# ── Colour helpers ─────────────────────────────────────────────────────────────

def cfg_color(bot, key: str, fallback: int = 0x5865F2) -> int:
    try:    return int(bot.bot_config["ui_settings"][key], 16)
    except: return fallback

def prefix(bot) -> str:
    try:    return str(bot.bot_config["bot_settings"]["default_prefix"])
    except: return "n!"

# ══════════════════════════════════════════════════════════════════════════════
# COMMAND REGISTRY
# Each entry has:
#   name        — primary command name
#   aliases     — alternate names
#   category    — category key
#   premium     — bool
#   admin       — requires manage_guild
#   description — one-liner shown in lists
#   usage       — list of usage strings (prefix + slash)
#   examples    — concrete examples
#   notes       — extra tips / bullet points shown in detailed view
#   related     — list of related command names (for suggestions)
# ══════════════════════════════════════════════════════════════════════════════

COMMAND_DATA = {
    # ── BIRTHDAY ──────────────────────────────────────────────────────────────
    "setbirthday": {
        "name": "setbirthday",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Set your birthday so the bot can announce it!",
        "usage": [
            "n!setbirthday <date> [year]",
            "/setbirthday <date> [year]",
        ],
        "examples": [
            "n!setbirthday 15/04",
            "n!setbirthday 04/15",
            "n!setbirthday 15/04/2001",
            "n!setbirthday April 15",
            "/setbirthday 15/04 2001",
        ],
        "notes": [
            "Accepted formats: `15/04` `04/15` `15-04-2001` `15.04` `April 15` `15 April`",
            "If the date is ambiguous (e.g. `05/06`) two buttons will appear — tap the correct one",
            "You can update your birthday anytime by running the command again",
            "The year is optional but needed for age calculation on your birthday",
        ],
        "related": ["birthday", "birthdaylist", "editbirthday", "myprofile"],
    },
    "birthday": {
        "name": "birthday",
        "aliases": ["bday"],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "View your or another user's birthday and countdown",
        "usage": [
            "n!birthday [user]",
            "/birthday [user]",
        ],
        "examples": [
            "n!birthday",
            "n!birthday @Alex",
            "/birthday",
            "/birthday @Alex",
        ],
        "notes": [
            "Leave `user` blank to check your own birthday",
            "Shows the date, days until next birthday, and age if year was provided",
            "On the birthday itself a 🎉 Wish button appears so others can send wishes",
        ],
        "related": ["setbirthday", "birthdaylist", "myprofile"],
    },
    "birthdaylist": {
        "name": "birthdaylist",
        "aliases": ["bdaylist"],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "List upcoming birthdays in this server, sorted by soonest",
        "usage": [
            "n!birthdaylist [limit]",
            "/birthdaylist [limit]",
        ],
        "examples": [
            "n!birthdaylist",
            "n!birthdaylist 20",
            "/birthdaylist 5",
        ],
        "notes": [
            "Default limit is 10, maximum is 25",
            "🎂 = birthday is TODAY, 🎈 = upcoming",
            "Only shows members who have set their birthday with `/setbirthday`",
        ],
        "related": ["setbirthday", "birthday"],
    },
    "editbirthday": {
        "name": "editbirthday",
        "aliases": [],
        "category": "utility",
        "premium": True,
        "admin": False,
        "description": "👑 Premium — Fix your birthday if it was parsed wrong",
        "usage": [
            "n!editbirthday <month> <day> [year]",
            "/editbirthday <month> <day> [year]",
        ],
        "examples": [
            "n!editbirthday 4 15",
            "n!editbirthday 4 15 2001",
            "/editbirthday 4 15 2001",
        ],
        "notes": [
            "Month and day must be numbers (e.g. `4` for April, `15` for the 15th)",
            "Year is optional — only needed for age display",
            "Use this if the intro parser got your date wrong",
        ],
        "related": ["setbirthday", "editprofile", "myprofile"],
    },
    "editprofile": {
        "name": "editprofile",
        "aliases": [],
        "category": "utility",
        "premium": True,
        "admin": False,
        "description": "👑 Premium — Update your name, age, or pronouns from your intro",
        "usage": [
            "n!editprofile [name] [age] [pronouns]",
            "/editprofile [name] [age] [pronouns]",
        ],
        "examples": [
            "n!editprofile name:Alex",
            "n!editprofile pronouns:they/them",
            "/editprofile name:Alex age:20 pronouns:she/her",
        ],
        "notes": [
            "All fields are optional — only provide what you want to change",
            "This edits what the bot parsed from your #introductions message",
            "Changes are shown in `/myprofile` and on your birthday announcement",
        ],
        "related": ["myprofile", "editbirthday", "setbirthday"],
    },
    "myprofile": {
        "name": "myprofile",
        "aliases": [],
        "category": "utility",
        "premium": True,
        "admin": False,
        "description": "👑 Premium — View your full birthday & intro profile",
        "usage": [
            "n!myprofile",
            "/myprofile",
        ],
        "examples": [
            "n!myprofile",
            "/myprofile",
        ],
        "notes": [
            "Shows your name, pronouns, age, birthday, announcement scope, and custom wish",
            "Only visible to you (ephemeral — hidden from others)",
            "Use `/editprofile` or `/editbirthday` to change anything",
        ],
        "related": ["editprofile", "editbirthday", "birthdaywish"],
    },
    "birthdaywish": {
        "name": "birthdaywish",
        "aliases": [],
        "category": "utility",
        "premium": True,
        "admin": False,
        "description": "👑 Premium — Set a custom message for your birthday announcement",
        "usage": [
            "n!birthdaywish <message>",
            "/birthdaywish <message>",
        ],
        "examples": [
            "n!birthdaywish {mention} is finally old! 🎉",
            "n!birthdaywish It's {name}'s special day — shower them with love! 💕",
            "/birthdaywish {mention} just leveled up in real life! 🎂",
        ],
        "notes": [
            "Use `{mention}` to include your @mention in the message",
            "Use `{name}` to include your display name",
            "Max 200 characters",
            "A preview of how it looks is shown when you set it",
        ],
        "related": ["birthdayscope", "myprofile", "birthdaynotify"],
    },
    "birthdayscope": {
        "name": "birthdayscope",
        "aliases": [],
        "category": "utility",
        "premium": True,
        "admin": False,
        "description": "👑 Premium — Choose if your birthday is announced in this server or all mutual servers",
        "usage": [
            "n!birthdayscope <server|mutual>",
            "/birthdayscope <server|mutual>",
        ],
        "examples": [
            "n!birthdayscope server",
            "n!birthdayscope mutual",
            "/birthdayscope mutual",
        ],
        "notes": [
            "`server` = announced only in the server where you set it (default)",
            "`mutual` = announced in every server where both you and the bot are present",
            "The other servers also need an announce channel set up with `/introbdsetup`",
        ],
        "related": ["birthdaywish", "myprofile", "birthdaynotify"],
    },
    "birthdaynotify": {
        "name": "birthdaynotify",
        "aliases": [],
        "category": "utility",
        "premium": True,
        "admin": False,
        "description": "👑 Premium — Toggle DM notifications when someone wishes you",
        "usage": [
            "n!birthdaynotify <true|false>",
            "/birthdaynotify <true|false>",
        ],
        "examples": [
            "n!birthdaynotify true",
            "n!birthdaynotify false",
            "/birthdaynotify false",
        ],
        "notes": [
            "`true` = you get a DM every time someone clicks the 🎉 Wish button",
            "`false` = no DMs (you still get announced in the channel)",
        ],
        "related": ["birthdaywish", "myprofile"],
    },
    "introbdsetup": {
        "name": "introbdsetup",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": True,
        "description": "Admin — Configure which channel to watch for intros and where to announce birthdays",
        "usage": [
            "n!introbdsetup <intro_channel> <announce_channel> [birthday_role]",
            "/introbdsetup <intro_channel> <announce_channel> [birthday_role]",
        ],
        "examples": [
            "n!introbdsetup #introductions #birthdays",
            "n!introbdsetup #introductions #general @Birthday",
            "/introbdsetup #introductions #birthdays @🎂Birthday",
        ],
        "notes": [
            "Requires **Manage Server** permission",
            "Once set, the bot automatically reads new messages in the intro channel",
            "The birthday role (optional) is given to members on their birthday for 24 hours",
            "Use `/scanintros` (premium) to import old intro messages retroactively",
        ],
        "related": ["scanintros", "birthdaylist"],
    },
    "scanintros": {
        "name": "scanintros",
        "aliases": [],
        "category": "utility",
        "premium": True,
        "admin": True,
        "description": "👑 Premium Admin — Scan past intro messages to import birthday data",
        "usage": [
            "n!scanintros [limit]",
            "/scanintros [limit]",
        ],
        "examples": [
            "n!scanintros",
            "n!scanintros 200",
            "/scanintros 150",
        ],
        "notes": [
            "Requires **Manage Server** permission",
            "Default: scans last 100 messages. Max: 200",
            "Safe to run multiple times — won't duplicate existing entries",
            "Run `/introbdsetup` first before scanning",
        ],
        "related": ["introbdsetup", "birthdaylist"],
    },

    # ── AFK ───────────────────────────────────────────────────────────────────
    "afk": {
        "name": "afk",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Set yourself as AFK — the bot will notify others who mention you",
        "usage": [
            "n!afk [reason]",
            "/afk [global_afk] [reason]",
        ],
        "examples": [
            "n!afk",
            "n!afk sleeping 💤",
            "n!afk at school, back later",
            "/afk reason:Eating dinner",
            "/afk global_afk:true reason:On vacation",
        ],
        "notes": [
            "Your nickname gets `[AFK]` prepended automatically",
            "Send **any message** (not a command) to remove AFK",
            "When someone mentions you, the bot notifies them you're AFK",
            "`global_afk: true` applies your AFK across all servers the bot is in",
            "You'll get a DM summary of everyone who mentioned you while you were AFK",
        ],
        "related": ["unafk", "afkstatus", "afklist", "afksettings"],
    },
    "unafk": {
        "name": "unafk",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Manually remove your AFK status",
        "usage": [
            "n!unafk",
            "/unafk",
        ],
        "examples": [
            "n!unafk",
            "/unafk",
        ],
        "notes": [
            "AFK is removed automatically when you send a message too",
            "Shows how long you were AFK and how many mentions you got",
        ],
        "related": ["afk", "afkstatus"],
    },
    "afkstatus": {
        "name": "afkstatus",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Check the AFK status of yourself or another user",
        "usage": [
            "n!afkstatus [user]",
            "/afkstatus [user]",
        ],
        "examples": [
            "n!afkstatus",
            "n!afkstatus @Alex",
            "/afkstatus @Alex",
        ],
        "notes": [
            "Shows reason, how long they've been AFK, scope, and mention count",
            "Leave `user` blank to check yourself",
        ],
        "related": ["afk", "unafk", "afklist"],
    },
    "afklist": {
        "name": "afklist",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": True,
        "description": "Mod — List all currently AFK users in this server",
        "usage": [
            "n!afklist",
            "/afklist",
        ],
        "examples": [
            "n!afklist",
            "/afklist",
        ],
        "notes": [
            "Requires **Manage Messages** permission",
            "Shows AFK reason and duration for each member",
        ],
        "related": ["afk", "afkstatus"],
    },
    "afksettings": {
        "name": "afksettings",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Toggle DM notifications for mentions received while AFK",
        "usage": [
            "n!afksettings <true|false>",
            "/afksettings <true|false>",
        ],
        "examples": [
            "n!afksettings true",
            "n!afksettings false",
            "/afksettings false",
        ],
        "notes": [
            "Must be currently AFK to use this",
            "`true` = get a DM every time someone mentions you",
            "`false` = no DMs during AFK",
        ],
        "related": ["afk", "unafk"],
    },

    # ── SPOTIFY ───────────────────────────────────────────────────────────────
    "spotify": {
        "name": "spotify",
        "aliases": ["spt", "nowplaying", "np"],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Show what someone is currently listening to on Spotify",
        "usage": [
            "n!spotify [user]",
            "/spotify [user]",
        ],
        "examples": [
            "n!spotify",
            "n!spotify @Alex",
            "/spotify",
            "/spotify @Alex",
        ],
        "notes": [
            "Leave `user` blank to check your own Spotify status",
            "The target user must have **Spotify** connected to Discord AND have activity status sharing enabled",
            "Shows track, artist, album, real-time progress bar and % complete",
            "🔄 **Refresh** button updates the progress bar live",
            "🎉 **Party Mode** button publicly announces you're vibing to the same song",
            "📋 **Copy Track** copies `Track — Artist` to clipboard (ephemeral)",
            "If the user's status is hidden, the bot cannot see their Spotify activity",
        ],
        "related": ["afk", "userinfo"],
    },

    # ── SHIP ──────────────────────────────────────────────────────────────────
    "ship": {
        "name": "ship",
        "aliases": [],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Ship two people together and see their love compatibility 💘",
        "usage": [
            "n!ship [user1] [user2]",
            "/ship [user1] [user2]",
        ],
        "examples": [
            "n!ship",
            "n!ship @Alex",
            "n!ship @Alex @Blake",
            "n!ship Alex Blake",
            "n!ship @Alex random",
            "/ship user1:@Alex user2:@Blake",
            "/ship user2:random",
        ],
        "notes": [
            "No args = ships you with a random server member",
            "One arg = ships you with that person",
            "Both args = ships those two people together",
            "Use `random` as either arg to pick a random server member",
            "Plain text names work too — e.g. `n!ship Alex Blake` (no @mention needed)",
            "Results are **consistent** — the same pair always gets the same % (hash-based)",
            "Use 🔁 **Re-roll** for a random result that changes each time",
            "8 tiers: 💔 Disaster → 🤍 Lukewarm → 💛 Neutral → 💓 Promising → 💕 Great Vibes → 💖 Perfect Match → 💞 SOULMATES",
            "❤️ **React** button counts how many people react to the ship",
            "🔗 **Share** posts a public message with the ship result",
        ],
        "related": ["birthday", "afk"],
    },
    # ── MODERATION ────────────────────────────────────────────────────────────
    "ban": {
        "name": "ban",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Permanently ban a member from the server",
        "usage": ["n!ban <member> [reason] [delete_messages]", "/ban <member> [reason] [delete_messages]"],
        "examples": [
            "n!ban @Alex spamming",
            "n!ban @Alex",
            "/ban member:@Alex reason:Raiding delete_messages:1",
        ],
        "notes": [
            "Shows a **confirmation embed** before acting — you must click ✅ to proceed",
            "DMs the banned user before banning them",
            "`delete_messages` = how many days of their messages to delete (0–7, default 0)",
            "Requires **Ban Members** permission",
            "Bot role must be higher than the target's top role",
        ],
        "related": ["tempban", "kick", "mute"],
    },
    "tempban": {
        "name": "tempban",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Temporarily ban a member — auto-unbanned when time expires",
        "usage": ["n!tempban <member> <duration> [reason]", "/tempban <member> <duration> [reason]"],
        "examples": [
            "n!tempban @Alex 1d breaking rules",
            "n!tempban @Alex 2h",
            "/tempban member:@Alex duration:30m reason:Spamming",
        ],
        "notes": [
            "Duration format: `30m` `2h` `1d` `1h30m` `7d` — combine units freely",
            "Maximum duration: **365 days**",
            "Shows a **confirmation embed** before acting",
            "DMs the user with the duration and reason before banning",
            "Requires **Ban Members** permission",
        ],
        "related": ["ban", "kick", "mute"],
    },
    "kick": {
        "name": "kick",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Kick a member from the server (they can rejoin with an invite)",
        "usage": ["n!kick <member> [reason]", "/kick <member> [reason]"],
        "examples": [
            "n!kick @Alex being disruptive",
            "/kick member:@Alex reason:Ignoring warnings",
        ],
        "notes": [
            "⚠️ **n!kick** is the mod command — use **n!kicks** for the GIF command",
            "The confirmation embed shows a reminder about this before acting",
            "Kicked members **can rejoin** — use `n!ban` to prevent that",
            "DMs the member before kicking",
            "Requires **Kick Members** permission",
        ],
        "related": ["ban", "tempban", "mute"],
    },
    "mute": {
        "name": "mute",
        "aliases": ["timeout", "silence"],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Timeout a member — they cannot talk, react, or join VCs",
        "usage": ["n!mute <member> <duration> [reason]", "/mute <member> <duration> [reason]"],
        "examples": [
            "n!mute @Alex 10m calm down",
            "n!mute @Alex 2h spamming",
            "/mute member:@Alex duration:30m",
        ],
        "notes": [
            "Uses Discord's **native timeout** — no mute role needed",
            "Maximum: **28 days** (Discord hard limit)",
            "Duration: `10m` `2h` `1d` etc.",
            "Shows a **confirmation embed** before acting",
            "DMs the muted member with duration and reason",
            "Requires **Moderate Members** permission",
            "Use `n!unmute` to remove early",
        ],
        "related": ["unmute", "ban", "kick"],
    },
    "unmute": {
        "name": "unmute",
        "aliases": ["untimeout"],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Remove a timeout from a member early",
        "usage": ["n!unmute <member> [reason]", "/unmute <member> [reason]"],
        "examples": [
            "n!unmute @Alex calmed down",
            "/unmute member:@Alex reason:Appeal accepted",
        ],
        "notes": [
            "No confirmation required — unmuting is a safe action",
            "DMs the member to let them know",
            "Requires **Moderate Members** permission",
        ],
        "related": ["mute", "ban", "kick"],
    },


    # ── PREMIUM ───────────────────────────────────────────────────────────────
    "premium": {
        "name": "premium",
        "aliases": [],
        "category": "premium",
        "premium": False,
        "admin": False,
        "description": "Check this server's premium status and expiry",
        "usage": ["n!premium", "/premium"],
        "examples": ["n!premium", "/premium"],
        "notes": [
            "Shows tier, expiry date, vanity slot count, and who purchased it",
            "Works in any server — shows FREE if not subscribed",
            "Use `n!premium_price` to see upgrade options",
        ],
        "related": ["premium_price", "vanity"],
    },
    "premium_price": {
        "name": "premium_price",
        "aliases": ["plans", "upgrade"],
        "category": "premium",
        "premium": False,
        "admin": False,
        "description": "Show Nexora premium plans and pricing",
        "usage": ["n!premium_price", "/premium_price"],
        "examples": ["n!premium_price", "/plans"],
        "notes": [
            "Plans: **BASIC** $4.99/mo · **PRO** $12.99/mo · **ENTERPRISE** $29.99/mo · **CUSTOM** negotiated",
            "Contact the bot owner to subscribe",
            "Yearly pricing available for savings",
        ],
        "related": ["premium", "vanity"],
    },
    "vanity": {
        "name": "vanity",
        "aliases": [],
        "category": "premium",
        "premium": True,
        "admin": False,
        "description": "View this server's vanity role configuration",
        "usage": ["n!vanity", "/vanity"],
        "examples": ["n!vanity"],
        "notes": [
            "👑 **Premium only** — requires BASIC tier or above",
            "Shows configured keyword → role mappings and slots used",
            "BASIC: 5 slots · PRO: 20 slots · ENTERPRISE/CUSTOM: Unlimited",
            "Vanity roles are auto-assigned when a member's status contains the keyword",
        ],
        "related": ["premium", "premium_price"],
    },
}

# ── Category metadata ──────────────────────────────────────────────────────────
CATEGORIES = {
    "utility":    {"emoji": "🔧", "label": "Utility",    "desc": "AFK, birthday, and other utilities"},
    "fun":        {"emoji": "🎮", "label": "Fun",         "desc": "Reaction and fun commands"},
    "info":       {"emoji": "ℹ️",  "label": "Info",        "desc": "Server, user, and bot info"},
    "moderation": {"emoji": "🛡️", "label": "Moderation", "desc": "Mod tools"},
    "games":      {"emoji": "🎲", "label": "Games",       "desc": "Games and activities"},
    "analytics":  {"emoji": "📊", "label": "Analytics",  "desc": "Server stats and exports"},
    "system":     {"emoji": "⚙️", "label": "System",     "desc": "Thread and guideline system"},
    "premium":    {"emoji": "👑", "label": "Premium",    "desc": "Premium features"},
    "owner":      {"emoji": "🔑", "label": "Owner",      "desc": "Owner-only commands"},
}

# ── Search / suggestion helpers ────────────────────────────────────────────────

def search_commands(query: str, limit: int = 5, registry: dict = None):
    """
    Fuzzy search over the live registry (COMMAND_DATA merged with auto-stubs).
    registry defaults to COMMAND_DATA if not passed.
    Scoring:
      100 exact name match
       90 alias match
       60 name starts-with
       30 name contains
       15 description contains
        5 notes contain keyword
    """
    src   = registry if registry is not None else COMMAND_DATA
    query = query.lower().strip()
    results = []
    for key, data in src.items():
        score = 0
        if query == key:                                              score += 100
        if query in (data.get("aliases") or []):                     score += 90
        if key.startswith(query):                                     score += 60
        if query in key:                                              score += 30
        if query in data.get("description", "").lower():             score += 15
        if any(query in n.lower() for n in data.get("notes", [])):   score += 5
        if score > 0:
            results.append((score, data))
    results.sort(key=lambda x: -x[0])
    return [r[1] for r in results[:limit]]

def get_related(command_name: str, limit: int = 4):
    data = COMMAND_DATA.get(command_name, {})
    related = data.get("related", [])
    suggestions = []
    for r in related[:limit]:
        if r in COMMAND_DATA:
            suggestions.append(COMMAND_DATA[r])
    return suggestions

# ── Embed builders ─────────────────────────────────────────────────────────────

def build_main_embed(bot) -> discord.Embed:
    p = prefix(bot)
    embed = discord.Embed(
        title="🌌 Nexora Help Center",
        description=(
            f"**Prefix:** `{p}` · **Slash:** `/`\n"
            f"`{p}help <command>` or `/help <command>` for detailed help on any command\n"
            f"Use the **dropdown** to browse a category or **Search** to find a command\n\u200b"
        ),
        color=cfg_color(bot, "embed_color"),
    )
    # Use live registry if available (auto-synced from loaded cogs)
    registry = getattr(bot, "_help_registry", COMMAND_DATA)
    by_cat = {}
    for data in registry.values():
        by_cat.setdefault(data["category"], []).append(data)

    for cat_key, cat_data in CATEGORIES.items():
        cmds = by_cat.get(cat_key, [])
        if not cmds: continue
        free_cmds    = [d for d in cmds if not d.get("premium")]
        premium_cmds = [d for d in cmds if d.get("premium")]
        lines = []
        if free_cmds:
            lines.append(" ".join(f"`{d['name']}`" for d in free_cmds))
        if premium_cmds:
            lines.append("👑 " + " ".join(f"`{d['name']}`" for d in premium_cmds))
        embed.add_field(
            name=f"{cat_data['emoji']} {cat_data['label']} ({len(cmds)})",
            value="\n".join(lines) or "—",
            inline=True,
        )
    embed.set_footer(text=f"Nexora · {len(registry)} commands loaded · 👑 = Premium only")
    return embed


def build_command_embed(bot, data: dict) -> discord.Embed:
    p    = prefix(bot)
    prem = data.get("premium", False)
    adm  = data.get("admin", False)
    color = 0xFFD700 if prem else cfg_color(bot, "success_color", 0x57F287)

    # Badge line
    badges = []
    if prem: badges.append("👑 **Premium**")
    if adm:  badges.append("🛡️ **Requires Permission**")
    badge_line = "  ·  ".join(badges)

    cat     = CATEGORIES.get(data["category"], {})
    aliases = data.get("aliases", [])
    alias_str = "  ".join(f"`{a}`" for a in aliases) if aliases else "None"

    embed = discord.Embed(
        title=f"📖 /{data['name']}",
        description=(
            f"{badge_line + chr(10) if badge_line else ''}"
            f"> {data['description']}\n\u200b"
        ),
        color=color,
    )

    # Quick info row
    embed.add_field(name="📂 Category", value=f"{cat.get('emoji','')} {cat.get('label', data['category'])}", inline=True)
    embed.add_field(name="🔀 Aliases",  value=alias_str,                                                              inline=True)
    embed.add_field(name="🔒 Access",   value="👑 Premium" if prem else ("🛡️ Admin" if adm else "✅ Everyone"),       inline=True)

    # Usage — prefix version + slash version separately
    prefix_usage = [u for u in data["usage"] if u.startswith("n!")]
    slash_usage  = [u for u in data["usage"] if u.startswith("/")]
    usage_val = ""
    if prefix_usage: usage_val += "**Prefix**\n" + "\n".join(f"`{u}`" for u in prefix_usage) + "\n"
    if slash_usage:  usage_val += "\n**Slash**\n" + "\n".join(f"`{u}`" for u in slash_usage)
    embed.add_field(name="📌 Usage", value=usage_val.strip() or "—", inline=False)

    # Examples
    if data.get("examples"):
        ex = "\n".join(f"` ` `{e}`" for e in data["examples"])
        embed.add_field(name="💡 Examples", value=ex, inline=False)

    # Notes
    if data.get("notes"):
        notes = "\n".join(f"**›** {n}" for n in data["notes"])
        embed.add_field(name="📝 Tips & Notes", value=notes, inline=False)

    # Related
    related = get_related(data["name"])
    if related:
        rel = "  ".join(f"`/{r['name']}`  {CATEGORIES.get(r['category'],{}).get('emoji','')} *{r['description'][:40]}…*" for r in related)
        embed.add_field(name="🔗 See Also", value="\n".join(f"`/{r['name']}` — {r['description'][:55]}" for r in related), inline=False)

    if data.get("_auto_stub"):
        embed.set_footer(text="⚠ Auto-detected command — full docs coming soon · Nexora")
    else:
        embed.set_footer(text="Nexora · n!help or /help to browse all commands")
    return embed


def build_search_results_embed(bot, query: str, results: list) -> discord.Embed:
    if not results:
        embed = discord.Embed(
            title=f"🔍 No results for `{query}`",
            description=(
                "Try a shorter or different keyword.\n\n"
                "**Popular commands:** "
                + " ".join(f"`{n}`" for n in list(COMMAND_DATA)[:6])
            ),
            color=cfg_color(bot, "error_color", 0xED4245),
        )
        return embed

    embed = discord.Embed(
        title=f"🔍 Search results for `{query}`",
        description=f"Found **{len(results)}** result(s). Tap a command name below for details.\n\u200b",
        color=cfg_color(bot, "embed_color"),
    )
    for data in results:
        badges = ("👑 " if data.get("premium") else "") + ("🛡️ " if data.get("admin") else "")
        embed.add_field(
            name=f"{badges}`/{data['name']}`",
            value=f"{data['description']}\n`{data['usage'][0]}`",
            inline=False,
        )
    embed.set_footer(text="Use /help <command> for full details on any command")
    return embed


def build_category_embed(bot, cat_key: str) -> discord.Embed:
    cat = CATEGORIES.get(cat_key, {"emoji": "📂", "label": cat_key.title(), "desc": ""})
    embed = discord.Embed(
        title=f"{cat['emoji']} {cat['label']} Commands",
        description=cat["desc"] + "\n\u200b",
        color=cfg_color(bot, "embed_color"),
    )
    registry = getattr(bot, "_help_registry", COMMAND_DATA)
    cmds = [d for d in registry.values() if d["category"] == cat_key]
    if not cmds:
        embed.description = "No commands in this category yet."
        return embed
    for data in cmds:
        badges = ("👑 " if data.get("premium") else "") + ("🛡️ " if data.get("admin") else "")
        embed.add_field(
            name=f"{badges}`/{data['name']}`",
            value=f"{data['description']}\n`{data['usage'][0]}`",
            inline=False,
        )
    embed.set_footer(text=f"Use /help <command> for detailed help • {len(cmds)} commands in this category")
    return embed

# ── Views ──────────────────────────────────────────────────────────────────────

class HelpView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot     = bot
        self.user_id = user_id
        self.message = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Use `/help` to open your own help menu.", ephemeral=True)
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            if hasattr(item, "disabled"):
                item.disabled = True
        try:
            if self.message: await self.message.edit(view=self)
        except: pass

    @discord.ui.select(
        placeholder="📂 Browse a category...",
        options=[
            discord.SelectOption(label="🏠 Main Menu",    value="main"),
            discord.SelectOption(label="🔧 Utility",      value="utility",    description="AFK, Birthday, and more"),
            discord.SelectOption(label="🎮 Fun",           value="fun",        description="Reaction and fun commands"),
            discord.SelectOption(label="ℹ️ Info",           value="info",       description="Server, user, bot info"),
            discord.SelectOption(label="🛡️ Moderation",   value="moderation", description="Moderation tools"),
            discord.SelectOption(label="🎲 Games",         value="games",      description="Games and activities"),
            discord.SelectOption(label="📊 Analytics",     value="analytics",  description="Server stats"),
            discord.SelectOption(label="⚙️ System",        value="system",     description="Thread and guidelines"),
            discord.SelectOption(label="👑 Premium",       value="premium",    description="Premium features"),
        ],
        min_values=1, max_values=1
    )
    async def category_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.defer()
        val = select.values[0]
        if val == "main":
            embed = build_main_embed(self.bot)
        else:
            embed = build_category_embed(self.bot, val)
        await interaction.edit_original_response(embed=embed, view=self)

    @discord.ui.button(label="🔍 Search Command", style=discord.ButtonStyle.blurple)
    async def search_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SearchModal(self.bot))

    @discord.ui.button(label="🏠 Home", style=discord.ButtonStyle.grey)
    async def home_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = build_main_embed(self.bot)
        await interaction.edit_original_response(embed=embed, view=self)


class SearchModal(discord.ui.Modal, title="🔍 Search Commands"):
    query = discord.ui.TextInput(
        label="Command name or keyword",
        placeholder="e.g. birthday, afk, set...",
        max_length=40,
        min_length=2,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        registry = getattr(self.bot, "_help_registry", COMMAND_DATA)
        results = search_commands(self.query.value, registry=registry)
        embed   = build_search_results_embed(self.bot, self.query.value, results)

        # If exact match — show full detail directly
        exact = registry.get(self.query.value.lower().strip())
        if exact:
            embed = build_command_embed(self.bot, exact)

        view = SearchResultView(self.bot, interaction.user.id, results)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)


class SearchResultView(discord.ui.View):
    """Appears after a search — buttons for each result to drill into detail"""
    def __init__(self, bot, user_id: int, results: list):
        super().__init__(timeout=120)
        self.bot     = bot
        self.user_id = user_id
        for data in results[:5]:
            label = f"/{data['name']}"
            if data.get("_auto_stub"):
                label += "  ·  undocumented"
            btn = discord.ui.Button(
                label=label[:80],
                style=discord.ButtonStyle.grey,
                custom_id=f"cmd_{data['name']}"
            )
            btn.callback = self._make_callback(data)
            self.add_item(btn)

    def _make_callback(self, data):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.user_id:
                return await interaction.response.send_message("❌ Not your search.", ephemeral=True)
            embed = build_command_embed(self.bot, data)
            await interaction.response.edit_message(embed=embed, view=self)
        return callback

# ── Cog ────────────────────────────────────────────────────────────────────────

# ── Category guesser for auto-stubs ───────────────────────────────────────────

def _guess_category(cmd: commands.Command) -> str:
    """Guess category from cog name / module path."""
    cog = cmd.cog
    if cog:
        cog_name = type(cog).__name__.lower()
        module   = (getattr(cog, "__module__", "") or "").lower()
        for key in ("moderation", "mod", "admin"):
            if key in cog_name or key in module: return "moderation"
        for key in ("fun", "game", "ship", "react"):
            if key in cog_name or key in module: return "fun"
        for key in ("info", "stat", "user", "server"):
            if key in cog_name or key in module: return "info"
        for key in ("analytic", "export", "log"):
            if key in cog_name or key in module: return "analytics"
        for key in ("system", "thread", "guide"):
            if key in cog_name or key in module: return "system"
        for key in ("premium", "boost"):
            if key in cog_name or key in module: return "premium"
        for key in ("owner", "dev"):
            if key in cog_name or key in module: return "owner"
    return "utility"


def _make_stub(cmd: commands.Command) -> dict:
    """Build a minimal COMMAND_DATA-style entry from a live command object."""
    p = "n!"
    name    = cmd.name
    aliases = list(cmd.aliases or [])
    desc    = cmd.description or cmd.help or "No description yet."
    # Trim discord's verbose help strings
    if len(desc) > 80:
        desc = desc[:77] + "…"
    usage = [f"n!{name}", f"/{name}"]
    return {
        "name":        name,
        "aliases":     aliases,
        "category":    _guess_category(cmd),
        "premium":     False,
        "admin":       False,
        "description": desc,
        "usage":       usage,
        "examples":    [],
        "notes":       ["Full documentation coming soon."],
        "related":     [],
        "_auto_stub":  True,   # flag so we know this was auto-generated
    }


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """
        Merge COMMAND_DATA with all currently loaded bot commands.
        Commands already documented in COMMAND_DATA keep their full docs.
        Undocumented commands get an auto-generated stub so they show up
        in search and category lists immediately.
        """
        self._sync_registry()
        logger.info("Help registry synced: %d commands", len(self.bot._help_registry))

    def _sync_registry(self):
        registry = dict(COMMAND_DATA)  # start from static docs

        skip = {"help", "h", "cmds", "commands"}  # don't stub the help command itself

        for cmd in self.bot.commands:
            name = cmd.name
            if name in skip or name in registry:
                continue
            registry[name] = _make_stub(cmd)
            # also index aliases so searches hit them
            for alias in (cmd.aliases or []):
                if alias not in registry:
                    stub = _make_stub(cmd)
                    stub["name"] = alias
                    # don't double-list in the UI — point back to canonical
                    stub["related"] = [name]
                    registry[alias] = stub

        self.bot._help_registry = registry

    async def cog_unload(self):
        # Clean up so it doesn't linger with stale data
        if hasattr(self.bot, "_help_registry"):
            del self.bot._help_registry

    @commands.hybrid_command(
        name="help",
        description="Get help for a command or browse all categories",
        aliases=["h", "cmds", "commands"]
    )
    @app_commands.describe(command="Command name to get detailed help for (leave blank for main menu)")
    async def help(self, ctx: commands.Context, *, command: Optional[str] = None):
        """
        Get detailed help for any command, or browse by category.
        Works as both n!help and /help.

        Examples:
          /help
          /help setbirthday
          /help afk
          n!help birthday
        """
        if command:
            query    = command.lower().strip()
            registry = getattr(self.bot, "_help_registry", COMMAND_DATA)

            # Exact match
            data = registry.get(query)
            # Alias match
            if not data:
                for d in registry.values():
                    if query in (d.get("aliases") or []):
                        data = d
                        break
            # Fuzzy match
            if not data:
                results = search_commands(query, limit=5, registry=registry)
                if results:
                    if len(results) == 1:
                        data = results[0]
                    else:
                        # Show search results with buttons
                        embed = build_search_results_embed(self.bot, query, results)
                        view  = SearchResultView(self.bot, ctx.author.id, results)
                        msg   = await ctx.send(embed=embed, view=view)
                        return
                else:
                    embed = build_search_results_embed(self.bot, query, [])
                    return await ctx.send(embed=embed)

            embed = build_command_embed(self.bot, data)
            view  = HelpView(self.bot, ctx.author.id)
            msg   = await ctx.send(embed=embed, view=view)
            view.message = msg
        else:
            embed = build_main_embed(self.bot)
            view  = HelpView(self.bot, ctx.author.id)
            msg   = await ctx.send(embed=embed, view=view)
            view.message = msg


async def setup(bot):
    await bot.add_cog(Help(bot))
    logger.info("Loaded Help")
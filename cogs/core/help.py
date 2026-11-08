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

# Components V2 support in this cog is written against the released 2.7.x API.
# Older 2.6 builds are intentionally rejected instead of failing later with
# opaque enum/serialization errors such as: int has no attribute 'value'.
try:
    _DPT = tuple(discord.version_info[:3])
except Exception:
    _DPT = tuple(int(x) for x in discord.__version__.split(".")[:3])

if _DPT < (2, 7, 1):
    raise RuntimeError(
        f"help.py requires discord.py >= 2.7.1 for its Components V2 UI; "
        f"detected {discord.__version__}. Upgrade with: "
        f"python -m pip install -U discord.py"
    )
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
    "help": {
        "name": "help",
        "aliases": ["h", "cmds", "commands"],
        "category": "info",
        "premium": False,
        "admin": False,
        "description": "Browse all commands by category or get detailed instructions for one command",
        "usage": [
            "n!help [command]",
            "/help [command]",
        ],
        "examples": [
            "n!help",
            "n!help afk",
            "/help",
            "/help birthdaywish",
        ],
        "notes": [
            "Leave the command name blank to open the interactive command browser",
            "Use /help <command> to see usage, examples, notes, and related commands",
            "Newly loaded commands are added to the browser automatically",
        ],
        "related": ["birthdayhelp", "birthdaywish"],
    },

    # ── BOT STATUS & TELEMETRY ─────────────────────────────────────────────────
    "status": {
        "name": "status",
        "aliases": ["stats", "botstatus", "cluster"],
        "category": "info",
        "premium": False,
        "admin": False,
        "description": "Open the interactive live status dashboard for hardware, network, games, and activity telemetry",
        "usage": [
            "n!status",
            "n!stats",
            "n!botstatus",
            "n!cluster",
            "/status",
        ],
        "examples": [
            "n!status",
            "/status",
        ],
        "notes": [
            "Four interactive tabs: **Hardware**, **Network**, **Games & Fun**, and **Activities**",
            "Hardware shows CPU load, system RAM, bot-process memory, worker threads, platform, Python, and discord.py version",
            "Network shows server/member/channel counts, gateway latency, messages processed, commands executed, and recorded incidents",
            "Games & Fun shows supported games, recorded match totals, currently AFK members, and multiplayer/party activity",
            "Activities shows the bot's presence mode, activity pool, prefixes, and Components V2 information",
            "Use the tab buttons to switch views; **Refresh** updates the dashboard and **Dismiss** closes it",
            "Prefix aliases: `n!stats`, `n!botstatus`, and `n!cluster`. The slash command is `/status`",
        ],
        "related": ["ping", "botinfo", "gamesstats", "premium"],
    },
    "ping": {
        "name": "ping",
        "aliases": [],
        "category": "info",
        "premium": False,
        "admin": False,
        "description": "Check Nexora's gateway latency and WebSocket heartbeat",
        "usage": [
            "n!ping",
            "/ping",
        ],
        "examples": [
            "n!ping",
            "/ping",
        ],
        "notes": [
            "Displays the current WebSocket gateway ping in milliseconds with a latency badge and meter",
            "Shows gateway connection state and the active shard indicator",
            "Use **Re-ping** to refresh the latency reading",
            "Use `/status` for the full hardware, network, games, and presence dashboard",
        ],
        "related": ["status", "botinfo"],
    },

    # ── QUOTE SYSTEM ─────────────────────────────────────────────────────────────
    "quote": {
        "name": "quote",
        "aliases": ["q"],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Create a high-fidelity atmospheric quote card with message jump link",
        "usage": [
            "n!quote",
            "n!quote <message_link>",
            "/quote [message_link]",
            "/quote channel [channel]",
            "/quote settings",
            "/quote toggle [enabled]",
            "/quote exclude <channel>",
            "/quote logchannel [channel]",
        ],
        "examples": [
            "n!quote (while replying to a message)",
            "n!quote https://discord.com/channels/123/456/789",
            "/quote message_link: https://discord.com/channels/123/456/789",
            "/quote channel #quotes",
            "/quote settings",
        ],
        "notes": [
            "Right-click or long-press any message ➔ **Apps** ➔ **Quote Message** for instant 1-click quoting",
            "Generates a sleek dark quote card featuring author avatar, quote text, and original jump link",
            "Supports custom Discord emojis (`<:name:id>` / `<a:name:id>`) and full Unicode color emojis",
            "Jumbo emoji mode automatically renders custom emojis in large display when no text is present",
            "Automatically strips messy URLs, GIF links, and raw attachment links, cleanly embedding media",
            "Each quote card features an interactive **[ 🗑️ Remove my Quote ]** button",
            "Only the quote creator or server moderators can remove quote cards",
            "Admins can set the target channel using `/quote channel #quotes`",
            "Mention suppression protects against unintended @everyone or role pings",
        ],
        "related": ["status", "help"],
    },

    # ── BIRTHDAY ──────────────────────────────────────────────────────────────
    "setbirthday": {
        "name": "setbirthday",
        "aliases": ["bdayset"],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Set your birthday with interactive dropdowns or date input for 00:00 midnight announcements",
        "usage": [
            "n!setbirthday [date] [year]",
            "/setbirthday [date] [year]",
        ],
        "examples": [
            "/setbirthday",
            "n!setbirthday",
            "n!setbirthday 15/04",
            "n!setbirthday 15/04/2001",
            "n!setbirthday April 15",
            "/setbirthday 15/04 2001",
        ],
        "notes": [
            "Run `/setbirthday` with no arguments to open the interactive **Birthday Studio** with Month & Day selectors!",
            "Accepted text formats: `15/04`, `04/15`, `15-04-2001`, `15.04`, `April 15`, `15 April`",
            "Announces automatically at **00:00 midnight** in your server's configured local UTC timezone",
            "If a numeric date is ambiguous (e.g. `05/06`), interactive confirmation buttons appear",
            "Includes quick buttons to customize your wish style (`/birthdaywish`) and view your profile",
        ],
        "related": ["birthday", "birthdaylist", "birthdaywish", "introbdsetup", "myprofile"],
    },
    "birthday": {
        "name": "birthday",
        "aliases": ["bday"],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "View your or another user's birthday, zodiac sign, live countdown, and action buttons",
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
            "Leave `user` blank to check your own birthday card",
            "Shows formatted date, zodiac sign, live days countdown, and turning age (if birth year was set)",
            "Includes quick interactive buttons to set/update your birthday, customize wish messages, or browse upcoming birthdays",
            "On the birthday itself, a 🎉 **Send Birthday Wish** button appears so members can send wishes",
        ],
        "related": ["setbirthday", "birthdaylist", "birthdaywish", "myprofile"],
    },
    "birthdaylist": {
        "name": "birthdaylist",
        "aliases": [],
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
            "Entries are sorted by how soon the next birthday occurs",
            "🎂 = birthday is TODAY, 🎈 = upcoming",
            "Only shows members who have set their birthday with `/setbirthday`",
        ],
        "related": ["setbirthday", "birthday"],
    },
    "birthdayhelp": {
        "name": "birthdayhelp",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Open the interactive birthday system command guide",
        "usage": [
            "n!birthdayhelp",
            "/birthdayhelp",
        ],
        "examples": [
            "n!birthdayhelp",
            "/birthdayhelp",
        ],
        "notes": [
            "Interactive menu with Home, Free Commands, Premium Commands, and Admin Setup sections",
            "The guide explains the automatic intro parser and birthday announcement system",
            "Available to everyone",
        ],
        "related": ["setbirthday", "birthday", "birthdaylist", "introbdsetup"],
    },

    "editbirthday": {
        "name": "editbirthday",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Fix your birthday if it was parsed wrong",
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
            "This correction command is FREE — premium is not required",
            "Year is optional — only needed for age display",
            "Use this if the intro parser got your date wrong",
        ],
        "related": ["setbirthday", "editprofile", "myprofile"],
    },
    "editprofile": {
        "name": "editprofile",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Update your name, age, or pronouns from your intro",
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
            "This profile correction command is FREE — premium is not required",
            "This edits what the bot parsed from your #introductions message",
            "Changes are shown in `/myprofile` and on your birthday announcement",
        ],
        "related": ["myprofile", "editbirthday", "setbirthday"],
    },
    "myprofile": {
        "name": "myprofile",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "View your full birthday & intro profile",
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
            "Profile viewing, corrections, custom wishes, and DM preferences are all free",
            "Only visible to you (ephemeral — hidden from others)",
            "Use `/editprofile` or `/editbirthday` to change anything",
        ],
        "related": ["editprofile", "editbirthday", "birthdaywish"],
    },
    "poll": {
        "name": "poll",
        "aliases": ["quickpoll"],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Create an interactive poll with 2 to 6 options and live voting progress bars",
        "usage": [
            "n!poll <question> | <opt1> | <opt2> [| opt3...]",
            "/poll <question> <option1> <option2> [option3] [option4] [option5] [option6] [duration]",
        ],
        "examples": [
            "/poll question:Favorite Season? option1:Summer option2:Winter option3:Spring option4:Autumn",
            "/poll question:Pizza or Burger? option1:Pizza option2:Burger duration:1h",
            "n!poll Best Game? | Minecraft | Elden Ring | Valorant",
            "n!quickpoll Do you like pineapple on pizza?",
        ],
        "notes": [
            "Minimum **2 options required** (`option1` and `option2`), Maximum **6 options** supported",
            "Real-time Unicode progress bars update on every community vote",
            "Click an option button to vote or tap again to switch/retract your vote",
            "Optional auto-close timer (e.g. `10m`, `1h`, `1d`)",
            "Poll creator or staff can click 🛑 **End Poll** to finalize and declare the winner",
        ],
        "related": ["remind", "wyr", "tod"],
    },
    "birthdaywish": {
        "name": "birthdaywish",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Customize birthday announcement format and edit normal-message and embed-card text separately",
        "usage": [
            "n!birthdaywish",
            "/birthdaywish",
            "n!birthdaywish <embed text>",
            "/birthdaywish <embed text>",
        ],
        "examples": [
            "/birthdaywish",
            "/birthdaywish {mention} just leveled up in real life! 🎂",
            "n!birthdaywish It's {name}'s special day — shower them with love! 💕",
        ],
        "notes": [
            "Choose Embed only, Normal message only, or Both message and embed",
            "Click Customize message + embed to write different text for the normal message and the embed card",
            "Use {mention} to mention the birthday person and {name} to insert their display name",
            "The optional command argument customizes the embed-card text (maximum 200 characters)",
            "Your chosen format and custom texts are saved to your profile in this server",
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
        "premium": False,
        "admin": False,
        "description": "Choose whether birthday wishes send you a DM",
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
        "aliases": ["bdaysetup", "birthdaysetup"],
        "category": "utility",
        "premium": False,
        "admin": True,
        "description": "Admin — Interactive Birthday & Intro Setup Studio (channels, 00:00 timezone, role & mention pings)",
        "usage": [
            "n!bdaysetup",
            "n!introbdsetup [intro_channel] [announce_channel] [birthday_role] [timezone_offset]",
            "/introbdsetup [intro_channel] [announce_channel] [birthday_role] [timezone_offset]",
        ],
        "examples": [
            "/introbdsetup",
            "n!bdaysetup",
            "/introbdsetup intro_channel:#introductions announce_channel:#birthdays birthday_role:@🎂Birthday timezone_offset:UTC+05:30",
        ],
        "notes": [
            "Run `/introbdsetup` or `n!bdaysetup` with no arguments to open the **Interactive Birthday Setup Studio**",
            "Configure your server's **UTC Timezone Offset** (e.g. `UTC+05:30`, `UTC+00:00`, `UTC-05:00`) so birthdays announce right at **00:00 midnight** local server time!",
            "Includes dropdown selectors for Intro Channel, Announcement Channel, Birthday Role, Ping Role, and UTC Timezone",
            "Includes a **🧪 Test Announcement** button to preview how birthday pings and cards look in your channel",
            "3-layer duplicate guard ensures each member's birthday is announced only once per calendar day",
            "Requires **Manage Server** permission",
        ],
        "related": ["scanintros", "setbirthday", "birthday", "birthdaylist"],
    },
    "scanintros": {
        "name": "scanintros",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": True,
        "description": "Admin — Scan past intro messages to import birthday data",
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
            "Free: scans up to 100 messages. Premium increases the limit to 1,000",
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
            "When someone mentions you, the bot replies directly to the user mentioning you with your AFK reason and away time",
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
        "description": "Ship two people together and see their love compatibility 💘 (Works in Servers, DMs & Group DMs)",
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
            "Works anywhere on Discord — Servers, 1-on-1 DMs, and Group DMs!",
            "No args = ships you with a random server/group member (or with Nexora in 1-on-1 DMs)",
            "One arg = ships you with that person; Both args = ships those two people together",
            "Use `random` as either arg to pick a random member",
            "Plain text names work too — e.g. `n!ship Alex Blake` (no @mention needed)",
            "Results are **consistent** — the same pair always gets the same % (hash-based)",
            "Use 🔁 **Re-roll** for a random result that changes each time",
            "8 tiers: 💔 Disaster → 🤍 Lukewarm → 💛 Neutral → 💓 Promising → 💕 Great Vibes → 💖 Perfect Match → 💞 SOULMATES",
            "❤️ **React** button counts how many people react to the ship; 🔗 **Share** posts publicly",
        ],
        "related": ["vibe", "compliment", "tod"],
    },
    "tod": {
        "name": "tod",
        "aliases": ["truthordare"],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Play the combined interactive Truth or Dare game solo or challenge a friend",
        "usage": [
            "n!tod [target] [rating]",
            "/tod [target] [rating]",
        ],
        "examples": [
            "n!tod",
            "n!tod @Alex",
            "/tod target:@Alex rating:spicy",
            "/tod rating:pg",
        ],
        "notes": [
            "Use `/truth` or `/dare` to start with only one type of prompt, or use this combined command",
            "Features **720+ unique, curated prompts** across all tiers: `pg` (Warm-Up), `teen` (Chaos), and `spicy` (High Stakes)",
            "Prompts cover psychological dilemmas, debate hot takes, gaming culture, real-life quirks, and bold Discord dares—moving beyond repetitive couple/romance questions",
            "Prompts do not repeat in the same session until that rating/type pool has been exhausted",
            "Interactive controls include Truth, Dare, Random, Switch, Another Prompt, Reroll, Complete, and Forfeit",
            "Play solo or challenge a friend; multiplayer challenges include turn notifications and response/forfeit controls",
            "Spicy prompts are bold, thought-provoking, and challenging rather than cringy or explicit; players can pass or reroll if needed",
        ],
        "related": ["truth", "dare", "wyr", "meme", "rps"],
    },
    "truth": {
        "name": "truth",
        "aliases": [],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Start Truth or Dare with a truth prompt only, solo or against a friend",
        "usage": [
            "n!truth [target] [rating]",
            "/truth [target] [rating]",
        ],
        "examples": [
            "n!truth",
            "n!truth @Alex spicy",
            "/truth",
            "/truth target:@Alex rating:spicy",
        ],
        "notes": [
            "Starts the session with a Truth prompt; use the in-game controls to keep playing",
            "Content tiers: `pg` (Warm-Up), `teen` (Chaos), and `spicy` (bold truth prompts); default is `teen`",
            "Leave `target` empty to play solo, or select a member to challenge",
            "Available as both a prefix command and a slash command",
        ],
        "related": ["tod", "dare", "wyr"],
    },
    "dare": {
        "name": "dare",
        "aliases": [],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Start Truth or Dare with a dare prompt only, solo or against a friend",
        "usage": [
            "n!dare [target] [rating]",
            "/dare [target] [rating]",
        ],
        "examples": [
            "n!dare",
            "n!dare @Alex spicy",
            "/dare",
            "/dare target:@Alex rating:spicy",
        ],
        "notes": [
            "Starts the session with a Dare prompt; use the in-game controls to keep playing",
            "Content tiers: `pg` (Warm-Up), `teen` (Chaos), and `spicy` (bold/flirty dares); default is `teen`",
            "Leave `target` empty to play solo, or select a member to challenge",
            "Available as both a prefix command and a slash command",
        ],
        "related": ["tod", "truth", "wyr"],
    },
    "wyr": {
        "name": "wyr",
        "aliases": ["wouldyourather"],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Vote on impossible, hilarious, thought-provoking dilemmas",
        "usage": [
            "n!wyr",
            "/wyr",
        ],
        "examples": [
            "n!wyr",
            "/wyr",
        ],
        "notes": [
            "100+ crazy, deep, and hilarious dilemmas",
            "Interactive buttons: 🔵 Option A vs 🔴 Option B",
            "Live Unicode percentage progress bars updating on each community vote",
            "Click ➡️ Next Dilemma to load new dilemmas non-stop!",
        ],
        "related": ["tod", "poll"],
    },
    "meme": {
        "name": "meme",
        "aliases": [],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Stream fresh, top-upvoted memes directly from Reddit",
        "usage": [
            "n!meme [category]",
            "/meme [category]",
        ],
        "examples": [
            "n!meme",
            "n!meme dank",
            "/meme category:programmer",
            "/meme category:wholesome",
        ],
        "notes": [
            "Categories: `dank` (r/dankmemes), `memes` (r/memes), `wholesome`, `me_irl`, `programmer`",
            "Displays high-res preview, upvotes (👍), and comment counts",
            "Click 🔄 **Next Meme** for instant seamless browsing without re-running the command",
        ],
        "related": ["tod", "wyr"],
    },
    "pp": {
        "name": "pp",
        "aliases": [],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Completely random fake measurement scanner 💀",
        "usage": [
            "n!pp [@user]",
            "/pp [user]",
        ],
        "examples": [
            "n!pp",
            "n!pp @Alex",
            "/pp user:@Alex",
        ],
        "notes": [
            "Generates a ridiculous ASCII scale (8====D) and length in inches & cm",
            "Ranks subject from Quantum Particle to Mythical Leviathan with Aura stats",
            "Click 🎲 **Measure Again** for instant rerolls",
        ],
        "related": ["iq", "vibe"],
    },
    "iq": {
        "name": "iq",
        "aliases": [],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Neural diagnostic: Random IQ score & hilarious evaluation",
        "usage": [
            "n!iq [@user]",
            "/iq [user]",
        ],
        "examples": [
            "n!iq",
            "n!iq @Alex",
            "/iq user:@Alex",
        ],
        "notes": [
            "Random IQ score from 15 to 350 across 7 hilarious tiers",
            "Displays neural breakdown: Logic %, Common Sense %, and Raw Chaos %",
            "Click 🧠 **Retest Brain** to run another diagnostic",
        ],
        "related": ["pp", "vibe", "npc"],
    },
    "vibe": {
        "name": "vibe",
        "aliases": [],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Daily solo vibe check or Duo compatibility dynamic",
        "usage": [
            "n!vibe [@user]",
            "/vibe [user]",
        ],
        "examples": [
            "n!vibe",
            "n!vibe @Alex",
            "/vibe user:@Alex",
        ],
        "notes": [
            "Solo mode: reveals daily animal vibe (87% Raccoon, Capybara, Void Cat, etc.)",
            "Duo mode (@user): tests chemistry and reveals your duo archetype (Soulbound Chaos Twins, Menace Duo, etc.)",
            "Click 🔄 **Recalculate Vibe** to reroll frequencies",
        ],
        "related": ["fortune", "compliment", "tod"],
    },
    "fortune": {
        "name": "fortune",
        "aliases": [],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Reveals an ominous, hilarious, and cursed fortune",
        "usage": [
            "n!fortune [@user]",
            "/fortune [user]",
        ],
        "examples": [
            "n!fortune",
            "n!fortune @Alex",
            "/fortune user:@Alex",
        ],
        "notes": [
            "Draws a cursed prophecy card from the crystal ball with survival tips",
            "Includes dubious lucky charm and supernatural danger rating",
            "Click 🔮 **Another Prophecy** to draw again",
        ],
        "related": ["vibe", "npc"],
    },
    "npc": {
        "name": "npc",
        "aliases": [],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Transforms a user or message into an RPG NPC dialogue box",
        "usage": [
            "n!npc [message]",
            "n!npc @user [message]",
            "/npc [message] [user]",
        ],
        "examples": [
            "n!npc",
            "n!npc Do you get to the Cloud District very often?",
            "/npc message:I have an urgent quest for you! user:@Alex",
        ],
        "notes": [
            "Turns custom or random messages into classic retro RPG dialogue boxes",
            "Displays NPC level, speaker, quest rewards (XP, Gold), and dialogue choices",
            "Interactive buttons: ⚔️ Accept Quest, 💰 Bribe (50g), 🚫 Decline/Flee",
        ],
        "related": ["vibe", "fortune"],
    },
    "compliment": {
        "name": "compliment",
        "aliases": [],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Send a wholesome, heartwarming compliment to someone",
        "usage": [
            "n!compliment [@user]",
            "/compliment [user]",
        ],
        "examples": [
            "n!compliment",
            "n!compliment @Alex",
            "/compliment user:@Alex",
        ],
        "notes": [
            "Sends heartwarming, witty, and genuine compliments in a soft rose card",
            "Great for cheering up friends and spreading positive server vibes",
            "Click 💖 **Another Compliment** to send more love",
        ],
        "related": ["vibe", "tod"],
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
    "unban": {
        "name": "unban",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Lift a ban for a user by ID or tag",
        "usage": ["n!unban <user> [reason]", "/unban <user> [reason]"],
        "examples": ["n!unban 123456789012345678 appeal accepted", "/unban user:123456789012345678"],
        "notes": [
            "Accepts User IDs or username tags",
            "Logs unban confirmation card with executor audit trail",
            "Requires **Ban Members** permission",
        ],
        "related": ["ban", "softban"],
    },
    "softban": {
        "name": "softban",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Bans and immediately unbans to purge recent messages and kick",
        "usage": ["n!softban <member> [reason] [delete_messages]", "/softban <member> [reason] [delete_messages]"],
        "examples": ["n!softban @Spammer raid cleanup", "/softban member:@Spammer delete_messages:1"],
        "notes": [
            "Scrubs messages without permanently keeping the user banned",
            "DMs the offender before actioning",
            "Requires **Ban Members** and **Kick Members** permissions",
        ],
        "related": ["ban", "kick", "purge"],
    },
    "purge": {
        "name": "purge",
        "aliases": ["clear", "clean"],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Bulk delete messages with multi-filtering and auto-cleanup",
        "usage": [
            "n!purge [amount] [filters...]",
            "/purge [amount] [user] [bots] [contains] [links] [attachments] [pinned]",
        ],
        "examples": [
            "n!purge 20",
            "n!purge 50 user:@Spammer",
            "/purge amount:25 bots:True",
            "/purge amount:100 links:True",
        ],
        "notes": [
            "Supports scanning and clearing up to 1,000 messages",
            "Filter options: `user`, `bots`, `contains`, `links`, `attachments`, and `pinned`",
            "Summary card automatically self-destructs after 5 seconds to leave chat spotless",
            "Messages older than 14 days cannot be bulk-deleted per Discord limits",
            "Requires **Manage Messages** permission",
        ],
        "related": ["softban", "lock"],
    },
    "warn": {
        "name": "warn",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Issue an official infraction warning to a member",
        "usage": ["n!warn <member> <reason>", "/warn <member> <reason>"],
        "examples": ["n!warn @Alex Inappropriate language in general", "/warn member:@Alex reason:Spamming links"],
        "notes": [
            "Generates a unique Case ID (e.g. #A1B2C3)",
            "DMs the member a formal Components V2 warning card with guidelines notice",
            "Requires **Manage Messages** permission",
        ],
        "related": ["warnings", "delwarn", "clearwarns"],
    },
    "warnings": {
        "name": "warnings",
        "aliases": ["warns", "infractions"],
        "category": "moderation",
        "premium": False,
        "admin": False,
        "description": "View warning history and active infractions for a member",
        "usage": ["n!warnings [member]", "/warnings [member]"],
        "examples": ["n!warnings", "n!warnings @Alex", "/warnings member:@Alex"],
        "notes": [
            "Interactive Components V2 paginated card with Previous/Next buttons",
            "Displays Case ID, timestamp, moderator, and reason for each incident",
            "Members can view their own infractions without admin permissions",
        ],
        "related": ["warn", "delwarn", "clearwarns"],
    },
    "delwarn": {
        "name": "delwarn",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Delete a specific warning record by Case ID",
        "usage": ["n!delwarn <member> <case_id>", "/delwarn <member> <case_id>"],
        "examples": ["n!delwarn @Alex A1B2C3", "/delwarn member:@Alex case_id:A1B2C3"],
        "notes": [
            "Case IDs can be found by running `/warnings @member`",
            "Requires **Manage Messages** permission",
        ],
        "related": ["warn", "warnings", "clearwarns"],
    },
    "clearwarns": {
        "name": "clearwarns",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Clear all warning records for a member",
        "usage": ["n!clearwarns <member>", "/clearwarns <member>"],
        "examples": ["n!clearwarns @Alex", "/clearwarns member:@Alex"],
        "notes": [
            "Features interactive confirmation dialog before wiping records",
            "Requires **Moderate Members** permission",
        ],
        "related": ["warn", "warnings", "delwarn"],
    },
    "lock": {
        "name": "lock",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Lock down a channel to stop member messages",
        "usage": ["n!lock [channel] [reason]", "/lock [channel] [reason]"],
        "examples": ["n!lock", "n!lock #general Raid incoming", "/lock channel:#chat"],
        "notes": [
            "Overrides @everyone Send Messages permission",
            "Outputs high-visibility red lockdown notice",
            "Requires **Manage Channels** permission",
        ],
        "related": ["unlock", "slowmode"],
    },
    "unlock": {
        "name": "unlock",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Unlock a channel and restore chatting permissions",
        "usage": ["n!unlock [channel] [reason]", "/unlock [channel] [reason]"],
        "examples": ["n!unlock", "n!unlock #general Situation resolved", "/unlock channel:#chat"],
        "notes": [
            "Restores regular messaging permissions",
            "Outputs green unlock notice card",
            "Requires **Manage Channels** permission",
        ],
        "related": ["lock", "slowmode"],
    },
    "slowmode": {
        "name": "slowmode",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Set channel slowmode cooldown delay",
        "usage": ["n!slowmode <duration> [channel]", "/slowmode <duration> [channel]"],
        "examples": ["n!slowmode 5s", "n!slowmode 1m #general", "n!slowmode off"],
        "notes": [
            "Accepts human durations: `5s`, `10s`, `30s`, `1m`, `5m`, `1h`, `off`",
            "Interactive slash autocomplete for easy preset picking",
            "Maximum delay is 6 hours (21600 seconds)",
            "Requires **Manage Channels** permission",
        ],
        "related": ["lock", "unlock"],
    },
    "afkclear": {
        "name": "afkclear",
        "aliases": [],
        "category": "moderation",
        "premium": False,
        "admin": True,
        "description": "Moderator command to forcefully reset a user's AFK status",
        "usage": ["n!afkclear <member>", "/afkclear <member>"],
        "examples": ["n!afkclear @Alex"],
        "notes": [
            "Useful if a member sets an offensive AFK nickname or reason",
            "Requires **Manage Nicknames** permission",
        ],
        "related": ["afk", "unafk", "afkstatus"],
    },
    "remind": {
        "name": "remind",
        "aliases": ["remindme"],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Set a persistent scheduled reminder with human duration",
        "usage": ["n!remind <time> <reason>", "/remind <time> <reason>"],
        "examples": [
            "n!remind 30m Check the oven",
            "n!remind 2h Team meeting",
            "/remind time:1d reason:Submit homework",
        ],
        "notes": [
            "Supports: `10m`, `30m`, `1h`, `4h`, `1d`, `3d`, `1w`",
            "DMs you with a Components V2 card and Jump URL when due",
            "Falls back to channel ping if DMs are disabled",
            "Persistent across bot restarts via MongoDB",
        ],
        "related": ["reminders", "delreminder"],
    },
    "reminders": {
        "name": "reminders",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "List all your scheduled active reminders",
        "usage": ["n!reminders", "/reminders"],
        "examples": ["n!reminders", "/reminders"],
        "notes": [
            "Shows countdown, reminder ID, and reason for each reminder",
            "Use `/delreminder <id>` to cancel one",
        ],
        "related": ["remind", "delreminder"],
    },
    "delreminder": {
        "name": "delreminder",
        "aliases": ["unremind", "cancelreminder"],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Cancel a scheduled reminder by its ID",
        "usage": ["n!delreminder <id>", "/delreminder <id>"],
        "examples": ["n!delreminder A1B2C3", "/delreminder id:A1B2C3"],
        "notes": [
            "Reminder IDs can be checked via `/reminders`",
        ],
        "related": ["remind", "reminders"],
    },
    "quickpoll": {
        "name": "quickpoll",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Quick Yes/No interactive button poll",
        "usage": ["n!quickpoll <question>", "/quickpoll <question>"],
        "examples": ["n!quickpoll Should we open voice channel?", "/quickpoll question:Start movie now?"],
        "notes": [
            "Instant Yes 👍 and No 👎 polling card",
        ],
        "related": ["poll"],
    },
    "calc": {
        "name": "calc",
        "aliases": ["calculate", "math"],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Evaluate a math expression or open an interactive keypad",
        "usage": ["n!calc [expression]", "/calc [expression]"],
        "examples": [
            "n!calc",
            "n!calc 25 * 4 + 10",
            "/calc expression:sqrt(144) + 12",
        ],
        "notes": [
            "Leave expression blank to open the interactive on-screen button keypad!",
            "Safe AST evaluation — no code execution risk",
            "Supported: `+`, `-`, `*`, `/`, `^`, `%`, `sqrt`, `sin`, `cos`, `tan`, `log`, `pi`, `e`",
            "Works in Servers, DMs, and Group DMs",
        ],
        "related": [],
    },

    # ── PREMIUM ───────────────────────────────────────────────────────────────
    "premium": {
        "name": "premium",
        "aliases": [],
        "category": "premium",
        "premium": False,
        "admin": False,
        "description": "View Server Premium status, perks, quotas, expiry, and diagnostics",
        "usage": [
            "n!premium",
            "n!premium server",
            "n!premium user",
            "/premium",
            "/premium view:user",
        ],
        "examples": [
            "n!premium",
            "n!premium server",
            "n!premium user",
            "/premium",
            "/premium view:user",
        ],
        "notes": [
            "The direct `/premium` command opens this server's overview; choose view:user for your personal VIP dashboard",
            "The dashboard includes Overview, Perks, Diagnostics, plan comparison, slot quotas, and storage health",
            "Prefix users can run `n!premium`, `n!premium server`, or `n!premium user`",
            "Use `/premium_price` to view upgrade plans and available tiers",
            "The bot owner can grant a tier with `/premium_grant` or `n!set_premium <server_id> PRO 30`",
        ],
        "related": ["premium_price", "premium_grant", "vanity", "vip", "booster_role"],
    },
    "premium_grant": {
        "name": "premium_grant",
        "aliases": [],
        "category": "owner",
        "premium": False,
        "admin": True,
        "description": "Grant Server Premium to a guild (bot owner only)",
        "usage": [
            "/premium_grant <guild_id> <tier> <days>",
            "n!set_premium <server_id> <tier> <days>",
        ],
        "examples": [
            "/premium_grant guild_id:123456789012345678 tier:PRO days:30",
            "n!set_premium 123456789012345678 PRO 30",
            "n!set_premium 123456789012345678 GRANDFATHERED -1",
        ],
        "notes": [
            "Owner-only; tiers: BASIC, PRO, ENTERPRISE, CUSTOM, or GRANDFATHERED",
            "Use days=-1 for a permanent grant; GRANDFATHERED is permanent",
            "Requires MongoDB for database-backed perks such as vanity and booster role configuration; the command warns if MongoDB is unavailable",
            "Use `/premium` to verify the tier and open the Perks/Diagnostics dashboard",
        ],
        "related": ["premium", "premium_price"],
    },
    "say": {
        "name": "say",
        "aliases": ["echo"],
        "category": "owner",
        "premium": False,
        "admin": False,
        "description": "Broadcast or reply with messages, files, and media as Nexora (Owner Only)",
        "usage": [
            "n!say <text>",
            "n!say (while replying to a message)",
            "n!say <message_link/ID> <text>",
            "n!say #channel <text>",
            "n!say -ping <text>",
            "/say message:<text> [reply_to] [channel] [ping] [attachment]",
        ],
        "examples": [
            "n!say Hello server!",
            "n!say (while replying to any message in Discord)",
            "n!say https://discord.com/channels/123/456/789 Replying to this message",
            "n!say #announcements Update is live! (with image attachment)",
            "n!say -ping Thank you for participating!",
            "/say message:Hello everyone! channel:#general",
            "/say message:Got it! reply_to:123456789012345678 ping:True",
        ],
        "notes": [
            "🔒 **Owner Only**: Strictly restricted to the bot owner",
            "Discord Native Reply: click reply on any message and type `n!say <text>` to reply as Nexora",
            "Remote Reply: specify a message URL or 17-20 digit message ID to reply across channels",
            "Forward Attachments: attach images, GIFs, videos, or files in prefix or slash mode",
            "Stealth Execution: prefix invocation message auto-deletes immediately; slash responses are ephemeral",
            "Silent by Default: reply pings default to OFF; add `-ping` or set `ping: True` to ping the user",
            "Automatic Chunking: messages longer than 2,000 characters are automatically split into sequential messages",
        ],
        "related": ["status", "help"],
    },
    "premium_price": {
        "name": "premium_price",
        "aliases": ["plans", "upgrade"],
        "category": "premium",
        "premium": False,
        "admin": False,
        "description": "Show Server Premium & User VIP plans with live discount calculator",
        "usage": ["n!premium_price", "/premium_price"],
        "examples": ["n!premium_price", "/plans"],
        "notes": [
            "Server Plans: **BASIC** $4.99/mo · **PRO** $12.99/mo · **ENTERPRISE** $29.99/mo",
            "User VIP Plans: **VIP** $2.99/mo · **VIP PLUS** $7.99/mo (Includes Server Pass)",
            "Interactive toggle switches between Monthly and Annual (Save 20%) billing",
            "Instant activation via UPI / PayPal",
        ],
        "related": ["premium", "vanity", "vip"],
    },
    "vanity": {
        "name": "vanity",
        "aliases": [],
        "category": "premium",
        "premium": True,
        "admin": False,
        "description": "Manage automated vanity status roles and supporter leaderboard",
        "usage": ["n!vanity", "/vanity"],
        "examples": ["n!vanity", "/vanity"],
        "notes": [
            "👑 **Server Premium only** — requires Basic tier or above",
            "Members with your server link/tag in their status unlock custom roles automatically",
            "Includes live supporter leaderboard and celebratory log announcements",
            "Use `/vanity_sync` to perform an immediate server-wide audit sweep",
        ],
        "related": ["vanity_sync", "premium", "premium_price"],
    },
    "vanity_sync": {
        "name": "vanity_sync",
        "aliases": [],
        "category": "premium",
        "premium": True,
        "admin": True,
        "description": "Run an instant live sweep to award or revoke vanity status roles",
        "usage": ["n!vanity_sync", "/vanity_sync"],
        "examples": ["n!vanity_sync", "/vanity_sync"],
        "notes": [
            "👑 **Server Premium only**",
            "Scans all active presences and syncs vanity roles immediately",
            "Outputs execution duration, members scanned, and roles awarded/revoked",
            "Requires **Manage Roles** permission",
        ],
        "related": ["vanity", "premium"],
    },
    "vip": {
        "name": "vip",
        "aliases": [],
        "category": "premium",
        "premium": True,
        "admin": False,
        "description": "Manage personal cross-server VIP perks, custom colors, and badges",
        "usage": ["n!vip [color|badge|pass]", "/vip [color|badge|pass]"],
        "examples": ["n!vip", "/vip color #00D2FF", "/vip badge crown", "/vip pass 1072508777623990362"],
        "notes": [
            "⭐ **User VIP only** — perks follow you across every server!",
            "Customize the bot's embed accent color on all your commands",
            "Equip exclusive VIP badges on your profile and avatar cards",
            "VIP Plus subscribers can redeem Server Passes to grant Server Premium to any guild",
        ],
        "related": ["premium", "premium_price", "avatar"],
    },
    "booster_role": {
        "name": "booster_role",
        "aliases": [],
        "category": "premium",
        "premium": True,
        "admin": False,
        "description": "Create and customize your personal private booster role",
        "usage": ["n!booster_role [create|color|name|icon|delete]", "/booster_role [create|color|name|icon|delete]"],
        "examples": ["/booster_role create name:Valkyrie color:#FF1493", "/booster_role color #00D2FF", "/booster_role delete"],
        "notes": [
            "👑 **Server Premium only** — requires active Nitro Booster status in server",
            "Create your private role and customize color (hex or presets) and name",
            "Role is automatically positioned below the configured anchor role",
            "Auto-cleans if booster leaves or unboosts",
        ],
        "related": ["premium", "vanity"],
    },
    "autoresponder": {
        "name": "autoresponder",
        "aliases": ["ar", "autoreply", "custom_reply"],
        "category": "utility",
        "premium": False,
        "admin": True,
        "description": "Automated keyword responses, rich embeds, and triggers (10 Free slots for all servers)",
        "usage": [
            "n!autoresponder",
            "n!autoresponder add <trigger> <reply> [match_mode]",
            "n!autoresponder edit <id> [options]",
            "n!autoresponder remove <id>",
            "n!autoresponder show <id>",
            "n!autoresponder test <message>",
            "n!autoresponder duplicate <id>",
            "n!autoresponder settings",
            "n!autoresponder stats",
            "n!autoresponder help",
            "/autoresponder add trigger:<phrase> reply:<text> [match_mode]",
            "/autoresponder edit identifier:<id> [reply] [trigger]",
            "/autoresponder test message:<text>",
        ],
        "examples": [
            "/autoresponder",
            "/autoresponder add trigger:hello reply:Hey {user.mention}! Welcome to {server}! match_mode:contains",
            "/autoresponder add trigger:rules reply:Read <#123456789>! match_mode:exact reply_to:True",
            "/autoresponder test message:hello world",
            "/autoresponder stats",
            "n!ar list",
        ],
        "notes": [
            "🆓 **Free for all servers**: 10 autoresponder slots included for free (Basic: 25 slots, Pro: 50 slots, Enterprise: Unlimited)",
            "Match modes: `contains`, `exact`, `startswith`, `endswith`, `whole_word`, and `regex` (Pro Tier)",
            "Dynamic safe variables: `{user}`, `{user.mention}`, `{user.id}`, `{user.avatar}`, `{server}`, `{server.id}`, `{channel}`, `{channel.id}`, `{members}`, `{created_at}`, `{random:1-100}`",
            "Supports inline reaction tags: `{react: :wave:}` or trigger reactions to react to messages",
            "Anti-spam protection with per-user, per-channel, and per-server cooldowns",
            "Supports channel and role restrictions, deterministic priorities, and zero-DB in-memory caching",
        ],
        "related": ["embed_studio", "premium_price"],
    },
    "embed_studio": {
        "name": "embed_studio",
        "aliases": ["embed_builder", "discohook"],
        "category": "utility",
        "premium": False,
        "admin": True,
        "description": "Interactive multi-embed builder, 1-click Discohook JSON importer, and announcement composer",
        "usage": ["n!embed_studio [channel] [json_code]", "/embed_studio [channel] [json_code]"],
        "examples": [
            "/embed_studio",
            "n!embed_studio #announcements",
            "n!embed_studio json {\"embeds\":[{\"title\":\"Rules\"}]}",
        ],
        "notes": [
            "✨ **Free for all servers** (no premium required)",
            "📋 **1-Click Import JSON Button**: click **📋 Import JSON** directly inside the studio to paste any Discohook JSON or single embed JSON",
            "🎨 Interactive modal composer for message content, title, description, hex color, fields, author, images, and footer",
            "🔔 Safe mention controls: toggle Role/User mentions or `@everyone` only when needed",
            "🔒 Strictly server-scoped channel selector (guaranteed never to show other servers' channels)",
            "Requires **Manage Messages**, **Manage Server**, or **Administrator** permission",
        ],
        "related": ["autoresponder", "say"],
    },
    "server_growth": {
        "name": "server_growth",
        "aliases": ["growth", "growth_analytics"],
        "category": "premium",
        "premium": True,
        "admin": False,
        "description": "Audit vanity supporter penetration, booster velocity, and community health",
        "usage": ["n!server_growth", "/server_growth"],
        "examples": ["/server_growth", "n!growth"],
        "notes": [
            "👑 **Server Premium only**",
            "Calculates the exact percentage and count of members promoting your vanity status",
            "Visual ASCII progress meters for activity, human ratios, and boost performance",
            "Community Engagement Index rating out of 100",
        ],
        "related": ["vanity", "premium"],
    },
    "tictactoe": {
        "name": "tictactoe",
        "aliases": ["ttt"],
        "category": "games",
        "premium": False,
        "admin": False,
        "description": "Play Tic-Tac-Toe solo vs smart AI or challenge a friend to a PvP duel (Servers, DMs & Group DMs)",
        "usage": ["n!tictactoe [opponent] [difficulty]", "/tictactoe [opponent] [difficulty]"],
        "examples": ["/tictactoe", "/tictactoe opponent:@Alex", "/tictactoe difficulty:hard", "n!ttt @Alex"],
        "notes": [
            "Leave `opponent` blank to play Solo vs Nexora AI (`easy`, `medium`, or unbeatable `hard` minimax)",
            "🔄 **Infinite Rematches:** Clicking **Rematch / Play Again** spawns a fresh game message so sessions never expire!",
            "🔔 **Reply Turn Pings:** Turn notifications reply directly to the match board and auto-clean previous pings",
            "Highlights winning 3-in-a-row line in green and saves records to `/gamestats`",
            "Works in Servers, 1-on-1 DMs, and Group DMs",
        ],
        "related": ["connect4", "rps", "guess", "gamestats"],
    },
    "connect4": {
        "name": "connect4",
        "aliases": ["c4", "fourinrow"],
        "category": "games",
        "premium": False,
        "admin": False,
        "description": "Play Connect 4 solo against Nexora AI or challenge a friend to a duel (Servers, DMs & Group DMs)",
        "usage": ["n!connect4 [opponent] [difficulty]", "/connect4 [opponent] [difficulty]"],
        "examples": ["/connect4", "/connect4 opponent:@Alex", "/connect4 difficulty:hard", "n!c4 @Alex"],
        "notes": [
            "7 columns × 6 rows gravity board with 🌟 winning 4-in-a-row star highlights",
            "Solo AI difficulties: `easy`, `medium`, and `hard` (tactical threat blocking & center control)",
            "🔄 **Infinite Rematches:** Clicking **Rematch / Play Again** spawns a fresh game message so sessions never expire!",
            "🔔 **Reply Turn Pings:** Turn notifications reply directly to the match board and auto-clean previous pings",
            "Records wins, losses, and win rates to `/gamestats`",
        ],
        "related": ["tictactoe", "rps", "guess", "gamestats"],
    },
    "rps": {
        "name": "rps",
        "aliases": [],
        "category": "games",
        "premium": False,
        "admin": False,
        "description": "Play Rock-Paper-Scissors solo against Nexora or duel a friend (Servers, DMs & Group DMs)",
        "usage": ["n!rps [opponent]", "/rps [opponent]"],
        "examples": ["/rps", "/rps opponent:@Alex", "n!rps @Alex"],
        "notes": [
            "Solo mode features live win-streak 🔥 tracking and milestone commentary",
            "Duel mode features secret locked-in choices with a reply ping alerting your opponent",
            "🔄 **Infinite Rematches:** Clicking **Rematch / Play Again** spawns a brand-new match message so buttons never expire!",
            "Saves win streaks and match stats to `/gamestats`",
        ],
        "related": ["tictactoe", "connect4", "guess", "gamestats"],
    },
    "guess": {
        "name": "guess",
        "aliases": [],
        "category": "games",
        "premium": False,
        "admin": False,
        "description": "Guess the secret number (1-100) solo against Nexora or duel a friend (Servers, DMs & Group DMs)",
        "usage": ["n!guess [opponent]", "/guess [opponent]"],
        "examples": ["/guess", "/guess opponent:@Alex", "n!guess @Alex"],
        "notes": [
            "Solo: Deduce the secret number in 6 attempts with hot/cold and narrowing range bounds",
            "Duel: Turn-based deduction race against your opponent with reply-to-board turn pings",
            "🔄 **Infinite Rematches:** Clicking **Rematch / Play Again** spawns a fresh game message so sessions never expire!",
            "Saves stats to `/gamestats`",
        ],
        "related": ["tictactoe", "connect4", "rps", "gamestats"],
    },
    "gamestats": {
        "name": "gamestats",
        "aliases": ["game_stats", "leaderboard_games"],
        "category": "games",
        "premium": False,
        "admin": False,
        "description": "View player mini-game win rates, records, and ranking medals",
        "usage": ["n!gamestats [member]", "/gamestats [member]"],
        "examples": ["/gamestats", "/gamestats member:@Alex", "n!gamestats"],
        "notes": [
            "Shows records for Tic-Tac-Toe, Connect 4, Rock-Paper-Scissors, and Number Guesser",
            "Includes Unicode win-rate progress bars and competitive ranks (Rookie to Grandmaster)",
            "Backed by in-memory cache + persistent MongoDB Atlas storage",
        ],
        "related": ["tictactoe", "connect4", "rps", "guess"],
    },
    "owner": {
        "name": "owner",
        "aliases": ["panel"],
        "category": "owner",
        "premium": False,
        "admin": False,
        "description": "Open the interactive Bot Owner Control Panel for live hot-reloading, slash sync, and diagnostics",
        "usage": ["n!owner", "n!panel"],
        "examples": ["n!owner", "n!panel"],
        "notes": [
            "🔒 **Owner Only** — opens an interactive dashboard with 1-click buttons",
            "🔄 **Reload All Cogs:** Hot-reload all 65 extensions in ~1 second without restarting the bot",
            "⚡ **Sync Slash Tree:** Sync global and test-guild slash commands live",
            "🧹 **Clear Caches:** Flush in-memory caches and run garbage collection",
        ],
        "related": ["reload", "say", "premium_grant"],
    },
    "reload": {
        "name": "reload",
        "aliases": ["rl"],
        "category": "owner",
        "premium": False,
        "admin": False,
        "description": "Hot-reload one extension (by short name or full path) or all extensions without restarting",
        "usage": ["n!reload [extension|all]", "n!rl [extension|all]"],
        "examples": ["n!reload", "n!reload all", "n!reload birthday_intro", "n!reload cogs.utility.embed_builder"],
        "notes": [
            "🔒 **Owner Only** — apply code updates live without restarting the process",
            "Supports short cog names (e.g. `n!reload help`, `n!reload rps`) or `n!reload all`",
        ],
        "related": ["owner", "say"],
    },
}

# ── Category metadata ──────────────────────────────────────────────────────────
CATEGORIES = {
    "utility":    {"emoji": "🔧", "label": "Utility",    "desc": "AFK, birthdays, profiles, and other utilities"},
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

# ── Components V2 builders ─────────────────────────────────────────────────────

HAS_COMPONENTS_V2 = hasattr(discord.ui, "LayoutView") and hasattr(discord.ui, "Container")
if not HAS_COMPONENTS_V2:
    raise RuntimeError(
        "Help Components V2 UI requires discord.py 2.6+; "
        "please upgrade discord.py before loading this cog."
    )


def _hex_color(bot, key: str, fallback: int) -> int:
    return cfg_color(bot, key, fallback)


def _color_for_command(bot, data: dict) -> int:
    if data.get("premium"):
        return _hex_color(bot, "premium_color", 0xFFBF47)
    if data.get("admin"):
        return _hex_color(bot, "warning_color", 0xFFAC33)
    return _hex_color(bot, "embed_color", 0x5865F2)


def _badge_line(data: dict) -> str:
    badges = []
    if data.get("premium"):
        badges.append("👑 **Premium**")
    if data.get("admin"):
        badges.append("🛡️ **Admin**")
    return " · ".join(badges)


def _display_limit(text: str, limit: int = 3900) -> str:
    text = text or ""
    return text if len(text) <= limit else text[:limit - 1] + "…"


class HelpLayoutView(discord.ui.LayoutView):
    """Reusable modern Components V2 shell for the help center."""

    def __init__(self, *, bot, user_id=None, color=0x5865F2, timeout=300):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = user_id
        self._color = color
        self.container = discord.ui.Container(accent_colour=color)
        self.add_item(self.container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.user_id is not None and interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ This help panel belongs to someone else. Use `/help` to open your own.",
                ephemeral=True,
            )
            return False
        return True

    def _reset(self):
        self.container.clear_items()

    def add_text(self, text: str):
        self.container.add_item(discord.ui.TextDisplay(_display_limit(text)))

    def add_separator(self):
        self.container.add_item(discord.ui.TextDisplay("━━━━━━━━━━━━━━━━━━━━━━━━"))

    def add_row(self, *items):
        row = discord.ui.ActionRow()
        for item in items:
            row.add_item(item)
        self.container.add_item(row)
        return row

    async def on_timeout(self):
        for item in self.container.children:
            if isinstance(item, discord.ui.ActionRow):
                for child in item.children:
                    if hasattr(child, "disabled"):
                        child.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


def _common_footer(view: HelpLayoutView, text: str):
    view.add_separator()
    view.add_text(f"-# {text}")


def build_main_view(bot, user_id: int) -> "HelpMainView":
    return HelpMainView(bot=bot, user_id=user_id)


class HelpMainView(HelpLayoutView):
    def __init__(self, *, bot, user_id, timeout=300):
        super().__init__(bot=bot, user_id=user_id, color=_hex_color(bot, "embed_color", 0x5865F2), timeout=timeout)
        self.message = None
        self._build()

    def _build(self):
        self._reset()
        registry = getattr(self.bot, "_help_registry", COMMAND_DATA)
        canonical_cmds = [d for name, d in registry.items() if name == d.get("name")]
        counts = {}
        for d in canonical_cmds:
            cat_name = d.get("category", "utility")
            counts[cat_name] = counts.get(cat_name, 0) + 1

        p = prefix(self.bot)
        total_unique = len(canonical_cmds)

        header = (
            "# 🌌 Nexora Help Center · `v3.0.0-pro`\n"
            "> High-performance multi-purpose Discord bot with MongoDB persistence, User App DM support & Components V2 UI.\n\n"
            f"**Prefix:** `{p}` or `{p.swapcase()}`  ·  **Slash:** `/`  ·  📚 **{total_unique}** unique commands\n"
            f"**Quick Jump:** `{p}help <command>` or `/help <command>`"
        )
        self.add_text(header)
        self.add_separator()

        whats_new = (
            "## ✨ What's New in v3.0.0-pro\n"
            "• 📱 **Use Nexora Anywhere (DM & User App Support):** 33 curated fun, game, profile, and utility commands (`/avatar`, `/userinfo`, `/ship`, `/rps`, `/tictactoe`, `/connect4`, `/guess`, `/tod`, `/wyr`, `/meme`, `/calc`, `/remind`) now work in 1-on-1 DMs & Group DMs!\n"
            "• 🎮 **Infinite Rematches & Reply Turn Pings:** Clicking **Rematch / Play Again** in `/rps`, `/tictactoe`, `/connect4`, and `/guess` spawns a brand-new match message so games never expire, and turn pings reply directly to the match board.\n"
            "• 🎂 **00:00 Midnight Birthday Engine:** Announces birthdays right at `00:00` midnight in each server's local UTC timezone with interactive setup studio (`/introbdsetup`, `n!bdaysetup`), guaranteed pings, and 3-layer duplicate protection.\n"
            "• 🎨 **Embed Studio + 1-Click JSON Import:** Build multi-embed announcements interactively or click **📋 Import JSON** inside `/embed_studio` to paste Discohook JSON directly.\n"
            "• 💬 **Atmospheric Quote Cards (`/quote`):** High-res Pillow quote cards with custom/jumbo emoji rendering and 1-click **Apps ➔ Quote Message** support.\n"
            "• 🎭 **720+ Curated Truth & Dare Prompts:** `/tod`, `/truth`, and `/dare` feature 720+ non-repeating prompts across `pg`, `teen`, and `spicy` tiers.\n"
            "• 🤖 **Auto-Responders & Vanity Roles:** 10 free autoresponder slots per server (`/autoresponder`) plus automated status keyword roles (`/vanity`).\n"
            "• ⚡ **Ultra-Fast RAM-Cached Engine:** Zero-blocking hot-path caching for AFK, Reminders, Quotes, Actions, and Game Stats, plus live hot-reloading (`n!owner`, `n!reload`)."
        )
        self.add_text(whats_new)
        self.add_separator()

        visible_categories = [k for k, v in CATEGORIES.items() if counts.get(k)]
        if visible_categories:
            cat_lines = ["## 📂 Browse Categories"]
            for key in visible_categories:
                cat = CATEGORIES[key]
                cat_lines.append(f"{cat['emoji']} **{cat['label']}** — `{counts[key]}` commands · {cat['desc']}")
            self.add_text("\n".join(cat_lines))

        select = discord.ui.Select(
            placeholder="📂 Browse a category...",
            custom_id="help-category",
            min_values=1,
            max_values=1,
            options=[
                discord.SelectOption(label="🏠 Main Menu", value="main", description="Back to the Help Center"),
                *[
                    discord.SelectOption(
                        label=f"{v['emoji']} {v['label']}",
                        value=k,
                        description=v["desc"][:100],
                    )
                    for k, v in CATEGORIES.items()
                    if counts.get(k)
                ],
            ],
        )
        select.callback = self._category_callback
        search = discord.ui.Button(
            label="Search Command",
            style=discord.ButtonStyle.primary,
            emoji="🔍",
            custom_id="help-search",
        )
        search.callback = self._search_callback
        self.add_row(select)
        self.add_row(search)
        _common_footer(self, "Select a category or search by command name, alias, or keyword.")

    async def _category_callback(self, interaction: discord.Interaction):
        select = interaction.data
        key = (select.get("values") or ["main"])[0]
        if key == "main":
            new_view = HelpMainView(bot=self.bot, user_id=self.user_id, timeout=self.timeout)
        else:
            new_view = HelpCategoryView(bot=self.bot, user_id=self.user_id, cat_key=key, timeout=self.timeout)
        await interaction.response.edit_message(view=new_view)

    async def _search_callback(self, interaction: discord.Interaction):
        await interaction.response.send_modal(SearchModal(self.bot))


class HelpCategoryView(HelpLayoutView):
    COMMANDS_PER_PAGE = 8

    def __init__(self, *, bot, user_id, cat_key, page=0, timeout=300):
        color = _hex_color(bot, "embed_color", 0x5865F2)
        super().__init__(bot=bot, user_id=user_id, color=color, timeout=timeout)
        self.cat_key = cat_key
        self.page = page
        self.message = None
        self._build()

    def _build(self):
        self._reset()
        cat = CATEGORIES.get(self.cat_key, {"emoji":"📂", "label":self.cat_key.title(), "desc":""})
        registry = getattr(self.bot, "_help_registry", COMMAND_DATA)
        # Alias entries are searchable, but only the canonical command belongs
        # in the browsing list.
        cmds = [
            data for name, data in registry.items()
            if data["category"] == self.cat_key and name == data["name"]
        ]
        cmds.sort(key=lambda data: data["name"])
        total_pages = max(1, (len(cmds) + self.COMMANDS_PER_PAGE - 1) // self.COMMANDS_PER_PAGE)
        self.page = max(0, min(self.page, total_pages - 1))
        start = self.page * self.COMMANDS_PER_PAGE
        page_cmds = cmds[start:start + self.COMMANDS_PER_PAGE]

        self.add_text(
            f"# {cat['emoji']} {cat['label']}\n\n"
            f"{cat['desc']}\n\n"
            f"**{len(cmds)}** command(s) in this category · Page **{self.page + 1}/{total_pages}**."
        )

        for data in page_cmds:
            badge = _badge_line(data)
            self.add_separator()
            self.add_text(
                f"{badge + chr(10) if badge else ''}"
                f"### `/{data['name']}`\n"
                f"{data['description']}\n"
                f"-# {(data.get('usage') or ['/' + data['name']])[0]}"
            )

        back = discord.ui.Button(label="Home", style=discord.ButtonStyle.secondary, emoji="🏠", custom_id="help-home")
        back.callback = self._home_callback
        search = discord.ui.Button(label="Search", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="help-search-cat")
        search.callback = self._search_callback
        self.add_row(back, search)
        if total_pages > 1:
            previous = discord.ui.Button(label="Previous", style=discord.ButtonStyle.secondary, emoji="◀", disabled=self.page == 0)
            next_page = discord.ui.Button(label="Next", style=discord.ButtonStyle.secondary, emoji="▶", disabled=self.page >= total_pages - 1)
            previous.callback = self._page_callback(-1)
            next_page.callback = self._page_callback(1)
            self.add_row(previous, next_page)
        _common_footer(self, f"Use `/help <command>` for full details · {len(cmds)} commands")

    async def _home_callback(self, interaction):
        await interaction.response.edit_message(view=HelpMainView(bot=self.bot, user_id=self.user_id, timeout=self.timeout))

    async def _search_callback(self, interaction):
        await interaction.response.send_modal(SearchModal(self.bot))

    def _page_callback(self, direction: int):
        async def callback(interaction: discord.Interaction):
            await interaction.response.edit_message(view=HelpCategoryView(
                bot=self.bot,
                user_id=self.user_id,
                cat_key=self.cat_key,
                page=self.page + direction,
                timeout=self.timeout,
            ))
        return callback


class CommandDetailView(HelpLayoutView):
    def __init__(self, *, bot, user_id, data, timeout=300):
        super().__init__(bot=bot, user_id=user_id, color=_color_for_command(bot, data), timeout=timeout)
        self.data = data
        self.message = None
        self._build()

    def _build(self):
        self._reset()
        data = self.data
        cat = CATEGORIES.get(data["category"], {})
        badge = _badge_line(data)
        lines = [
            f"# 📖 /{data['name']}",
            "",
        ]
        if badge:
            lines += [badge, ""]
        lines += [
            f"> {data['description']}",
            "",
            f"📂 **Category:** {cat.get('emoji','📂')} {cat.get('label', data['category'])}",
            f"🔒 **Access:** {'👑 Premium' if data.get('premium') else ('🛡️ Admin' if data.get('admin') else '✅ Everyone')}",
        ]
        if data.get("aliases"):
            lines.append("🔀 **Aliases:** " + " · ".join(f"`{x}`" for x in data["aliases"]))
        self.add_text("\n".join(lines))

        if data.get("usage"):
            self.add_separator()
            self.add_text("## 📌 Usage\n" + "\n".join(f"`{u}`" for u in data["usage"]))

        if data.get("examples"):
            self.add_separator()
            self.add_text("## 💡 Examples\n" + "\n".join(f"`{e}`" for e in data["examples"]))

        if data.get("notes"):
            self.add_separator()
            self.add_text("## 📝 Tips & Notes\n" + "\n".join(f"› {n}" for n in data["notes"]))

        related = get_related(data["name"])
        if related:
            self.add_separator()
            self.add_text(
                "## 🔗 See Also\n" +
                "\n".join(f"`/{r['name']}` — {r['description']}" for r in related)
            )

        if data.get("_auto_stub"):
            footer = "Live command reference · Usage and parameters are kept in sync automatically"
        else:
            footer = "Nexora Help Center · Use `/help` to browse all commands"
        _common_footer(self, footer)

        home = discord.ui.Button(label="Home", style=discord.ButtonStyle.secondary, emoji="🏠", custom_id="help-detail-home")
        home.callback = self._home_callback
        search = discord.ui.Button(label="Search", style=discord.ButtonStyle.primary, emoji="🔍", custom_id="help-detail-search")
        search.callback = self._search_callback
        self.add_row(home, search)

    async def _home_callback(self, interaction):
        await interaction.response.edit_message(view=HelpMainView(bot=self.bot, user_id=self.user_id, timeout=self.timeout))

    async def _search_callback(self, interaction):
        await interaction.response.send_modal(SearchModal(self.bot))


class SearchModal(discord.ui.Modal, title="🔍 Search Nexora Commands"):
    query = discord.ui.TextInput(
        label="Command name or keyword",
        placeholder="Try: birthday, moderation, afk, premium...",
        max_length=40,
        min_length=2,
    )

    def __init__(self, bot):
        super().__init__()
        self.bot = bot

    async def on_submit(self, interaction: discord.Interaction):
        registry = getattr(self.bot, "_help_registry", COMMAND_DATA)
        results = search_commands(self.query.value, limit=5, registry=registry)
        exact = registry.get(self.query.value.lower().strip())

        if exact:
            view = CommandDetailView(bot=self.bot, user_id=interaction.user.id, data=exact)
            await interaction.response.send_message(view=view, ephemeral=True)
            return

        view = SearchResultView(bot=self.bot, user_id=interaction.user.id, query=self.query.value, results=results)
        await interaction.response.send_message(view=view, ephemeral=True)


class SearchResultView(HelpLayoutView):
    def __init__(self, *, bot, user_id, query, results, timeout=120):
        super().__init__(bot=bot, user_id=user_id, color=_hex_color(bot, "embed_color", 0x5865F2), timeout=timeout)
        self.query = query
        self.results = results
        self._build()

    def _build(self):
        self._reset()
        if not self.results:
            popular = " ".join(f"`{n}`" for n in list(COMMAND_DATA)[:6])
            self.add_text(
                f"# 🔍 No results\n\n"
                f"Nothing matched `{self.query}`.\n\n"
                f"**Try:** a shorter keyword or one of these popular commands:\n{popular}"
            )
            home = discord.ui.Button(label="Home", style=discord.ButtonStyle.secondary, emoji="🏠", custom_id="search-home")
            home.callback = self._home_callback
            self.add_row(home)
            return

        self.add_text(
            f"# 🔍 Search Results\n\n"
            f"Found **{len(self.results)}** result(s) for `{self.query}`.\n"
            "Choose a command below for its full documentation."
        )
        for data in self.results:
            badge = _badge_line(data)
            self.add_separator()
            self.add_text(
                f"{badge + chr(10) if badge else ''}"
                f"### `/{data['name']}`\n"
                f"{data['description']}\n"
                f"-# {(data.get('usage') or ['/' + data['name']])[0]}"
            )

        for data in self.results[:5]:
            btn = discord.ui.Button(
                label=f"/{data['name']}"[:80],
                style=discord.ButtonStyle.secondary,
                custom_id=f"help-result-{data['name']}",
            )
            btn.callback = self._make_callback(data)
            self.add_row(btn)

    def _make_callback(self, data):
        async def callback(interaction: discord.Interaction):
            await interaction.response.edit_message(
                view=CommandDetailView(bot=self.bot, user_id=self.user_id, data=data, timeout=self.timeout)
            )
        return callback

    async def _home_callback(self, interaction):
        await interaction.response.edit_message(view=HelpMainView(bot=self.bot, user_id=self.user_id, timeout=self.timeout))


def _send_help_view(ctx, view):
    return ctx.send(view=view)


# ── Cog ────────────────────────────────────────────────────────────────────────

# ── Category guesser for auto-stubs ───────────────────────────────────────────

def _guess_category(cmd) -> str:
    """Guess category from cog name / module path."""
    cog = getattr(cmd, "cog", None) or getattr(cmd, "binding", None)
    if cog:
        cog_name = type(cog).__name__.lower()
        module   = (getattr(cog, "__module__", "") or "").lower()
        if any(k in cog_name or k in module for k in ("owner", "dev")):
            return "owner"
        if any(k in cog_name or k in module for k in ("premium", "boost", "vanity")):
            return "premium"
        if any(k in cog_name or k in module for k in ("moderation", "mod", "admin", "ban", "kick", "mute", "warn", "lockdown", "snipe", "purge", "voicemove")):
            return "moderation"
        if any(k in cog_name or k in module for k in ("game", "rps", "tictactoe", "say")):
            return "games"
        if any(k in cog_name or k in module for k in ("analytic", "export", "server_logs")):
            return "analytics"
        if any(k in cog_name or k in module for k in ("system", "thread", "guide")):
            return "system"
        if any(k in cog_name or k in module for k in ("info", "stat", "user", "server", "avatar", "invite", "channel", "role", "botinfo")):
            return "info"
        if any(k in cog_name or k in module for k in ("fun", "ship", "react", "confess", "meme", "tod", "wyr", "party", "pat", "hug", "kiss", "slap", "punch", "bite", "bonk", "boop", "cuddle", "kill", "poke", "kicks", "blush")):
            return "fun"
        if any(k in cog_name or k in module for k in ("utility", "util", "afk", "birthday", "poll", "calc", "remind", "spotify", "steal")):
            return "utility"
    return "utility"


def _make_stub(cmd) -> dict:
    """Build useful live documentation for a command without a hand-written entry."""
    p = "n!"
    name = cmd.name
    aliases = list(getattr(cmd, "aliases", []) or [])
    desc = getattr(cmd, "description", None) or getattr(cmd, "help", None) or "No description provided."
    if len(desc) > 80:
        desc = desc[:77] + "…"
    signature = (getattr(cmd, "signature", "") or "").strip()
    if not signature:
        parameters = getattr(cmd, "parameters", []) or []
        parts = []
        for parameter in parameters:
            parameter_name = getattr(parameter, "name", "option")
            required = getattr(parameter, "required", False)
            parts.append(f"<{parameter_name}>" if required else f"[{parameter_name}]")
        signature = " ".join(parts)
    suffix = f" {signature}" if signature else ""
    parameter_note = (
        f"Parameters: `{signature}`" if signature else "No parameters required."
    )

    is_hybrid = isinstance(cmd, commands.HybridCommand)
    is_slash = isinstance(cmd, app_commands.Command) or is_hybrid or hasattr(cmd, "app_command")
    is_prefix = isinstance(cmd, commands.Command)

    usage_list = []
    if is_prefix:
        usage_list.append(f"n!{name}{suffix}")
    if is_slash:
        usage_list.append(f"/{name}{suffix}")
    if not usage_list:
        usage_list = [f"n!{name}{suffix}", f"/{name}{suffix}"]

    examples_list = [usage_list[-1] if usage_list else f"n!{name}"]

    return {
        "name":        name,
        "aliases":     aliases,
        "category":    _guess_category(cmd),
        "premium":     False,
        "admin":       False,
        "description": desc,
        "usage":       usage_list,
        "examples":    examples_list,
        "notes":       [
            parameter_note,
            "Prefix: `n!` · Slash: `/`",
            "This reference is generated dynamically from live command registrations.",
        ],
        "related":     [],
        "_auto_stub":  True,
    }


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def cog_load(self):
        """Initial sync on load."""
        self._sync_registry()
        logger.info("Help registry initialized: %d commands", len(self.bot._help_registry))

    @commands.Cog.listener()
    async def on_ready(self):
        """Full re-sync once all cogs have completed loading."""
        self._sync_registry()
        logger.info("Help registry refreshed on_ready: %d total commands indexed", len(self.bot._help_registry))

    def _sync_registry(self):
        """Index all commands across bot.commands and bot.tree."""
        registry = dict(COMMAND_DATA)

        skip = {"h", "cmds", "commands"}

        for canonical_name, data in list(COMMAND_DATA.items()):
            for alias in (data.get("aliases") or []):
                if alias not in skip and alias not in registry:
                    registry[alias] = data

        for cmd in self.bot.commands:
            name = cmd.name
            if name in skip:
                continue
            if name not in registry:
                registry[name] = _make_stub(cmd)
            for alias in (cmd.aliases or []):
                if alias in skip:
                    continue
                if alias not in registry:
                    registry[alias] = registry[name]

        for cmd in self.bot.tree.walk_commands():
            name = cmd.name
            if name in skip:
                continue
            if name not in registry:
                registry[name] = _make_stub(cmd)

        self.bot._help_registry = registry

    async def cog_unload(self):
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
        # Always dynamically sync so newly loaded cogs are 100% visible
        self._sync_registry()
        registry = getattr(self.bot, "_help_registry", COMMAND_DATA)

        if command:
            query = command.lower().strip()
            data = registry.get(query)
            if not data:
                for d in registry.values():
                    if query in (d.get("aliases") or []):
                        data = d
                        break
            if not data:
                results = search_commands(query, limit=5, registry=registry)
                view = SearchResultView(bot=self.bot, user_id=ctx.author.id, query=query, results=results)
                msg = await ctx.send(view=view)
                view.message = msg
                return
            view = CommandDetailView(bot=self.bot, user_id=ctx.author.id, data=data)
            msg = await ctx.send(view=view)
            view.message = msg
        else:
            view = HelpMainView(bot=self.bot, user_id=ctx.author.id)
            msg = await ctx.send(view=view)
            view.message = msg


async def setup(bot):
    await bot.add_cog(Help(bot))
    logger.debug("Loaded Help")

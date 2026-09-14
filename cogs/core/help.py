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
            "If a numeric date can mean two things, the bot asks you to choose the correct interpretation",
            "If the date is ambiguous (e.g. `05/06`) two buttons will appear — tap the correct one",
            "You can update your birthday anytime by running the command again",
            "The year is optional but needed for age calculation on your birthday",
        ],
        "related": ["birthday", "birthdaylist", "editbirthday", "editprofile", "myprofile"],
    },
    "birthday": {
        "name": "birthday",
        "aliases": [],
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
    "birthdaywish": {
        "name": "birthdaywish",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Set a custom message for your birthday announcement",
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
            "Use `/scanintros` to import recent intro messages retroactively",
        ],
        "related": ["scanintros", "birthdaylist"],
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
            "When someone mentions you, the bot leaves a persistent reply with your reason and away time",
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
    "tod": {
        "name": "tod",
        "aliases": ["truthordare"],
        "category": "fun",
        "premium": False,
        "admin": False,
        "description": "Play interactive Truth or Dare solo or challenge a friend",
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
            "Tiers: `pg` (family friendly), `teen` (secrets & party), `spicy` (wild dares & chaos)",
            "Interactive buttons: 💬 Truth, ⚡ Dare, 🎲 Random, 🔄 Reroll",
            "PvP mode: Target player can claim ✅ Completed (+1000 Aura) or 🐔 Chicken Out with funny forfeit penalty!",
        ],
        "related": ["wyr", "meme", "rps"],
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
    "poll": {
        "name": "poll",
        "aliases": [],
        "category": "utility",
        "premium": False,
        "admin": False,
        "description": "Create an interactive button poll with real-time progress bars",
        "usage": ["n!poll <question> [options] [duration]", "/poll <question> [options] [duration]"],
        "examples": [
            "n!poll What movie to watch? Inception | Interstellar | Oppenheimer",
            "/poll question:Game night tomorrow? options:Yes, No duration:1h",
        ],
        "notes": [
            "Supports up to 10 options with interactive buttons",
            "Live Unicode percentage progress bars (`▰▰▰▰▱▱▱`) updating on each vote",
            "Anti-cheat: one vote per member, clicking again toggles vote",
            "Creator or staff can end poll anytime with 🛑 End Poll button",
        ],
        "related": ["quickpoll"],
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
        ],
        "related": [],
    },
    "tictactoe": {
        "name": "tictactoe",
        "aliases": ["ttt"],
        "category": "games",
        "premium": False,
        "admin": False,
        "description": "Challenge a friend to an interactive 3x3 Tic-Tac-Toe game",
        "usage": ["n!tictactoe <opponent>", "/tictactoe <opponent>"],
        "examples": ["n!tictactoe @Alex", "/tictactoe opponent:@Alex"],
        "notes": [
            "Interactive 3x3 Components V2 button grid",
            "Player X vs Player O with turn enforcement and active status display",
            "Automatically detects wins/draws and highlights winning tiles in green",
            "90s turn timeout",
        ],
        "related": ["rps", "tod"],
    },
    "rps": {
        "name": "rps",
        "aliases": [],
        "category": "games",
        "premium": False,
        "admin": False,
        "description": "Play Rock-Paper-Scissors solo against Nexora or duel a friend",
        "usage": ["n!rps [opponent]", "/rps [opponent]"],
        "examples": ["n!rps", "n!rps @Alex", "/rps", "/rps opponent:@Alex"],
        "notes": [
            "No opponent = play solo vs Nexora bot with instant results and Play Again button",
            "With opponent = 2-player secret selection duel where choices are revealed simultaneously",
        ],
        "related": ["tictactoe", "tod"],
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
        counts = {}
        for d in registry.values():
            counts[d["category"]] = counts.get(d["category"], 0) + 1

        lines = [
            "# 🌌 Nexora Help Center",
            "",
            f"**Prefix:** `{prefix(self.bot)}` or `{prefix(self.bot).swapcase()}`  ·  **Slash:** `/`",
            "",
            "Browse every command, search by keyword, or open a command directly.",
            "",
            "**Quick start**",
            f"`{prefix(self.bot)}help <command>`  ·  `/help <command>`",
            "",
            f"📚 **{len(registry)}** commands indexed",
            "",
            "🎂 **Birthday System** — reads configured introductions, stores server-specific profiles, posts scheduled announcements, and supports optional birthday roles. Personal setup and privacy controls are free; premium adds cross-server reach.",
        ]

        visible_categories = [k for k,v in CATEGORIES.items() if counts.get(k)]
        if visible_categories:
            lines += ["", "**Categories**"]
            for key in visible_categories:
                cat = CATEGORIES[key]
                lines.append(f"{cat['emoji']} **{cat['label']}** — `{counts[key]}` commands · {cat['desc']}")

        self.add_text("\n".join(lines))

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

def _guess_category(cmd: commands.Command) -> str:
    """Guess category from cog name / module path."""
    cog = getattr(cmd, "cog", None) or getattr(cmd, "binding", None)
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
    """Build useful live documentation for a command without a hand-written entry."""
    p = "n!"
    name = cmd.name
    aliases = list(getattr(cmd, "aliases", []) or [])
    desc = getattr(cmd, "description", None) or getattr(cmd, "help", None) or "No description provided."
    # Trim discord's verbose help strings
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
    return {
        "name":        name,
        "aliases":     aliases,
        "category":    _guess_category(cmd),
        "premium":     False,
        "admin":       False,
        "description": desc,
        "usage":       [f"n!{name}{suffix}", f"N!{name}{suffix}", f"/{name}{suffix}"],
        "examples":    [f"/{name}{suffix}"],
        "notes":       [
            parameter_note,
            "Prefix commands accept either `n!` or `N!`.",
            "This reference is generated from the live command registration.",
        ],
        "related":     [],
        "_auto_stub":  True,
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

        # Pure slash commands do not appear in bot.commands. Add them too so
        # `/help` documents every command users can actually invoke.
        for cmd in self.bot.tree.walk_commands():
            name = cmd.name
            if name in skip or name in registry:
                continue
            registry[name] = _make_stub(cmd)

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

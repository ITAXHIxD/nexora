# Nexora Discord Bot

Nexora is a modular, all-in-one Discord bot built with Python and `discord.py`. It combines server moderation, community utilities, interactive help menus, games, analytics, thread automation, and configurable premium features in one bot.

> **Invite Nexora:** https://discord.com/oauth2/authorize?client_id=1167464602620145808  
> **Prefix:** `n!` (the bot also responds to mentions; slash commands are available where registered).  
> **Help:** `n!help` or `/help`

## ✨ Standout Commands — Try These First

These are some of Nexora's more distinctive commands, especially the interactive ones:

| Command | What makes it special |
|---|---|
| **`n!randomavatar`** · `n!rav` · `/randomavatar` | 🎲 Picks a random server member and shows their high-resolution avatar and profile. Use the buttons to reroll, switch between **Avatar/Profile**, or dismiss the view. |
| **`n!spotify`** · `n!np` · `n!nowplaying` · `n!spt` · `/spotify` | 🎧 Opens an interactive Spotify now-playing card for you or another member, with album art, track progress, a Spotify link, refresh, and a lyrics-search shortcut. |
| **`n!avatar`** · `/avatar` | 🖼️ Explore an avatar in high resolution, with interactive tabs for profile details, banner/server avatar where available, and download links. |
| **`n!afk`** · `/afk` | 💤 Set an AFK status and get notified when people mention you; supports the bot's configured AFK options. |
| **`n!help` · `/help`** | 🧭 Browse command categories, open command details, and find commands through the interactive help menu. |

> **Quick tip:** Prefix commands use `n!`; slash-command availability depends on what has been registered with Discord. Interactive commands may show buttons or menus after you run them.


## Features

### 🛡️ Moderation and server safety
- Ban, kick, mute/timeout, temporary ban, warnings, and message purge tools.
- Channel lockdown and voice-member movement utilities.
- Server logging and message-snipe utilities.
- Permission checks for staff-only actions.

### 🧵 Community and forum automation
- Thread management and configurable guideline flows.
- Tools to support structured community/help workflows and thread handling.

### 📊 Analytics and status
- Server activity and bot statistics.
- Rotating bot presence/status.
- Bot information and diagnostics/help navigation.

### ⚙️ Utilities
- **`afk`** status with prefix and slash-command support, optional global AFK, status inspection, manual removal, and mention notifications.
- Polls, reminders, calculator, birthday/intro utilities, and emoji/sticker stealing utilities.
- **`spotify`** (aliases: `np`, `nowplaying`, `spt`) for live Spotify activity and interactive playback displays.

### ℹ️ Information
- User, server, role, channel, invite, and bot information.
- **`avatar`** for high-resolution avatar/profile media, and **`randomavatar`** (alias: `rav`) to discover a random server member with reroll and profile tabs.

### 🎮 Games
- Rock Paper Scissors, Tic-Tac-Toe, Connect Four, number guessing, and game statistics.
- Quick message/say utilities and interactive game sessions.

### 🎉 Fun and social commands
- Interaction commands such as hug, cuddle, pat, poke, boop, slap, blush, bite, punch, kiss, and more.
- Ship/match commands, Would You Rather, Truth or Dare, party activities, memes, and confessions.

### ⭐ Premium and customization
- Server Premium and user VIP tiers.
- Vanity/status-triggered supporter role management.
- Booster roles, configurable auto-replies, embed tools, and server-growth features.
- Premium settings and tier information are configured through the project's configuration and storage modules.

### 🧭 Interactive help
- Interactive help views with category browsing, command details, and command search.
- Buttons, select menus, and modals where supported by each feature.

## Project structure

```text
nexora/
├── bot.py                    # Bot entry point, startup, extension loading, events
├── bot.bat                   # Windows launch helper for an existing virtual environment
├── requirements.txt          # Python dependencies
├── config/
│   ├── bot_config.json       # Prefix, UI defaults, and bot settings
│   └── premium_config.json   # Premium tiers and feature limits
├── cogs/
│   ├── analytics/            # Analytics and usage statistics
│   ├── core/                 # Help and status
│   ├── fun/                  # Social, party, meme, and confession commands
│   ├── games/                # Interactive games
│   ├── info/                 # Information and avatar commands
│   ├── moderation/           # Moderation and server logs
│   ├── owner/                # Owner-only utilities
│   ├── premium/               # Premium features
│   ├── system/               # Guidelines and thread management
│   ├── utility/              # AFK, reminders, polls, Spotify, and other tools
│   └── premium_main.py       # Premium management and vanity system
├── utils/
│   ├── config.py             # Environment-variable loading
│   ├── database.py           # SQLite-backed data helpers
│   ├── error_handler.py      # Shared error handling
│   ├── game_stats.py         # Game-statistics helpers
│   ├── premium_storage.py    # Premium data storage and sanitization
│   └── ui.py                 # Shared interactive UI components
└── data/                     # Runtime data; contents may be generated by the bot
```

The bot loads its extensions from the `EXTENSIONS` list in `bot.py`. A cog is a Python module/class that groups related commands and event listeners.

## Requirements

- Python 3.11 or newer recommended.
- A Discord application and bot token.
- The dependencies listed in `requirements.txt`.
- Optional: a MongoDB connection string if you want to enable the MongoDB-backed features.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/ITAXHIxD/nexora.git
cd nexora
```

### 2. Create and activate a virtual environment

**Windows (Command Prompt):**

```bat
py -3.11 -m venv venv
venv\Scripts\activate
```

**macOS/Linux:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install dependencies

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

Create a `.env` file in the project root. Never commit this file.

```dotenv
DISCORD_TOKEN=your_discord_bot_token
APPLICATION_ID=your_discord_application_id
LOG_CHANNEL_ID=your_log_channel_id
SUPPORT_WEBHOOK_URL=
DATABASE_ENABLED=false
# Optional, only if using MongoDB:
MONGO_URI=
```

`LOG_WEBHOOK_URL` is also accepted as a fallback for `SUPPORT_WEBHOOK_URL`. Use only webhook URLs you control. Leave optional values empty if you do not use those features.

### 5. Configure the Discord application

In the Discord Developer Portal:

1. Enable the **Message Content Intent**, **Server Members Intent**, and **Presence Intent** if your server features require them. Nexora requests these intents in code.
2. Invite the bot with the OAuth scopes `bot` and `applications.commands`.
3. Grant only the permissions required by the features you enable (for example, moderation actions, nickname/role management, message management, and viewing/sending messages).
4. Ensure the bot's role is positioned above roles it needs to manage.

### 6. Start the bot

```bash
python bot.py
```

On Windows, `bot.bat` can be used if the project has the expected `venv` directory and dependencies installed.

## Configuration and data

- `config/bot_config.json` contains settings such as the default prefix, command response limits, status rotation, and UI colors.
- `config/premium_config.json` defines premium tiers and feature limits.
- Runtime files under `data/` may store AFK state, game statistics, guild settings, and other feature data.
- `DATABASE_ENABLED=true` enables the SQLite helper controlled by the database module.
- `MONGO_URI` is optional; the bot is designed to continue without MongoDB if it is unavailable or not configured.

Back up runtime data before making changes or migrating storage. Do not share database files containing server/user data publicly.

## Troubleshooting

- **Bot does not start:** check that `DISCORD_TOKEN` is set, dependencies installed successfully, and the console traceback.
- **Prefix commands do not respond:** verify the Message Content Intent in the Developer Portal and that the bot can read and send messages in the channel.
- **Slash commands are missing:** verify the `applications.commands` OAuth scope and check the command-sync logs during startup.
- **Moderation or role commands fail:** check the bot's permissions and role hierarchy.
- **MongoDB warning:** set a valid `MONGO_URI` only if you intend to use MongoDB; otherwise the bot can run without it.

## Security and repository hygiene

- Keep `.env`, bot tokens, webhook URLs, and database credentials private.
- Avoid committing `venv/`, `__pycache__/`, generated database files, or live server data.
- Rotate any token or webhook that has been exposed.
- Use a separate test server when testing moderation, role, and automation features.

## License

No license file was identified in the repository when this README was prepared. Unless a license is added, reuse and redistribution permissions are not explicitly granted. Add a `LICENSE` file if you want to define how others may use the project.

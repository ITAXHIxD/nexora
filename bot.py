import asyncio
import io
import json
import logging
import os
import random
import subprocess
import sys
from datetime import datetime, timezone

# Auto-install missing dependencies on cloud hosts like WispByte
_REQUIRED_PACKAGES = {
    "PIL": "pillow",
    "psutil": "psutil",
    "motor": "motor",
    "dotenv": "python-dotenv",
}
_missing_pkgs = []
for _mod, _pkg in _REQUIRED_PACKAGES.items():
    try:
        __import__(_mod)
    except ImportError:
        _missing_pkgs.append(_pkg)

if _missing_pkgs:
    print(f"[Startup] Installing missing packages {_missing_pkgs}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", *_missing_pkgs])
        print("[Startup] All required packages installed successfully!")
    except Exception as _err:
        print(f"[Startup] Could not auto-install packages: {_err}")


import aiohttp
import discord
from discord.ext import commands, tasks

from utils.config import (
    DATABASE_ENABLED,
    DISCORD_TOKEN,
    LOG_CHANNEL_ID,
    OWNER_ID,
    SUPPORT_WEBHOOK_URL,
)
from utils.database import DatabaseManager
from utils.premium_storage import load_premium_data

# ── MongoDB ────────────────────────────────────────────────────────────────────
try:
    import motor.motor_asyncio
    from dotenv import load_dotenv
    load_dotenv()
    MONGO_AVAILABLE = True
except ImportError:
    MONGO_AVAILABLE = False
    logging.getLogger(__name__).warning(
        "motor or dotenv not installed. Run: pip install motor python-dotenv\n"
        "Bot will continue using local JSON files until then."
    )
# ──────────────────────────────────────────────────────────────────────────────

if hasattr(sys.stdout, "buffer") and sys.stdout.buffer is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "buffer") and sys.stderr.buffer is not None:
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

class CleanConsoleFilter(logging.Filter):
    """Filter out benign library warnings to keep terminal logs clean and readable."""
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "PyNaCl is not installed" in msg or "davey is not installed" in msg:
            return False
        return True

_console_handler = logging.StreamHandler(sys.stdout)
_console_handler.setFormatter(
    logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
)
_console_handler.addFilter(CleanConsoleFilter())

_root_logger = logging.getLogger()
_root_logger.setLevel(logging.INFO)
_root_logger.handlers = [_console_handler]

# Suppress spammy low-level library logs
for noisy in ("discord", "discord.http", "discord.gateway", "discord.client", "aiohttp.access", "aiohttp.client"):
    logging.getLogger(noisy).setLevel(logging.WARNING)

logger = logging.getLogger(__name__)


def load_config() -> dict:
    try:
        with open("config/bot_config.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.critical("config/bot_config.json not found.")
        raise SystemExit(1)
    except json.JSONDecodeError:
        logger.critical("config/bot_config.json is not valid JSON.")
        raise SystemExit(1)


bot_config = load_config()
bot_settings = bot_config.get("bot_settings", {})
DEFAULT_PREFIX = bot_settings.get("default_prefix", "n!")


CREATIVE_ACTIVITIES = [
    # ── Playing ──
    {"type": discord.ActivityType.playing, "name": "n!help | /help for commands"},
    {"type": discord.ActivityType.playing, "name": "with {user_count} friends across {server_count} servers"},
    {"type": discord.ActivityType.playing, "name": "chess with quantum algorithms"},
    {"type": discord.ActivityType.playing, "name": "Truth or Dare | n!tod & n!truth"},
    {"type": discord.ActivityType.playing, "name": "Confession game | n!confe"},
    {"type": discord.ActivityType.playing, "name": "Would You Rather | n!wyr"},
    {"type": discord.ActivityType.playing, "name": "Rock Paper Scissors | n!rps"},
    {"type": discord.ActivityType.playing, "name": "Tic-Tac-Toe championship | n!ttt"},
    {"type": discord.ActivityType.playing, "name": "Connect 4 World League | n!connect4"},
    {"type": discord.ActivityType.playing, "name": "Guess The Number Duel | n!guess"},
    {"type": discord.ActivityType.playing, "name": "Reddit Stream & Memes | n!reddit"},
    {"type": discord.ActivityType.playing, "name": "Minecraft hardcore in {server_count} realms"},
    {"type": discord.ActivityType.playing, "name": "Cyberpunk 2077 in 8K HDR"},
    {"type": discord.ActivityType.playing, "name": "Elden Ring: Shadow of the Erdtree"},
    {"type": discord.ActivityType.playing, "name": "Genshin Impact with max Primogems"},
    {"type": discord.ActivityType.playing, "name": "Honkai: Star Rail in Astral Express"},
    {"type": discord.ActivityType.playing, "name": "Pokemon Showdown OU League"},
    {"type": discord.ActivityType.playing, "name": "Super Smash Bros Ultimate"},
    {"type": discord.ActivityType.playing, "name": "League of Legends with 0 toxicity"},
    {"type": discord.ActivityType.playing, "name": "with Discord Components V2"},
    {"type": discord.ActivityType.playing, "name": "matchmaker | n!ship"},
    {"type": discord.ActivityType.playing, "name": "detective in #general"},
    {"type": discord.ActivityType.playing, "name": "hide and seek with {user_count} members"},
    {"type": discord.ActivityType.playing, "name": "with neural networks & synapses"},
    {"type": discord.ActivityType.playing, "name": "Monopoly with infinite bot currency"},
    {"type": discord.ActivityType.playing, "name": "party games | n!party"},
    {"type": discord.ActivityType.playing, "name": "with bits, bytes & firewalls"},
    {"type": discord.ActivityType.playing, "name": "in {server_count} parallel dimensions"},
    {"type": discord.ActivityType.playing, "name": "the Turing Test Championship"},
    {"type": discord.ActivityType.playing, "name": "Valorant ranked with the dev team"},
    {"type": discord.ActivityType.playing, "name": "GTA VI in exclusive early access"},
    {"type": discord.ActivityType.playing, "name": "infinite aura generator | n!aura"},
    {"type": discord.ActivityType.playing, "name": "synthwave in high fidelity"},

    # ── Watching ──
    {"type": discord.ActivityType.watching, "name": "over {user_count} incredible souls"},
    {"type": discord.ActivityType.watching, "name": "{server_count} servers thrive & grow"},
    {"type": discord.ActivityType.watching, "name": "CyberPunk S2 | Tears of Steel"},
    {"type": discord.ActivityType.watching, "name": "One Piece episode {random_ep}"},
    {"type": discord.ActivityType.watching, "name": "Jujutsu Kaisen Season kitkat leaks"},
    {"type": discord.ActivityType.watching, "name": "One Piece Movie: God Valley"},
    {"type": discord.ActivityType.watching, "name": "the multiverse unfold"},
    {"type": discord.ActivityType.watching, "name": "for spam and rule breakers"},
    {"type": discord.ActivityType.watching, "name": "the audit logs closely"},
    {"type": discord.ActivityType.watching, "name": "anime in 4K with the community"},
    {"type": discord.ActivityType.watching, "name": "Interstellar for the 100th time"},
    {"type": discord.ActivityType.watching, "name": "matrix code rain in dark mode"},
    {"type": discord.ActivityType.watching, "name": "cat memes in 4K resolution"},
    {"type": discord.ActivityType.watching, "name": "r/memes top posts of all time"},
    {"type": discord.ActivityType.watching, "name": "over AFK members sleeping peacefully | n!afk"},
    {"type": discord.ActivityType.watching, "name": "Twitch Rivals championship"},
    {"type": discord.ActivityType.watching, "name": "stars ignite across distant galaxies"},
    {"type": discord.ActivityType.watching, "name": "n!help requests in real time"},
    {"type": discord.ActivityType.watching, "name": "sunrise over {server_count} servers"},
    {"type": discord.ActivityType.watching, "name": "the timeline branch into infinity"},
    {"type": discord.ActivityType.watching, "name": "cosmic horizon & quantum events"},
    {"type": discord.ActivityType.watching, "name": "{channel_count} channels for good vibes"},
    {"type": discord.ActivityType.watching, "name": "Studio Ghibli masterpieces"},

    # ── Listening ──
    {"type": discord.ActivityType.listening, "name": "the echo of {user_count} voices"},
    {"type": discord.ActivityType.listening, "name": "Makima is Listening"},
    {"type": discord.ActivityType.listening, "name": "whispers from other dimensions"},
    {"type": discord.ActivityType.listening, "name": "phonk drift music at 3 AM"},
    {"type": discord.ActivityType.listening, "name": "anime opening themes on blast"},
    {"type": discord.ActivityType.listening, "name": "OverTaken"},
    {"type": discord.ActivityType.listening, "name": "smooth city pop from Tokyo 1986"},
    {"type": discord.ActivityType.listening, "name": "lo-fi beats to grind commands to"},
    {"type": discord.ActivityType.listening, "name": "voice channel karaoke sessions"},
    {"type": discord.ActivityType.listening, "name": "keyboard clicks of late-night coders"},
    {"type": discord.ActivityType.listening, "name": "rain sounds on a cozy Discord night"},
    {"type": discord.ActivityType.listening, "name": "the heartbeat of the server"},
    {"type": discord.ActivityType.listening, "name": "Spotify with friends | n!spotify"},
    {"type": discord.ActivityType.listening, "name": "user confessions & secrets | n!confess"},
    {"type": discord.ActivityType.listening, "name": "frequencies of deep space"},
    {"type": discord.ActivityType.listening, "name": "community feedback & vibes"},
    {"type": discord.ActivityType.listening, "name": "the smooth hum of clean servers"},
    {"type": discord.ActivityType.listening, "name": "interstellar transmissions"},

    # ── Competing ──
    {"type": discord.ActivityType.competing, "name": "the Grand Discord Bot Tournament"},
    {"type": discord.ActivityType.competing, "name": "speedrunning server setups"},
    {"type": discord.ActivityType.competing, "name": "Rock-Paper-Scissors World League | n!rps"},
    {"type": discord.ActivityType.competing, "name": "Connect 4 Grandmaster Tournament | n!connect4"},
    {"type": discord.ActivityType.competing, "name": "Tic-Tac-Toe Flawless Streak | n!ttt"},
    {"type": discord.ActivityType.competing, "name": "Guess the Number psychic showdown | n!guess"},
    {"type": discord.ActivityType.competing, "name": "the Ultimate Trivia Showdown"},
    {"type": discord.ActivityType.competing, "name": "the Turing Test Grand Finals"},
    {"type": discord.ActivityType.competing, "name": "fastest response time in {server_count} guilds"},
    {"type": discord.ActivityType.competing, "name": "for the best community vibe"},

    # ── Streaming ──
    {
        "type": discord.ActivityType.streaming,
        "name": "helping across {server_count} servers",
        "url": "https://discord.gg/f5b85pRgq9",
    },
    {
        "type": discord.ActivityType.streaming,
        "name": "Nexora Multiverse | n!help",
        "url": "https://discord.gg/f5b85pRgq9",
    },
    {
        "type": discord.ActivityType.streaming,
        "name": "24/7 chill energy & moderation",
        "url": "https://discord.gg/f5b85pRgq9",
    },
]


EXTENSIONS = [
    "cogs.system.terminal_logger",
    "cogs.core.status",
    "cogs.core.help",
    "cogs.analytics.analytics",
    "cogs.fun.confession",
    "cogs.fun.ship",
    "cogs.fun.kicks",
    "cogs.fun.punch",
    "cogs.fun.bonk",
    "cogs.fun.poke",
    "cogs.fun.pat",
    "cogs.fun.boop",
    "cogs.fun.slap",
    "cogs.fun.blush",
    "cogs.fun.hug",
    "cogs.fun.cuddle",
    "cogs.fun.bite",
    "cogs.fun.kill",
    "cogs.fun.kiss",
    "cogs.fun.tod",
    "cogs.fun.wyr",
    "cogs.fun.meme",
    "cogs.fun.party",
    "cogs.games.gamesstats",
    "cogs.games.say",
    "cogs.games.tictactoe",
    "cogs.games.rps",
    "cogs.games.guess",
    "cogs.games.connect4",
    "cogs.info.botinfo",
    "cogs.info.invite",
    "cogs.info.serverinfo",
    "cogs.info.userinfo",
    "cogs.info.avatar",
    "cogs.info.randomavatar",
    "cogs.info.roleinfo",
    "cogs.info.channelinfo",
    "cogs.owner.owner",
    "cogs.system.guideline_mode",
    "cogs.system.thread_manager",
    "cogs.utility.afk",
    "cogs.utility.steal",
    "cogs.utility.spotifyview",
    "cogs.utility.birthday_intro",
    "cogs.utility.remind",
    "cogs.utility.poll",
    "cogs.utility.calculator",
    "cogs.utility.quote",
    "cogs.moderation.server_logs",
    "cogs.moderation.snipe",
    "cogs.moderation.voicemove",
    "cogs.moderation.ban",
    "cogs.moderation.tempban",
    "cogs.moderation.kick",
    "cogs.moderation.mute",
    "cogs.moderation.purge",
    "cogs.moderation.warn",
    "cogs.moderation.lockdown",
    "cogs.premium_main",
    "cogs.premium.user_vip",
    "cogs.premium.booster_role",
    "cogs.premium.autoreply",
    "cogs.premium.embed_studio",
    "cogs.premium.server_growth",
    "utils.error_handler",
]


def _safe_dt(val) -> datetime | None:
    if val is None or val == "null":
        return None
    if isinstance(val, datetime):
        return val if val.tzinfo is not None else val.replace(tzinfo=timezone.utc)
    if isinstance(val, str):
        try:
            dt = datetime.fromisoformat(val)
            return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)
        except ValueError:
            return None
    return None


class CharacterBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        app_id_env = os.getenv("APPLICATION_ID", "1167464602620145808")
        app_id = int(app_id_env) if app_id_env and app_id_env.isdigit() else 1167464602620145808

        super().__init__(
            command_prefix=commands.when_mentioned_or(DEFAULT_PREFIX, DEFAULT_PREFIX.swapcase()),
            intents=intents,
            help_command=None,
            case_insensitive=True,
            application_id=app_id,
            owner_id=OWNER_ID,
        )

        self.bot_config = bot_config
        self.db_manager = DatabaseManager(DATABASE_ENABLED)
        self.premium_guild_ids = set()
        self.premium_guild_tiers = {}
        self.premium_user_ids = set()
        self.premium_user_tiers = {}
        self.premium_user_colors = {}
        self.session: aiohttp.ClientSession | None = None
        self.log_channel: discord.TextChannel | None = None
        self.loaded_extensions: set[str] = set()

        # ── MongoDB Atlas ──────────────────────────────────────────────────────
        # Shared across ALL cogs via bot.mongo_db
        # Access in any cog: col = self.bot.mongo_db["collection_name"]
        self.mongo_client = None
        self.mongo_db     = None
        # ──────────────────────────────────────────────────────────────────────

        self.bot_stats = {
            "messages_processed": 0,
            "conversations_today": 0,
            "commands_used": 0,
            "errors_encountered": 0,
            "start_time": datetime.now(timezone.utc),
        }

        self.load_premium_guilds()
        self.load_premium_tiers()

    # ── MongoDB connect / disconnect ───────────────────────────────────────────

    async def connect_mongo(self):
        """
        Connect to MongoDB Atlas.
        Reads MONGO_URI from your .env file (or Wisp environment variables).

        Wisp setup:
            Go to Wisp dashboard → your server → Environment Variables
            Add:  MONGO_URI = mongodb+srv://user:pass@cluster.mongodb.net/botdb

        Local VS Code setup:
            Create a .env file in your project root:
            MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/botdb
        """
        if not MONGO_AVAILABLE:
            logger.warning("MongoDB skipped — motor not installed.")
            return

        uri = os.getenv("MONGO_URI")
        if not uri:
            logger.warning(
                "MONGO_URI not set in environment variables.\n"
                "  • Wisp:     Dashboard → Environment Variables → add MONGO_URI\n"
                "  • Local:    Create .env file with MONGO_URI=...\n"
                "Bot will run without MongoDB until this is set."
            )
            return

        try:
            self.mongo_client = motor.motor_asyncio.AsyncIOMotorClient(uri)
            self.mongo_db     = self.mongo_client["botdb"]
            # Quick ping to confirm Atlas is reachable
            await self.mongo_client.admin.command("ping")
            logger.info("✅ Connected to MongoDB Atlas — database: 'botdb'")
        except Exception as e:
            logger.error("❌ MongoDB connection failed: %s", e)
            logger.error("Bot will continue without MongoDB. Check your MONGO_URI.")
            self.mongo_client = None
            self.mongo_db     = None

    async def disconnect_mongo(self):
        if self.mongo_client:
            self.mongo_client.close()
            logger.info("MongoDB connection closed.")

    # ── Lifecycle ──────────────────────────────────────────────────────────────

    async def setup_hook(self):
        self.session = aiohttp.ClientSession()

        # Connect to MongoDB before loading cogs so they can use bot.mongo_db
        await self.connect_mongo()

        await self._load_extensions()
        await self._sync_app_commands()

    async def close(self):
        logger.info("Shutting down...")

        for cog in self.cogs.values():
            if hasattr(cog, "close"):
                try:
                    await cog.close()
                except Exception as e:
                    logger.warning("Error while closing cog %s: %s", cog.qualified_name, e)

        if self.update_activity.is_running():
            self.update_activity.cancel()

        if self.session and not self.session.closed:
            await self.session.close()

        # Close MongoDB last
        await self.disconnect_mongo()

        await super().close()

    # ── Extension loading ──────────────────────────────────────────────────────

    async def _load_extensions(self):
        failed = []
        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                self.loaded_extensions.add(ext)
                logger.debug("Loaded extension: %s", ext)
            except Exception as e:
                failed.append((ext, str(e)))
                logger.error("Failed to load extension %s: %s", ext, e)

        if failed:
            logger.warning("Loaded %d/%d extensions (%d failed)", len(self.loaded_extensions), len(EXTENSIONS), len(failed))
        else:
            logger.info("📦 Loaded all %d extensions successfully", len(self.loaded_extensions))

    async def _sync_app_commands(self):
        if not bot_settings.get("auto_sync_commands", True):
            logger.debug("Auto sync disabled in config.")
            return

        try:
            cmds = await self.tree.sync()
            synced_names = {cmd.name for cmd in cmds}
            help_status = "registered" if "help" in synced_names else "MISSING"
            logger.info(
                "⚡ App commands synced globally: %d commands | /help: %s",
                len(cmds), help_status,
            )
            if "help" not in synced_names:
                logger.error(
                    "/help was not present in the global sync response. Check that cogs.core.help loaded and registered its hybrid command."
                )
        except Exception as e:
            logger.error("Global slash sync failed: %s", e)

        test_guild_id = int(os.getenv("TEST_GUILD_ID", "0"))
        if test_guild_id:
            try:
                guild = discord.Object(id=test_guild_id)
                # Copy global command definitions into the test guild so updates show there immediately.
                self.tree.copy_global_to(guild=guild)
                cmds = await self.tree.sync(guild=guild)
                guild_names = {cmd.name for cmd in cmds}
                help_status = "registered" if "help" in guild_names else "MISSING"
                logger.info(
                    "⚡ App commands synced to test guild %d: %d commands | /help: %s",
                    test_guild_id, len(cmds), help_status,
                )
                if "help" not in guild_names:
                    logger.error("/help was not present in the test-guild sync response.")
            except Exception as e:
                logger.error("Guild sync failed (%d): %s", test_guild_id, e)

    # ── Premium ────────────────────────────────────────────────────────────────

    def load_premium_guilds(self):
        self.premium_guild_ids = set()
        self.premium_guild_tiers = {}
        self.premium_user_ids = set()
        self.premium_user_tiers = {}
        self.premium_user_colors = {}
        try:
            premium_data = load_premium_data()
            for gid_str, sub in premium_data.get("subscriptions", {}).items():
                if isinstance(sub, dict) and sub.get("tier", "FREE").upper() != "FREE":
                    exp = _safe_dt(sub.get("expires_at"))
                    if exp and datetime.now(timezone.utc) > exp:
                        continue
                    gid = int(gid_str) if str(gid_str).isdigit() else gid_str
                    self.premium_guild_ids.add(gid)
                    self.premium_guild_tiers[gid] = sub.get("tier", "FREE").upper()

            for uid_str, usub in premium_data.get("user_subscriptions", {}).items():
                if isinstance(usub, dict) and usub.get("tier", "FREE").upper() != "FREE":
                    exp = _safe_dt(usub.get("expires_at"))
                    if exp and datetime.now(timezone.utc) > exp:
                        continue
                    uid = int(uid_str) if str(uid_str).isdigit() else uid_str
                    self.premium_user_ids.add(uid)
                    self.premium_user_tiers[uid] = usub.get("tier", "FREE").upper()
                    if usub.get("custom_color"):
                        self.premium_user_colors[uid] = usub["custom_color"]
            logger.debug(
                "Loaded %d premium guilds and %d VIP users from local storage",
                len(self.premium_guild_ids), len(self.premium_user_ids),
            )
        except Exception as e:
            logger.error("Error reading premium storage: %s", e)

    def load_premium_tiers(self):
        self._premium_tiers_cache = {}
        try:
            with open("config/premium_config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                self._premium_tiers_cache = cfg.get("premium_tiers", {})
        except Exception:
            self._premium_tiers_cache = {}

    def get_tier_config(self, tier: str) -> dict:
        t = str(tier or "FREE").strip().upper()
        if getattr(self, "_premium_tiers_cache", None):
            return self._premium_tiers_cache.get(t, {"features": {}, "limits": {}})
        try:
            with open("config/premium_config.json", "r", encoding="utf-8") as f:
                cfg = json.load(f)
                self._premium_tiers_cache = cfg.get("premium_tiers", {})
                return self._premium_tiers_cache.get(t, {})
        except Exception:
            return {"features": {}, "limits": {}}

    def is_premium_guild(self, guild_id: int) -> bool:
        gid = int(guild_id)
        if gid in self.premium_guild_ids or str(gid) in self.premium_guild_ids:
            return True
        guild_str = str(guild_id)
        try:
            premium_data = load_premium_data()
            subscription = premium_data.get("subscriptions", {}).get(guild_str)
            if subscription:
                exp = _safe_dt(subscription.get("expires_at"))
                if exp and datetime.now(timezone.utc) > exp:
                    return False
                return subscription.get("tier", "FREE").lower() != "free"
        except Exception as e:
            logger.error("Error reading premium runtime data: %s", e)

        return self.premium_guild_tiers.get(gid, "free").lower() != "free" or self.premium_guild_tiers.get(guild_str, "free").lower() != "free"

    def get_premium_tier(self, guild_id: int) -> str:
        gid = int(guild_id)
        if not self.is_premium_guild(gid):
            return "FREE"
        return self.premium_guild_tiers.get(gid) or self.premium_guild_tiers.get(str(gid), "FREE")

    def is_premium_user(self, user_id: int) -> bool:
        uid = int(user_id)
        if uid in self.premium_user_ids or str(uid) in self.premium_user_ids:
            return True
        user_str = str(user_id)
        try:
            premium_data = load_premium_data()
            sub = premium_data.get("user_subscriptions", {}).get(user_str)
            if sub:
                exp = _safe_dt(sub.get("expires_at"))
                if exp and datetime.now(timezone.utc) > exp:
                    return False
                return sub.get("tier", "FREE").lower() != "free"
        except Exception as e:
            logger.error("Error reading user VIP runtime data: %s", e)
        return self.premium_user_tiers.get(uid, "free").lower() != "free"

    def get_user_vip_tier(self, user_id: int) -> str:
        uid = int(user_id)
        if not self.is_premium_user(uid):
            return "FREE"
        return self.premium_user_tiers.get(uid) or self.premium_user_tiers.get(str(uid), "FREE")

    def get_user_custom_color(self, user_id: int) -> int | None:
        return self.premium_user_colors.get(int(user_id))

    # ── Support & System Logging ───────────────────────────────────────────────

    async def setup_log_channel(self):
        if not LOG_CHANNEL_ID:
            return
        try:
            cid = int(str(LOG_CHANNEL_ID).strip())
            self.log_channel = self.get_channel(cid)
            if not self.log_channel:
                try:
                    self.log_channel = await self.fetch_channel(cid)
                except Exception:
                    pass
            if self.log_channel:
                logger.info("Logging channel set to: #%s (%s)", self.log_channel.name, self.log_channel.id)
        except Exception as e:
            logger.debug("Error setting up logging channel: %s", e)

    async def send_support_log(
        self,
        title: str,
        description: str,
        color: int = 0x5865F2,
        fields: list[dict] | None = None,
        thumbnail_url: str | None = None,
    ):
        """
        Sends high-priority system logs to the support channel webhook
        (SUPPORT_WEBHOOK_URL / LOG_WEBHOOK_URL) and/or LOG_CHANNEL_ID.
        """
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(timezone.utc),
        )
        if fields:
            for f in fields:
                embed.add_field(name=f["name"], value=f["value"], inline=f.get("inline", True))
        if thumbnail_url:
            embed.set_thumbnail(url=thumbnail_url)
        embed.set_footer(text="Nexora Core System · Support Feed")

        # 1. Send via Webhook if configured
        if SUPPORT_WEBHOOK_URL and self.session and not self.session.closed:
            try:
                webhook = discord.Webhook.from_url(SUPPORT_WEBHOOK_URL, session=self.session)
                bot_name = self.user.name if self.user else "Nexora"
                avatar = str(self.user.display_avatar.url) if self.user else None
                await webhook.send(embed=embed, username=f"{bot_name} Core Logs", avatar_url=avatar)
            except Exception as e:
                logger.debug("Support webhook dispatch error: %s", e)

        # 2. Send via TextChannel only if TerminalLogger is not handling the channel
        if self.log_channel and "TerminalLogger" not in self.cogs:
            try:
                await self.log_channel.send(embed=embed)
            except Exception as e:
                logger.debug("Support text channel dispatch error: %s", e)

    async def send_log(
        self,
        log_type: str,
        title: str,
        description: str,
        color: int = 0x0099FF,
        fields: list[dict] | None = None,
    ):
        """Backwards-compatible wrapper routing to unified support log."""
        await self.send_support_log(
            title=f"📊 [{log_type}] {title}",
            description=description,
            color=color,
            fields=fields,
        )

    # ── Activity rotation ──────────────────────────────────────────────────────

    async def get_dynamic_activity(self):
        try:
            server_count  = len(self.guilds)
            user_count    = sum(g.member_count or 0 for g in self.guilds)
            channel_count = len(list(self.get_all_channels()))
            random_ep     = random.randint(1, 1150)
            template = random.choice(CREATIVE_ACTIVITIES)
            name = template["name"].format(
                server_count=server_count,
                user_count=user_count,
                channel_count=channel_count,
                random_ep=random_ep,
            )
            if template["type"] == discord.ActivityType.streaming:
                return discord.Streaming(name=name, url=template.get("url", "https://discord.gg/f5b85pRgq9"))
            return discord.Activity(type=template["type"], name=name)
        except Exception as e:
            logger.debug("Error generating dynamic activity: %s", e)
            return discord.Activity(type=discord.ActivityType.playing, name="n!help | /help")

    @tasks.loop(minutes=5)
    async def update_activity(self):
        try:
            activity = await self.get_dynamic_activity()
            await self.change_presence(activity=activity, status=discord.Status.online)
            logger.debug("Rotated status activity to: %s", activity.name)
        except Exception as e:
            logger.debug("Error updating activity: %s", e)


bot = CharacterBot()


@bot.event
async def on_ready():
    await bot.setup_log_channel()

    if bot_settings.get("status_rotation", True) and not bot.update_activity.is_running():
        bot.update_activity.start()

    # Aesthetic Terminal Banner Metrics
    total_guilds = len(bot.guilds)
    total_users = sum(g.member_count or 0 for g in bot.guilds)
    total_channels = len(list(bot.get_all_channels()))
    ping_ms = round(bot.latency * 1000) if bot.latency and not str(bot.latency) == "inf" else 0
    mongo_status = "Connected (botdb) ✅" if bot.mongo_db is not None else "Local JSON Fallback ⚠️"
    webhook_status = "Configured & Active ✅" if SUPPORT_WEBHOOK_URL else "Not Configured (Channel ID Fallback)"

    # ANSI Colors
    C_CYAN = "\033[96m"
    C_MAGENTA = "\033[95m"
    C_GREEN = "\033[92m"
    C_YELLOW = "\033[93m"
    C_BLUE = "\033[94m"
    C_BOLD = "\033[1m"
    C_RESET = "\033[0m"

    banner = f"""
{C_CYAN}{C_BOLD}  ███╗   ██╗███████╗██╗  ██╗ ██████╗ ██████╗  █████╗ 
  ████╗  ██║██╔════╝╚██╗██╔╝██╔═══██╗██╔══██╗██╔══██╗
  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║██████╔╝███████║
  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║██╔══██╗██╔══██║
  ██║ ╚████║███████╗██╔╝ ██╗╚██████╔╝██║  ██║██║  ██║
  ╚═╝  ╚═══╝╚══════╝╚═╝  ╚═╝ ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝{C_RESET}
{C_MAGENTA}  ✦ Interactive Discord Framework · Components V2 Edition ✦{C_RESET}

{C_BLUE}┌─────────────────────────────────────────────────────────────────────────────┐{C_RESET}
{C_BLUE}│{C_RESET} {C_BOLD}🤖 Bot Instance:{C_RESET}  {C_GREEN}{bot.user}{C_RESET} ({bot.user.id if bot.user else 0})
{C_BLUE}│{C_RESET} {C_BOLD}🌐 Distribution:{C_RESET}  {C_CYAN}{total_guilds:,}{C_RESET} Servers  •  {C_CYAN}{total_users:,}{C_RESET} Members  •  {C_CYAN}{total_channels:,}{C_RESET} Channels
{C_BLUE}│{C_RESET} {C_BOLD}⚡ Performance:{C_RESET}   Ping: {C_GREEN}{ping_ms}ms{C_RESET}  •  Shards: {C_GREEN}{bot.shard_count or 1}{C_RESET}  •  Prefix: {C_YELLOW}{DEFAULT_PREFIX}{C_RESET}
{C_BLUE}│{C_RESET} {C_BOLD}📦 Extensions:{C_RESET}    {C_GREEN}{len(bot.loaded_extensions)}/{len(EXTENSIONS)}{C_RESET} Modules Operational
{C_BLUE}│{C_RESET} {C_BOLD}🍃 Database:{C_RESET}      {mongo_status}
{C_BLUE}│{C_RESET} {C_BOLD}📡 Support Feed:{C_RESET}  {webhook_status}
{C_BLUE}│{C_RESET} {C_BOLD}🐍 Runtime:{C_RESET}       Python {sys.version.split()[0]}  •  discord.py {discord.__version__}
{C_BLUE}└─────────────────────────────────────────────────────────────────────────────┘{C_RESET}
{C_GREEN}✔ Nexora system core initialized and awaiting interactions.{C_RESET}
"""
    print(banner)

    # Dispatch Online notification to support webhook
    await bot.send_support_log(
        title="🚀 Nexora System Online & Operational",
        description=f"**{bot.user}** has successfully initialized and is serving across Discord.",
        color=0x57F287,
        fields=[
            {"name": "🤖 Bot Tag", "value": f"`{bot.user}`", "inline": True},
            {"name": "⚡ Ping", "value": f"`{ping_ms}ms`", "inline": True},
            {"name": "🌐 Servers", "value": f"`{total_guilds:,}`", "inline": True},
            {"name": "👥 Users", "value": f"`{total_users:,}`", "inline": True},
            {"name": "📦 Extensions", "value": f"`{len(bot.loaded_extensions)}/{len(EXTENSIONS)}`", "inline": True},
            {"name": "🍃 Database", "value": mongo_status, "inline": True},
        ],
        thumbnail_url=str(bot.user.display_avatar.url) if bot.user else None,
    )


@bot.event
async def on_guild_join(guild: discord.Guild):
    total_guilds = len(bot.guilds)
    logger.info("Joined new guild: %s (ID: %s, Members: %d)", guild.name, guild.id, guild.member_count or 0)
    await bot.send_support_log(
        title="📥 Joined New Server",
        description=f"Nexora was added to **{guild.name}**!",
        color=0x57F287,
        fields=[
            {"name": "Server Name", "value": guild.name, "inline": True},
            {"name": "Server ID", "value": f"`{guild.id}`", "inline": True},
            {"name": "Members", "value": f"`{guild.member_count:,}`", "inline": True},
            {"name": "Owner", "value": f"{guild.owner.mention if guild.owner else 'Unknown'}", "inline": True},
            {"name": "Total Guilds Now", "value": f"`{total_guilds:,}`", "inline": True},
        ],
        thumbnail_url=str(guild.icon.url) if guild.icon else None,
    )


@bot.event
async def on_guild_remove(guild: discord.Guild):
    total_guilds = len(bot.guilds)
    logger.info("Removed from guild: %s (ID: %s)", guild.name, guild.id)
    await bot.send_support_log(
        title="📤 Removed From Server",
        description=f"Nexora was removed from **{guild.name}**.",
        color=0xED4245,
        fields=[
            {"name": "Server Name", "value": guild.name, "inline": True},
            {"name": "Server ID", "value": f"`{guild.id}`", "inline": True},
            {"name": "Total Guilds Remaining", "value": f"`{total_guilds:,}`", "inline": True},
        ],
        thumbnail_url=str(guild.icon.url) if guild.icon else None,
    )


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    bot.bot_stats["messages_processed"] += 1
    content = message.content
    if not content:
        return
    # Fast-path guard: skip Context allocation if message doesn't start with prefix or bot mention
    lower_prefix = DEFAULT_PREFIX.lower()
    if not (content[:len(lower_prefix)].lower() == lower_prefix or content.startswith("<@")):
        return
    ctx = await bot.get_context(message)
    if ctx.valid:
        bot.bot_stats["commands_used"] += 1
        await bot.invoke(ctx)


async def main():
    if not DISCORD_TOKEN:
        logger.critical("❌ DISCORD_TOKEN is not set! Ensure your .env file or environment variable is configured on WispByte.")
        return
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception("Fatal error: %s", e)

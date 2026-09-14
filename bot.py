import asyncio
import io
import json
import logging
import os
import random
import sys
from datetime import datetime, timezone

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

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
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
    {"type": discord.ActivityType.playing, "name": "Truth or Dare | n!tod"},
    {"type": discord.ActivityType.playing, "name": "Would You Rather | n!wyr"},
    {"type": discord.ActivityType.playing, "name": "Rock Paper Scissors | n!rps"},
    {"type": discord.ActivityType.playing, "name": "Tic-Tac-Toe championship"},
    {"type": discord.ActivityType.playing, "name": "Minecraft hardcore in {server_count} realms"},
    {"type": discord.ActivityType.playing, "name": "Cyberpunk 2077 in 8K HDR"},
    {"type": discord.ActivityType.playing, "name": "Elden Ring: Shadow of the Erdtree"},
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
    {"type": discord.ActivityType.playing, "name": "synthwave in high fidelity"},

    # ── Watching ──
    {"type": discord.ActivityType.watching, "name": "over {user_count} incredible souls"},
    {"type": discord.ActivityType.watching, "name": "{server_count} servers thrive & grow"},
    {"type": discord.ActivityType.watching, "name": "One Piece episode {random_ep}"},
    {"type": discord.ActivityType.watching, "name": "the multiverse unfold"},
    {"type": discord.ActivityType.watching, "name": "for spam and rule breakers"},
    {"type": discord.ActivityType.watching, "name": "the audit logs closely"},
    {"type": discord.ActivityType.watching, "name": "anime in 4K with the community"},
    {"type": discord.ActivityType.watching, "name": "Interstellar for the 100th time"},
    {"type": discord.ActivityType.watching, "name": "matrix code rain in dark mode"},
    {"type": discord.ActivityType.watching, "name": "stars ignite across distant galaxies"},
    {"type": discord.ActivityType.watching, "name": "n!help requests in real time"},
    {"type": discord.ActivityType.watching, "name": "sunrise over {server_count} servers"},
    {"type": discord.ActivityType.watching, "name": "the timeline branch into infinity"},
    {"type": discord.ActivityType.watching, "name": "cosmic horizon & quantum events"},
    {"type": discord.ActivityType.watching, "name": "{channel_count} channels for good vibes"},
    {"type": discord.ActivityType.watching, "name": "Studio Ghibli masterpieces"},

    # ── Listening ──
    {"type": discord.ActivityType.listening, "name": "the echo of {user_count} voices"},
    {"type": discord.ActivityType.listening, "name": "whispers from other dimensions"},
    {"type": discord.ActivityType.listening, "name": "lo-fi hip hop radio 24/7"},
    {"type": discord.ActivityType.listening, "name": "synthwave beats to chill/code to"},
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
    {"type": discord.ActivityType.competing, "name": "Rock-Paper-Scissors World League"},
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
    "cogs.info.botinfo",
    "cogs.info.invite",
    "cogs.info.serverinfo",
    "cogs.info.userinfo",
    "cogs.info.avatar",
    "cogs.info.randomavatar",
    "cogs.info.roleinfo",
    "cogs.info.channelinfo",
    "cogs.owner.owner",
    "cogs.premium.vanity",
    "cogs.system.guideline_mode",
    "cogs.system.thread_manager",
    "cogs.utility.afk",
    "cogs.utility.steal",
    "cogs.utility.spotifyview",
    "cogs.utility.birthday_intro",
    "cogs.utility.remind",
    "cogs.utility.poll",
    "cogs.utility.calculator",
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
    "utils.error_handler",
]


class CharacterBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(DEFAULT_PREFIX, DEFAULT_PREFIX.swapcase()),
            intents=intents,
            help_command=None,
            case_insensitive=True,
        )

        self.bot_config = bot_config
        self.db_manager = DatabaseManager(DATABASE_ENABLED)
        self.premium_guild_ids = set()
        self.premium_guild_tiers = {}
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
            logger.info("⚡ App commands synced globally: %d commands", len(cmds))
        except Exception as e:
            logger.error("Global slash sync failed: %s", e)

        test_guild_id = int(os.getenv("TEST_GUILD_ID", "0"))
        if test_guild_id:
            try:
                guild = discord.Object(id=test_guild_id)
                cmds  = await self.tree.sync(guild=guild)
                logger.info("⚡ App commands synced to test guild %d: %d commands", test_guild_id, len(cmds))
            except Exception as e:
                logger.error("Guild sync failed (%d): %s", test_guild_id, e)

    # ── Premium ────────────────────────────────────────────────────────────────

    def load_premium_guilds(self):
        self.premium_guild_ids = set()
        logger.debug("Loaded premium guilds")

    def load_premium_tiers(self):
        self.premium_guild_tiers = {}
        logger.debug("Loaded premium tiers")

    def is_premium_guild(self, guild_id: int) -> bool:
        guild_str = str(guild_id)
        try:
            premium_data = load_premium_data()
            subscription = premium_data.get("subscriptions", {}).get(guild_str)
            if subscription:
                expires_at = subscription.get("expires_at")
                if expires_at and expires_at != "null":
                    try:
                        if datetime.now(timezone.utc) > datetime.fromisoformat(expires_at):
                            return False
                    except ValueError:
                        pass
                return subscription.get("tier", "FREE").lower() != "free"
        except Exception as e:
            logger.error("Error reading premium runtime data: %s", e)

        if guild_str in self.premium_guild_ids:
            return True
        return self.premium_guild_tiers.get(guild_str, "free").lower() != "free"

    # ── Support & System Logging ───────────────────────────────────────────────

    async def setup_log_channel(self):
        if not LOG_CHANNEL_ID:
            return
        try:
            self.log_channel = self.get_channel(int(LOG_CHANNEL_ID))
            if self.log_channel:
                logger.debug("Logging channel set to: %s", self.log_channel.name)
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

        # 2. Send via TextChannel if configured
        if self.log_channel:
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
{C_CYAN}{C_BOLD}  ███╗   ██╗███████╗██╗   ██╗ ██████╗ ██████╗  █████╗ 
  ████╗  ██║██╔════╝╚██╗ ██╔╝██╔═══██╗██╔══██╗██╔══██╗
  ██╔██╗ ██║█████╗   ╚████╔╝ ██║   ██║██████╔╝███████║
  ██║╚██╗██║██╔══╝    ╚██╔╝  ██║   ██║██╔══██╗██╔══██║
  ██║ ╚████║███████╗   ██║   ╚██████╔╝██║  ██║██║  ██║
  ╚═╝  ╚═══╝╚══════╝   ╚═╝    ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝{C_RESET}
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
    ctx = await bot.get_context(message)
    if ctx.valid:
        bot.bot_stats["commands_used"] += 1
    await bot.invoke(ctx)


async def main():
    await bot.start(DISCORD_TOKEN)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception("Fatal error: %s", e)

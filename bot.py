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

from utils.config import DATABASE_ENABLED, DISCORD_TOKEN, LOG_CHANNEL_ID, OWNER_ID
from utils.database import DatabaseManager

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
    {"type": discord.ActivityType.watching, "name": "the multiverse unfold"},
    {"type": discord.ActivityType.listening, "name": "whispers from other dimensions"},
    {"type": discord.ActivityType.playing, "name": "with quantum possibilities"},
    {
        "type": discord.ActivityType.streaming,
        "name": "helping across servers",
        "url": "https://discord.gg/f5b85pRgq9",
    },
    {"type": discord.ActivityType.playing, "name": "in {server_count} different realities"},
    {"type": discord.ActivityType.listening, "name": "the echo of {user_count} voices"},
    {"type": discord.ActivityType.competing, "name": "the Turing Test Championship"},
    {"type": discord.ActivityType.watching, "name": f"One Piece episode {random.randint(1, 1150)}"},
    {"type": discord.ActivityType.playing, "name": "chess with the universe"},
    {"type": discord.ActivityType.playing, "name": "with n!help and /help"},
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
    "cogs.games.gamesstats",
    "cogs.games.guess",
    "cogs.games.say",
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
    "cogs.moderation.snipe",
    "cogs.moderation.voicemove",
    "cogs.moderation.ban",
    "cogs.moderation.tempban",
    "cogs.moderation.kick",
    "cogs.premium_main",
    
]


class CharacterBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        super().__init__(
            command_prefix=commands.when_mentioned_or(DEFAULT_PREFIX),
            intents=intents,
            help_command=None,
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
        for ext in EXTENSIONS:
            try:
                await self.load_extension(ext)
                self.loaded_extensions.add(ext)
                logger.info("Loaded extension: %s", ext)
            except Exception as e:
                logger.error("Failed to load %s: %s", ext, e)

    async def _sync_app_commands(self):
        if not bot_settings.get("auto_sync_commands", True):
            logger.info("Auto sync disabled in config.")
            return

        try:
            cmds = await self.tree.sync()
            logger.info("App commands synced globally: %d", len(cmds))
        except Exception as e:
            logger.error("Global sync failed: %s", e)

        test_guild_id = int(os.getenv("TEST_GUILD_ID", "0"))
        if test_guild_id:
            try:
                guild = discord.Object(id=test_guild_id)
                cmds  = await self.tree.sync(guild=guild)
                logger.info("App commands synced to guild %d: %d", test_guild_id, len(cmds))
            except Exception as e:
                logger.error("Guild sync failed (%d): %s", test_guild_id, e)

    # ── Premium ────────────────────────────────────────────────────────────────

    def load_premium_guilds(self):
        self.premium_guild_ids = set()
        logger.info("Loaded premium guilds (placeholder)")

    def load_premium_tiers(self):
        self.premium_guild_tiers = {}
        logger.info("Loaded premium tiers (placeholder)")

    def is_premium_guild(self, guild_id: int) -> bool:
        guild_str = str(guild_id)
        try:
            path = os.path.join("data", "premium_data.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    premium_data = json.load(f)
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
            logger.error("Error reading premium_data.json: %s", e)

        if guild_str in self.premium_guild_ids:
            return True
        return self.premium_guild_tiers.get(guild_str, "free").lower() != "free"

    # ── Logging ────────────────────────────────────────────────────────────────

    async def setup_log_channel(self):
        if not LOG_CHANNEL_ID:
            return
        try:
            self.log_channel = self.get_channel(int(LOG_CHANNEL_ID))
            if self.log_channel:
                logger.info("Logging channel set to: %s", self.log_channel.name)
        except Exception as e:
            logger.error("Error setting up logging channel: %s", e)

    async def send_log(
        self,
        log_type: str,
        title: str,
        description: str,
        color: int = 0x0099FF,
        fields: list[dict] | None = None,
    ):
        if not self.log_channel:
            return
        try:
            embed = discord.Embed(
                title=f"📊 {title}",
                description=description,
                color=color,
                timestamp=datetime.now(timezone.utc),
            )
            if fields:
                for field in fields:
                    embed.add_field(
                        name=field["name"],
                        value=field["value"],
                        inline=field.get("inline", True),
                    )
            embed.set_footer(text=f"CharacterBot Logs - {log_type}")
            await self.log_channel.send(embed=embed)
        except Exception as e:
            logger.error("Error sending log: %s", e)

    # ── Activity rotation ──────────────────────────────────────────────────────

    async def get_dynamic_activity(self):
        try:
            server_count  = len(self.guilds)
            user_count    = sum(g.member_count or 0 for g in self.guilds)
            channel_count = len(list(self.get_all_channels()))
            template = random.choice(CREATIVE_ACTIVITIES)
            name = template["name"].format(
                server_count=server_count,
                user_count=user_count,
                channel_count=channel_count,
            )
            if template["type"] == discord.ActivityType.streaming:
                return discord.Streaming(name=name, url=template.get("url", "https://discord.gg/f5b85pRgq9"))
            return discord.Activity(type=template["type"], name=name)
        except Exception as e:
            logger.error("Error generating dynamic activity: %s", e)
            return discord.Activity(type=discord.ActivityType.watching, name="for errors...")

    @tasks.loop(minutes=5)
    async def update_activity(self):
        try:
            activity = await self.get_dynamic_activity()
            await self.change_presence(activity=activity, status=discord.Status.online)
            logger.info(f"Updated activity to: {activity.name}")
        except Exception as e:
            logger.error(f"Error updating activity: {e}")

bot = CharacterBot()


@bot.event
async def on_ready():
    await bot.setup_log_channel()
    logger.info("🚀 %s has awakened!", bot.user)

    if bot_settings.get("status_rotation", True) and not bot.update_activity.is_running():
        bot.update_activity.start()

    # Log MongoDB status on ready
    if bot.mongo_db is not None:
        logger.info("🍃 MongoDB Atlas: connected ✅")
    else:
        logger.info("🍃 MongoDB Atlas: not connected (JSON fallback active)")

    logger.info("🎭 Loaded %d/%d extensions", len(bot.loaded_extensions), len(EXTENSIONS))
    logger.info("🎭 All premium features initialized")


@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return
    bot.bot_stats["messages_processed"] += 1
    ctx = await bot.get_context(message)
    if ctx.valid:
        bot.bot_stats["commands_used"] += 1
    await bot.invoke(ctx)


@bot.event
async def on_command_error(ctx: commands.Context, error: commands.CommandError):
    if isinstance(error, commands.CommandNotFound):
        return
    if isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Arguments",
            description=(
                f"Usage: `{ctx.prefix}{ctx.command.qualified_name}`\n"
                f"Missing: `{error.param.name}`"
            ),
            color=discord.Color.red(),
        )
        await ctx.send(embed=embed)
        return
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Missing permissions for this command.")
        return
    if isinstance(error, commands.MissingRole | commands.MissingAnyRole):
        await ctx.send("❌ Missing required role for this command.")
        return
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You do not have access to this command.")
        return
    if isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Slow down. Try again in `{error.retry_after:.1f}s`.")
        return
    if isinstance(error, commands.MaxConcurrencyReached):
        await ctx.send("⚠️ This command is already running.")
        return


@bot.event
async def on_command_error(ctx, error):
    """Global error handler for all commands"""
    if isinstance(error, commands.CommandNotFound):
        print("Unknown command invoked.", ctx.command)
        return  # Silently ignore unknown commands
    
    elif isinstance(error, commands.MissingRequiredArgument):
        embed = discord.Embed(
            title="❌ Missing Arguments",
            description=f"**Usage:** `{ctx.prefix}{ctx.command.qualified_name}`\n\n"
                       f"Missing: `{error.param.name}`\n"
                       f"**Example:** `{ctx.prefix}{ctx.command} 123456 ultra 30`",
            color=discord.Color.red()
        )
        await ctx.send(embed=embed)
    
    elif isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ Missing permissions! You need `Manage Roles` or higher.")
    
    elif isinstance(error, commands.MissingRole):
        await ctx.send("❌ Missing required role!")
    
    elif isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You don't have access to this command!")
    
    elif isinstance(error, commands.CommandOnCooldown):
        await ctx.send(f"⏳ Slow down! Try again in **{error.retry_after:.1f}s**")
    
    elif isinstance(error, commands.MaxConcurrencyReached):
        await ctx.send("⚠️ This command is already running!")
    else:
        logger.error(f"Error in command '{ctx.command}': {error}")
        await ctx.send("❌ An unexpected error occurred. The issue has been logged.")

async def main():
    await asyncio.sleep(20)
    await bot.start(DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.exception("Fatal error: %s", e)

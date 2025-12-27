import discord
import logging
import os
import random
import asyncio
from discord.ext import commands, tasks
from datetime import datetime
from utils.config import DISCORD_TOKEN, LOG_CHANNEL_ID, DATABASE_ENABLED, OWNER_ID
from utils.database import DatabaseManager
import sys, io
import json
import aiohttp
# --- Set up stdout/stderr encoding (from your original code) ---
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

# --- Logging setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    """Loads bot configuration from a JSON file."""
    try:
        with open('config/bot_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.critical("bot_config.json not found! Please create it in the 'config' folder.")
        raise SystemExit(1)
    except json.JSONDecodeError:
        logger.critical("bot_config.json is not a valid JSON file!")
        raise SystemExit(1)

try:
    bot_config = load_config()
    DEFAULT_PREFIX = bot_config['bot_settings']['default_prefix']
except (KeyError, ValueError) as e:
    logger.critical(f"Error reading values from bot_config.json: {e}")
    raise SystemExit(1)


# --- Your original global variables ---
CREATIVE_ACTIVITIES = [
    {"type": discord.ActivityType.watching, "name": "the multiverse unfold"},
    {"type": discord.ActivityType.listening, "name": "whispers from other dimensions"},
    {"type": discord.ActivityType.playing, "name": "with quantum possibilities"},
    {"type": discord.ActivityType.streaming, "name": "helping across servers", "url": "https://discord.gg/f5b85pRgq9"},
    {"type": discord.ActivityType.playing, "name": "in {server_count} different realities"},
    {"type": discord.ActivityType.listening, "name": "the echo of {user_count} voices"},
    {"type": discord.ActivityType.competing, "name": "the Turing Test Championship"},
    {"type": discord.ActivityType.watching, "name": f"One Piece episodes {random.randint(1,1150)}"},
    {"type": discord.ActivityType.playing, "name": "chess with the universe"},
    {"type": discord.ActivityType.playing, "name": "with n!help and /help"}
]

PREFERRED_EMOJIS = {
    "positive": {"name": "happyface", "id": 1395484920658526318, "fallback": "😊"},
    "negative": {"name": "sadface",  "id": None, "fallback": "😢"},
    "funny":    {"name": "lol",      "id": None, "fallback": "😄"},
    "angry":    {"name": "angry",    "id": None, "fallback": "😠"},
    "confused": {"name": "confused", "id": None, "fallback": "🤔"},
    "thanks":   {"name": "thanks",   "id": None, "fallback": "🙏"},
    "question": {"name": "question", "id": None, "fallback": "❓"},
}

class CharacterBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.all()
        intents.message_content = True
        intents.members = True
        intents.presences = True

        # --- UPDATED: Use the prefix from the config file ---
        super().__init__(command_prefix=DEFAULT_PREFIX, intents=intents, help_command=None)
        self.bot_config = bot_config
        self.db_manager = DatabaseManager(DATABASE_ENABLED)
        self.premium_guild_ids = set()
        self.premium_guild_tiers = {}
        self.session = None
        self.load_premium_guilds()
        self.load_premium_tiers()

        self.bot_stats = {
            'messages_processed': 0,
            'conversations_today': 0,
            'commands_used': 0,
            'errors_encountered': 0,
            'start_time': datetime.now()
        }
        self.log_channel = None
        self.rate_limits = {}

    def load_premium_guilds(self):
        self.premium_guild_ids = set()
        logger.info("Loaded premium guilds (placeholder)")

    def load_premium_tiers(self):
        self.premium_guild_tiers = {}
        logger.info("Loaded premium tiers (placeholder)")
    
    def is_premium_guild(self, guild_id) -> bool:
        """Check if guild has premium access using multiple sources"""
        guild_str = str(guild_id)
    
        # Method 1: Check premium_data.json (primary source)
        try:
            path = os.path.join("data", "premium_data.json")
            if os.path.exists(path):
                with open(path, "r", encoding="utf-8") as f:
                    premium_data = json.load(f)
                if guild_str in premium_data.get("subscriptions", {}):
                    subscription = premium_data["subscriptions"][guild_str]
                    expires_at = subscription.get("expires_at")
                    if expires_at and expires_at != "null" and expires_at is not None:
                        try:
                            exp_date = datetime.fromisoformat(expires_at)
                            if datetime.now() > exp_date:
                                return False  # Expired
                        except ValueError:
                            pass
                    tier = subscription.get("tier", "FREE").lower()
                    return tier != "free"
        except Exception as e:
            logger.error(f"Error reading premium_data.json: {e}")
    
        # Method 2: Check cached premium guilds set (fallback)
        if hasattr(self, 'premium_guild_ids'):
            return guild_str in self.premium_guild_ids
    
        # Method 3: Check premium tier dict (fallback)
        if hasattr(self, 'premium_guild_tiers'):
            tier = self.premium_guild_tiers.get(guild_str, "free")
            return tier != "free"
    
        # Default to False
        return False
    
    async def setup_log_channel(self):
        if LOG_CHANNEL_ID:
            try:
                self.log_channel = self.get_channel(int(LOG_CHANNEL_ID))
                if self.log_channel:
                    logger.info(f"Logging channel set to: {self.log_channel.name}")
            except Exception as e:
                logger.error(f"Error setting up logging channel: {e}")
    async def setup_hook(self):
        """Called when the bot is starting up"""
        # Initialize aiohttp session
        self.session = aiohttp.ClientSession()
    async def send_log(self, log_type: str, title: str, description: str, color: int = 0x0099ff, fields: list = None):
        if not self.log_channel:
            return
        try:
            embed = discord.Embed(
                title=f"📊 {title}", description=description, color=color, timestamp=datetime.now()
            )
            if fields:
                for f in fields:
                    embed.add_field(name=f['name'], value=f['value'], inline=f.get('inline', True))
            embed.set_footer(text=f"CharacterBot Logs - {log_type}")
            await self.log_channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error sending log: {e}")

    async def get_dynamic_activity(self):
        try:
            server_count = len(self.guilds)
            user_count = sum(g.member_count for g in self.guilds if g.member_count)
            channel_count = len(list(self.get_all_channels()))
            t = random.choice(CREATIVE_ACTIVITIES)
            name = t["name"].format(server_count=server_count, user_count=user_count, channel_count=channel_count)
            if t["type"] == discord.ActivityType.streaming:
                return discord.Streaming(name=name, url=t.get("url", "https://discord.gg/SrFxunWVCf"))
            return discord.Activity(type=t["type"], name=name)
        except Exception as e:
            logger.error(f"Error generating dynamic activity: {e}")
            return discord.Activity(type=discord.ActivityType.watching, name="for errors...")

    @tasks.loop(minutes=5)
    async def update_activity(self):
        try:
            activity = await self.get_dynamic_activity()
            await self.change_presence(activity=activity, status=discord.Status.online)
            logger.info(f"Updated activity to: {activity.name}")
        except Exception as e:
            logger.error(f"Error updating activity: {e}")

    async def setup_hook(self):
        # load extensions (cogs)
        self.session = aiohttp.ClientSession()
        for ext in [
            # Core utilities
            "cogs.core.status",
            "cogs.core.help",
        
            # Analytics
            "cogs.analytics.analytics",
            #fun
            "cogs.fun.confession",
            "cogs.fun.ship",
            "cogs.fun.kick",
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
            
            # Games
            "cogs.games.guess",
            "cogs.games.say",
        
            # Info commands
            "cogs.info.botinfo",
            "cogs.info.invite",
            "cogs.info.serverinfo",
            "cogs.info.userinfo",
            "cogs.info.avatar",
            "cogs.info.randomavatar",
            "cogs.info.roleinfo",
            "cogs.info.channelinfo",
        
            # Owner commands
            "cogs.owner.owner",
            "cogs.owner.premium",
        
            # Premium / special features
            "cogs.premium.vanity",

            # system/special command
            "cogs.system.guideline_mode",
            "cogs.system.thread_manager",

            #utility
            "cogs.utility.afk",
            "cogs.utility.steal",
            "cogs.utility.spotifyview",

            # Moderation
            "cogs.moderation.snipe"
        ]:
            try:
                await self.load_extension(ext)
                logger.info(f"Loaded extension: {ext}")
            except Exception as e:
                logger.error(f"Failed to load {ext}: {e}")

        # IMPORTANT: Sync the app command tree
        try:
            # Global sync
            if bot_config['bot_settings']['auto_sync_commands']:
                cmds = await self.tree.sync()
                logger.info(f"App commands synced globally: {len(cmds)}")
        except Exception as e:
            logger.error(f"Global sync failed: {e}")

        # Optional: per-guild fast sync during development
        try:
            TEST_GUILD_ID = 1087039578931724468
            if TEST_GUILD_ID:
                guild = discord.Object(id=TEST_GUILD_ID)
                cmds = await self.tree.sync(guild=guild)
                logger.info(f"App commands synced to guild {TEST_GUILD_ID}: {len(cmds)}")
        except Exception as e:
            logger.error(f"Guild sync failed: {e}")

bot = CharacterBot()

@bot.event
async def on_ready():
    await bot.setup_log_channel()
    logger.info(f'🚀 {bot.user} has awakened!')
    if not bot.update_activity.is_running() and bot_config['bot_settings']['status_rotation']:
        bot.update_activity.start()
    
    # Re-sync on ready in case it was missed during setup_hook
    # Only syncs if auto_sync is enabled and sync wasn't successful before
    if bot_config['bot_settings']['auto_sync_commands']:
        try:
            synced = await bot.tree.sync()
            logger.info(f"Synced {len(synced)} command(s)")
        except Exception as e:
            logger.error(f"Failed to sync commands on ready: {e}")
    
    logger.info("🎭 All premium features initialized")

@bot.event
async def on_message(message: discord.Message):
    if message.author.bot or not message.guild:
        return

    await bot.process_commands(message)

    if message.content.startswith(bot.command_prefix):
        bot.bot_stats['commands_used'] += 1
        return


if __name__ == "__main__":
    if not DISCORD_TOKEN:
        logger.critical("Missing DISCORD_TOKEN")
        raise SystemExit(1)
    bot.run(DISCORD_TOKEN)
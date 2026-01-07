import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
import logging
import json
import io

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --- NEW: A custom check decorator for owner commands ---
def is_owner():
    async def predicate(ctx):
        # We can use the bot's internal is_owner method, or a simple ID check
        return ctx.author.id == ctx.bot.owner_id
    return commands.check(predicate)

class Owner(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(name="debug_commands", description="List all registered commands.",aliases=['debug'])
    @is_owner()
    async def debug_commands(self, ctx: commands.Context):
        commands_list = [cmd.name for cmd in self.bot.tree.get_commands()]
        
        try:
            embed_color = int(self.bot.bot_config['ui_settings']['embed_color'], 16)
        except (KeyError, ValueError):
            embed_color = 0x0099ff

        embed = discord.Embed(
            title="Registered Commands",
            description=f"Found {len(commands_list)} commands:\n" + "\n".join(commands_list),
            color=embed_color
        )
        await ctx.send(embed=embed, ephemeral=True)
    @commands.command()
    @commands.is_owner()
    async def activate(self, ctx, guild_id: str, tier: str):
        """!activate 123456789 ULTRA - Owner gives premium"""
        data = self._get_data()
        data["subscriptions"][guild_id] = {"tier": tier.upper(), "expires_at": None}
        self._save_data(data)
        await ctx.send(f"✅ **{tier}** activated for {guild_id}")

    @commands.hybrid_command(name="force_resync", description="Force resync all commands.")
    @is_owner()
    async def force_resync(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        try:
            guild_synced = await self.bot.tree.sync(guild=ctx.guild)
            global_synced = await self.bot.tree.sync()
            
            await ctx.followup.send(
                f"✅ Resynced!\nGuild: {len(guild_synced)} commands\nGlobal: {len(global_synced)} commands", 
                ephemeral=True
            )
        except Exception as e:
            await ctx.followup.send(f"❌ Resync failed: {e}", ephemeral=True)

    @commands.hybrid_command(name="backup", description="Create a backup of bot stats.")
    @is_owner()
    async def backup(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        backup_data = {
            'stats': self.bot.bot_stats,
            'timestamp': datetime.now().isoformat(),
        }
        filename = f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        
        # Write to a file-like object in memory instead of the disk
        data_bytes = json.dumps(backup_data, indent=2, ensure_ascii=False).encode('utf-8')
        file = discord.File(io.BytesIO(data_bytes), filename=filename)
        
        await ctx.followup.send("✅ Backup Created!", file=file, ephemeral=True)

    @commands.hybrid_command(name="resetstats", description="Reset bot statistics.")
    @is_owner()
    async def resetstats(self, ctx: commands.Context):
        self.bot.bot_stats = {
            'messages_processed': 0,
            'conversations_today': 0,
            'commands_used': 0,
            'errors_encountered': 0,
            'api_calls_made': 0,
            'start_time': datetime.now()
        }
        try:
            embed_color = int(self.bot.bot_config['ui_settings']['success_color'], 16)
        except (KeyError, ValueError):
            embed_color = 0x00ff00

        embed = discord.Embed(title="✅ Statistics Reset", description="Bot statistics have been reset.", color=embed_color)
        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="sync", description="Sync slash commands globally.")
    @commands.is_owner()
    @app_commands.describe(guild_id="Optional: Sync to a specific guild ID for testing.")
    async def sync(self, ctx: commands.Context, guild_id: str = None):
        # Check if it's a slash command interaction
        if ctx.interaction:
            await ctx.defer(ephemeral=True)
        
        try:
            if guild_id:
                guild_obj = discord.Object(id=int(guild_id))
                synced = await self.bot.tree.sync(guild=guild_obj)
                message = f"✅ Synced {len(synced)} commands to guild `{guild_id}`."
            else:
                synced = await self.bot.tree.sync()
                message = f"✅ Synced {len(synced)} commands globally."
            
            await ctx.send(message, ephemeral=True if ctx.interaction else False)
        except Exception as e:
            await ctx.send(f"❌ Sync failed: {e}", ephemeral=True if ctx.interaction else False)
    
    @commands.hybrid_command(name="unsync", description="Clear all slash commands.")
    @is_owner()
    async def unsync(self, ctx: commands.Context):
        await ctx.defer(ephemeral=True)
        try:
            self.bot.tree.clear_commands(guild=None)
            await self.bot.tree.sync()
            
            await ctx.followup.send("✅ All global slash commands have been cleared.", ephemeral=True)
        except Exception as e:
            await ctx.followup.send(f"❌ Unsync failed: {e}", ephemeral=True)


async def setup(bot):
    # This is a bit of a workaround to get the OWNER_ID from the config file.
    # A cleaner approach is to set bot.owner_id in your main bot file.
    OWNER_ID =  bot.bot_config.get('owner_id')
    try:
        if isinstance(OWNER_ID, (int, str)):
            bot.owner_id = int(OWNER_ID)
        else:
            bot.owner_id = OWNER_ID
    except (ValueError, TypeError):
        bot.owner_id = None
        logger.error("OWNER_ID is not a valid integer. Owner-only commands may not work.")

    await bot.add_cog(Owner(bot))
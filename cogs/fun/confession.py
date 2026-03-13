import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import datetime
import logging

logger = logging.getLogger(__name__)

class Confession(commands.Cog):
    """Anonymous confession system. Logging and tracing restricted to Bot Owner only."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

        # Use a stable project-level data folder
        base_path = os.getcwd()
        self.data_dir = os.path.join(base_path, "data", "confessions")
        os.makedirs(self.data_dir, exist_ok=True)

        self.config_file = os.path.join(self.data_dir, "confessions.json")
        self.log_file = os.path.join(self.data_dir, "confession_logs.json")

        # in-memory storage
        self.guild_data: dict[str, dict] = {}
        self.identity_logs: dict[str, list] = {}

        self._load_all()

    # ---------- persistence ----------

    def _load_all(self):
        """Load both config and logs from disk."""
        # Load config
        if os.path.exists(self.config_file):
            try:
                with open(self.config_file, "r", encoding="utf-8") as f:
                    self.guild_data = json.load(f)
                logger.info("Confession config loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load confessions config: {e}")
                self.guild_data = {}
        else:
            self.guild_data = {}

        # Load logs - BACKWARD COMPATIBILITY
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, "r", encoding="utf-8") as f:
                    self.identity_logs = json.load(f)
                
                # FIX: Migrate old log format to new format
                for gid, logs in self.identity_logs.items():
                    for i, entry in enumerate(logs):
                        if "id" in entry and "confession_number" not in entry:
                            entry["confession_number"] = entry.pop("id")
                        if "user" in entry and "username" not in entry:
                            entry["username"] = entry.pop("user")
                
                logger.info("Confession logs loaded and migrated successfully")
            except Exception as e:
                logger.error(f"Failed to load identity logs: {e}")
                self.identity_logs = {}
        else:
            self.identity_logs = {}

    def _save_config(self):
        """Save guild config to disk."""
        try:
            with open(self.config_file, "w", encoding="utf-8") as f:
                json.dump(self.guild_data, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save confessions config: {e}")

    def _save_log(self):
        """Save identity logs to disk."""
        try:
            with open(self.log_file, "w", encoding="utf-8") as f:
                json.dump(self.identity_logs, f, indent=4, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Failed to save identity logs: {e}")

    def _get_guild_cfg(self, guild: discord.Guild) -> dict:
        """Get or initialize guild config."""
        gid = str(guild.id)
        if gid not in self.guild_data:
            self.guild_data[gid] = {"channel_id": None, "counter": 0}
        return self.guild_data[gid]

    def _get_confession_number(self, entry: dict) -> int:
        """Get confession number from entry (supports both old and new format)."""
        return entry.get("confession_number") or entry.get("id", 0)

    # ---------- commands ----------

    @commands.hybrid_command(
        name="confessionsetup",
        description="Set the confession channel."
    )
    @commands.has_permissions(manage_guild=True)
    async def confession_setup(self, ctx: commands.Context, channel: discord.TextChannel):
        """Setup confession channel for the server."""
        cfg = self._get_guild_cfg(ctx.guild)
        cfg["channel_id"] = channel.id
        cfg.setdefault("counter", 0)
        self._save_config()
        await ctx.send(f"✅ Confession channel set to {channel.mention}")

    @commands.hybrid_command(
        name="confessionlist",
        description="[ADMIN ONLY] List all configured confession channels."
    )
    @commands.has_permissions(manage_guild=True)
    async def confession_list(self, ctx: commands.Context):
        """List all servers with configured confession channels."""
        if not self.guild_data:
            return await ctx.send("❌ No confession channels configured yet.", ephemeral=True)

        embed = discord.Embed(title="📋 All Confession Channels", color=discord.Color.blue())
        
        for gid, cfg in self.guild_data.items():
            guild = self.bot.get_guild(int(gid))
            if guild:
                channel = guild.get_channel(cfg.get("channel_id"))
                channel_mention = channel.mention if channel else f"ID: {cfg.get('channel_id')} (deleted)"
                embed.add_field(
                    name=guild.name[:256],
                    value=f"{channel_mention}\nConfessions: {cfg.get('counter', 0)}",
                    inline=False
                )
            else:
                embed.add_field(
                    name=f"Server ID: {gid}",
                    value=f"Channel ID: {cfg.get('channel_id')}\nConfessions: {cfg.get('counter', 0)}",
                    inline=False
                )

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="confess",
        description="Send an anonymous confession."
    )
    async def confess(self, ctx: commands.Context, *, text: str):
        """Send anonymous confession to configured channel."""
        cfg = self._get_guild_cfg(ctx.guild)
        channel_id = cfg.get("channel_id")

        if not channel_id:
            return await ctx.send("❌ Confession channel not set. Use `/confessionsetup <channel>`", ephemeral=True)

        channel = ctx.guild.get_channel(channel_id)
        if not channel:
            return await ctx.send("❌ The saved confession channel no longer exists.", ephemeral=True)

        # Increment counter and save
        cfg["counter"] = int(cfg.get("counter", 0)) + 1
        count = cfg["counter"]
        self._save_config()

        # Log identity with NEW format
        gid = str(ctx.guild.id)
        if gid not in self.identity_logs:
            self.identity_logs[gid] = []

        log_entry = {
            "confession_number": count,
            "username": str(ctx.author),
            "user_id": ctx.author.id,
            "user_discriminator": ctx.author.discriminator,
            "content": text,
            "timestamp": datetime.datetime.now().isoformat(),
            "channel_id": channel_id
        }
        
        self.identity_logs[gid].append(log_entry)
        self._save_log()

        # Send public confession
        embed = discord.Embed(
            title=f"🕊️ Confession #{count}",
            description=text,
            color=discord.Color.random(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        await channel.send(embed=embed)

        # User feedback
        feedback = f"✅ Sent as confession **#{count}**"
        if ctx.interaction:
            await ctx.send(feedback, ephemeral=True)
        else:
            try:
                await ctx.message.delete()
            except Exception:
                pass

    @commands.hybrid_command(
        name="confessiontrace",
        description="[OWNER ONLY] Trace a confession by number."
    )
    @commands.is_owner()
    async def confession_trace(self, ctx: commands.Context, number: int):
        """Trace confession author (Bot Owner only)."""
        gid = str(ctx.guild.id)
        logs = self.identity_logs.get(gid, [])
        
        # FIXED: Handle both old ("id") and new ("confession_number") formats
        entry = next((item for item in logs if self._get_confession_number(item) == number), None)
        
        if not entry:
            return await ctx.send(f"❌ Confession **#{number}** not found in logs.", ephemeral=True)

        # Handle both old and new field names
        conf_num = self._get_confession_number(entry)
        username = entry.get("username") or entry.get("user", "Unknown")
        user_id = entry.get("user_id", "Unknown")
        timestamp = entry.get("timestamp") or entry.get("time", "Unknown")
        content = entry.get("content", "No content")

        embed = discord.Embed(
            title=f"🔍 Trace: Confession #{conf_num}",
            color=discord.Color.red()
        )
        embed.add_field(
            name="👤 Author",
            value=f"`{username}`\nID: `{user_id}`",
            inline=False
        )
        embed.add_field(
            name="📝 Content",
            value=content[:1024],
            inline=False
        )
        embed.add_field(
            name="📊 Details",
            value=f"Channel: <#{entry.get('channel_id', 'Unknown')}>\nLogged: {timestamp}",
            inline=False
        )

        await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(
        name="confessionstats",
        description="[OWNER ONLY] Show confession statistics."
    )
    @commands.is_owner()
    async def confession_stats(self, ctx: commands.Context):
        """Show confession statistics for current guild."""
        gid = str(ctx.guild.id)
        cfg = self._get_guild_cfg(ctx.guild)
        logs = self.identity_logs.get(gid, [])
        
        embed = discord.Embed(title="📊 Confession Stats", color=discord.Color.green())
        embed.add_field(name="Total Confessions", value=str(cfg.get("counter", 0)), inline=True)
        embed.add_field(name="Logged Entries", value=str(len(logs)), inline=True)
        channel_id = cfg.get("channel_id")
        channel = ctx.guild.get_channel(channel_id) if channel_id else None
        embed.add_field(
            name="Channel", 
            value=channel.mention if channel else "Not set", 
            inline=True
        )
        
        await ctx.send(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(Confession(bot))

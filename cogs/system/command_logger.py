"""
cogs/system/command_logger.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Universal Command Audit & Logging Engine for Nexora.

Captures all prefix commands and slash / interaction commands,
formatting rich audit records and dispatching them to configured
command log channels (global and server-specific).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    SUCCESS_COLOR,
    ERROR_COLOR,
    WARNING_COLOR,
    CYAN_COLOR,
)

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join("data", "command_logs_config.json")


class CommandLogger(commands.Cog):
    """Logs executed prefix commands and slash commands to dedicated audit channels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._ensure_config()
        self.config = self._load_config()

    def _ensure_config(self):
        os.makedirs("data", exist_ok=True)
        if not os.path.exists(CONFIG_PATH):
            default_global = os.getenv("CMD_LOG_CHANNEL_ID") or os.getenv("COMMAND_LOG_CHANNEL_ID") or os.getenv("LOG_CHANNEL_ID")
            initial_data = {
                "enabled": True,
                "global_channel_id": int(default_global) if default_global and default_global.isdigit() else None,
                "guild_channels": {},
            }
            try:
                with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                    json.dump(initial_data, f, indent=2)
            except Exception as e:
                logger.error("Failed to create command_logs_config.json: %s", e)

    def _load_config(self) -> dict:
        try:
            if os.path.exists(CONFIG_PATH):
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error("Failed to read command_logs_config.json: %s", e)
        return {
            "enabled": True,
            "global_channel_id": None,
            "guild_channels": {},
        }

    def _save_config(self):
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self.config, f, indent=2)
        except Exception as e:
            logger.error("Failed to save command_logs_config.json: %s", e)

    def get_global_log_channel_id(self) -> Optional[int]:
        cid = self.config.get("global_channel_id")
        if not cid:
            env_val = os.getenv("CMD_LOG_CHANNEL_ID") or os.getenv("COMMAND_LOG_CHANNEL_ID") or os.getenv("LOG_CHANNEL_ID")
            if env_val and env_val.strip().isdigit():
                return int(env_val.strip())
        return cid

    def get_guild_log_channel_id(self, guild_id: int) -> Optional[int]:
        guild_channels = self.config.get("guild_channels", {})
        return guild_channels.get(str(guild_id))

    async def _dispatch_log(self, embed: discord.Embed, guild_id: Optional[int] = None):
        """Sends the command log embed to global channel and/or guild-specific channel."""
        if not self.config.get("enabled", True):
            return

        target_channel_ids = set()

        # 1. Global log channel (e.g. from CMD_LOG_CHANNEL_ID or LOG_CHANNEL_ID)
        global_cid = self.get_global_log_channel_id()
        if global_cid:
            target_channel_ids.add(global_cid)

        # 2. Guild-specific log channel if configured
        if guild_id:
            guild_cid = self.get_guild_log_channel_id(guild_id)
            if guild_cid:
                target_channel_ids.add(guild_cid)

        for cid in target_channel_ids:
            try:
                channel = self.bot.get_channel(cid)
                if not channel:
                    channel = await self.bot.fetch_channel(cid)
                if channel and hasattr(channel, "send"):
                    await channel.send(embed=embed)
            except Exception as e:
                logger.debug("Could not dispatch command log to channel %s: %s", cid, e)

    # ── Prefix Command Completion Listener ────────────────────────────────────

    @commands.Cog.listener()
    async def on_command_completion(self, ctx: commands.Context):
        if not ctx.command:
            return

        cmd_name = ctx.command.qualified_name
        user = ctx.author
        guild = ctx.guild
        channel = ctx.channel

        clean_content = ctx.message.content
        if len(clean_content) > 900:
            clean_content = clean_content[:900] + "... [truncated]"

        embed = discord.Embed(
            title=f"⚡ Prefix Command Executed: `{ctx.prefix}{cmd_name}`",
            color=BRAND_COLOR,
            timestamp=datetime.now(timezone.utc),
        )

        embed.set_author(name=f"{user} ({user.id})", icon_url=user.display_avatar.url)
        embed.add_field(name="👤 User", value=f"{user.mention} (`{user.id}`)", inline=True)

        if guild:
            ch_mention = channel.mention if hasattr(channel, "mention") else f"#{channel.name}"
            embed.add_field(name="📍 Location", value=f"**{guild.name}** (`{guild.id}`)\n{ch_mention}", inline=True)
        else:
            embed.add_field(name="📍 Location", value="Direct Messages (DM)", inline=True)

        embed.add_field(name="📝 Message Content", value=f"```{clean_content}```" if clean_content else "*None*", inline=False)

        if hasattr(ctx.message, "jump_url"):
            embed.add_field(name="🔗 Reference", value=f"[Jump to Message]({ctx.message.jump_url})", inline=True)

        embed.set_footer(text="Nexora Command Audit Feed · Prefix Engine")

        await self._dispatch_log(embed, guild_id=guild.id if guild else None)

    # ── Application / Slash Command Completion Listener ───────────────────────

    @commands.Cog.listener()
    async def on_app_command_completion(
        self,
        interaction: discord.Interaction,
        command: Union[app_commands.Command, app_commands.ContextMenu],
    ):
        cmd_name = command.qualified_name if command else (interaction.command.name if interaction.command else "Unknown")
        user = interaction.user
        guild = interaction.guild
        channel = interaction.channel

        # Format options
        options_list = []
        if interaction.data and "options" in interaction.data:
            def extract_options(opts):
                formatted = []
                for opt in opts:
                    if "value" in opt:
                        val_str = str(opt['value'])
                        if len(val_str) > 80:
                            val_str = val_str[:80] + "..."
                        formatted.append(f"`{opt['name']}`: {val_str}")
                    elif "options" in opt:
                        sub = extract_options(opt["options"])
                        formatted.append(f"`{opt['name']}` -> {', '.join(sub)}")
                return formatted
            options_list = extract_options(interaction.data["options"])

        opts_text = ", ".join(options_list) if options_list else "*No parameters*"
        if len(opts_text) > 900:
            opts_text = opts_text[:900] + "... [truncated]"

        embed = discord.Embed(
            title=f"⚡ Slash Command Executed: `/{cmd_name}`",
            color=CYAN_COLOR,
            timestamp=datetime.now(timezone.utc),
        )

        embed.set_author(name=f"{user} ({user.id})", icon_url=user.display_avatar.url)
        embed.add_field(name="👤 User", value=f"{user.mention} (`{user.id}`)", inline=True)

        if guild:
            ch_mention = channel.mention if channel and hasattr(channel, "mention") else f"#{getattr(channel, 'name', 'unknown')}"
            embed.add_field(name="📍 Location", value=f"**{guild.name}** (`{guild.id}`)\n{ch_mention}", inline=True)
        else:
            embed.add_field(name="📍 Location", value="Direct Messages (DM)", inline=True)

        embed.add_field(name="⚙️ Parameters", value=opts_text, inline=False)
        embed.set_footer(text="Nexora Command Audit Feed · Slash Engine")

        await self._dispatch_log(embed, guild_id=guild.id if guild else None)

    # ── Configuration Commands ────────────────────────────────────────────────

    @commands.hybrid_command(name="set_cmd_log", description="Set or change the channel for bot command audit logs", aliases=["setcmdlog"])
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_cmd_log(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        target = channel or ctx.channel
        perms = target.permissions_for(ctx.guild.me)
        if not perms.send_messages or not perms.embed_links:
            return await ctx.send(f"❌ I lack permission to send embeds in {target.mention}!", ephemeral=True)

        is_owner = False
        if ctx.bot.owner_id:
            is_owner = (ctx.author.id == ctx.bot.owner_id)
        elif hasattr(ctx.bot, "is_owner"):
            is_owner = await ctx.bot.is_owner(ctx.author)

        # If owner runs it, update global channel; otherwise update guild channel
        if is_owner and (ctx.message and "--global" in ctx.message.content.lower() or not ctx.guild):
            self.config["global_channel_id"] = target.id
            scope_str = "Global Master Command Logs"
        else:
            if "guild_channels" not in self.config:
                self.config["guild_channels"] = {}
            self.config["guild_channels"][str(ctx.guild.id)] = target.id
            scope_str = f"Server Command Logs for **{ctx.guild.name}**"

        self.config["enabled"] = True
        self._save_config()

        # Send test audit message
        test_embed = discord.Embed(
            title="✅ Command Logging Channel Configured",
            description=f"This channel has been successfully set as the {scope_str}.\nAll future command executions will be logged here.",
            color=SUCCESS_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        test_embed.set_footer(text="Nexora Command Audit Feed")
        try:
            await target.send(embed=test_embed)
        except Exception:
            pass

        await ctx.send(f"✅ **Command Audit Channel Set**: Configured to {target.mention} ({scope_str}).", ephemeral=True)

    @commands.hybrid_command(name="cmd_log_status", description="Check the status and current channel for command audit logs", aliases=["cmdlogstatus"])
    @commands.has_permissions(administrator=True)
    async def cmd_log_status(self, ctx: commands.Context):
        global_cid = self.get_global_log_channel_id()
        guild_cid = self.get_guild_log_channel_id(ctx.guild.id) if ctx.guild else None
        enabled = self.config.get("enabled", True)

        global_mention = f"<#{global_cid}> (`{global_cid}`)" if global_cid else "*Not set (set via CMD_LOG_CHANNEL_ID in .env or `n!setcmdlog --global`)*"
        guild_mention = f"<#{guild_cid}> (`{guild_cid}`)" if guild_cid else "*Not configured for this server*"

        embed = discord.Embed(
            title="📊 Command Audit Log Status",
            color=CYAN_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Status", value="🟢 **Enabled**" if enabled else "🔴 **Disabled**", inline=True)
        embed.add_field(name="🌐 Global Master Log Channel", value=global_mention, inline=False)
        if ctx.guild:
            embed.add_field(name="🏠 Current Server Log Channel", value=guild_mention, inline=False)
        embed.set_footer(text="Nexora Core System")

        await ctx.send(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(CommandLogger(bot))
    logger.debug("Loaded CommandLogger Cog")

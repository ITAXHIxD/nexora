"""
cogs/moderation/server_logs.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Universal Server Logging & Audit Trail Engine for Nexora
  • Guild log channel configuration (/setlog, n!setlog, /removelog, /logstatus)
  • Intelligent auto-detection of server log channels (mod-logs, audit-logs, etc.)
  • Automatic message delete & message edit tracking
  • Member join & leave audit logs
  • Components V2 + Embed hybrid dispatching
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    NexoraView,
    DismissButton,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)

DATA_DIR = "data"
LOCAL_SETTINGS_FILE = os.path.join(DATA_DIR, "guild_settings.json")

# Standard channel names checked if no explicit channel was configured
AUTO_DETECT_LOG_NAMES = {
    "mod-logs",
    "mod-log",
    "modlog",
    "modlogs",
    "server-logs",
    "server-log",
    "audit-logs",
    "audit-log",
    "bot-logs",
    "bot-log",
    "logs",
}


class ServerLogs(commands.Cog):
    """Universal Server Logging System: tracks events and moderations for any server."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.log_channel_cache: dict[int, Optional[int]] = {}
        self._ensure_local_storage()

    def _ensure_local_storage(self):
        os.makedirs(DATA_DIR, exist_ok=True)
        if not os.path.exists(LOCAL_SETTINGS_FILE):
            try:
                with open(LOCAL_SETTINGS_FILE, "w", encoding="utf-8") as f:
                    json.dump({}, f)
            except Exception as e:
                logger.warning(f"Could not create local guild settings file: {e}")

    # ── Database / Cache Operations ───────────────────────────────────────────

    async def get_configured_channel_id(self, guild_id: int) -> Optional[int]:
        """Fetch configured log channel ID from cache, Mongo, or local JSON."""
        if guild_id in self.log_channel_cache:
            return self.log_channel_cache[guild_id]

        cid: Optional[int] = None
        # Try Mongo first
        if getattr(self.bot, "mongo_db", None) is not None:
            try:
                doc = await self.bot.mongo_db["guild_settings"].find_one({"_id": str(guild_id)})
                if doc and "log_channel_id" in doc:
                    cid = doc["log_channel_id"]
            except Exception as e:
                logger.debug(f"Mongo error fetching log channel for {guild_id}: {e}")

        # Fallback to local JSON
        if cid is None and os.path.exists(LOCAL_SETTINGS_FILE):
            try:
                with open(LOCAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    guild_data = data.get(str(guild_id), {})
                    cid = guild_data.get("log_channel_id")
            except Exception as e:
                logger.debug(f"Local storage read error for guild {guild_id}: {e}")

        self.log_channel_cache[guild_id] = cid
        return cid

    async def set_configured_channel_id(self, guild_id: int, channel_id: Optional[int]):
        """Save configured log channel ID to cache, Mongo, and local JSON."""
        self.log_channel_cache[guild_id] = channel_id

        # Save to Mongo
        if getattr(self.bot, "mongo_db", None) is not None:
            try:
                if channel_id is None:
                    await self.bot.mongo_db["guild_settings"].update_one(
                        {"_id": str(guild_id)},
                        {"$unset": {"log_channel_id": ""}},
                        upsert=True,
                    )
                else:
                    await self.bot.mongo_db["guild_settings"].update_one(
                        {"_id": str(guild_id)},
                        {"$set": {"log_channel_id": channel_id, "updated_at": datetime.now(timezone.utc).isoformat()}},
                        upsert=True,
                    )
            except Exception as e:
                logger.error(f"Mongo error saving log channel for {guild_id}: {e}")

        # Save to local JSON
        try:
            data = {}
            if os.path.exists(LOCAL_SETTINGS_FILE):
                with open(LOCAL_SETTINGS_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            if str(guild_id) not in data:
                data[str(guild_id)] = {}

            if channel_id is None:
                data[str(guild_id)].pop("log_channel_id", None)
            else:
                data[str(guild_id)]["log_channel_id"] = channel_id
                data[str(guild_id)]["updated_at"] = datetime.now(timezone.utc).isoformat()

            with open(LOCAL_SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Local storage save error for guild {guild_id}: {e}")

    # ── Channel Resolver ──────────────────────────────────────────────────────

    async def get_log_channel(self, guild: discord.Guild) -> Optional[discord.TextChannel]:
        """
        Locate the log channel for any server.
        1. Checks explicit server configuration.
        2. If none configured, scans for standard log channel names.
        3. Validates bot permissions (send_messages, embed_links).
        """
        if not guild:
            return None

        # 1. Check explicit setting
        cid = await self.get_configured_channel_id(guild.id)
        if cid:
            ch = guild.get_channel(cid)
            if isinstance(ch, discord.TextChannel):
                perms = ch.permissions_for(guild.me)
                if perms.send_messages and perms.embed_links:
                    return ch

        # 2. Auto-detection fallback
        for ch in guild.text_channels:
            norm_name = ch.name.lower().replace("_", "-").strip()
            if norm_name in AUTO_DETECT_LOG_NAMES:
                perms = ch.permissions_for(guild.me)
                if perms.send_messages and perms.embed_links:
                    return ch

        return None

    # ── Configuration Commands ────────────────────────────────────────────────

    @commands.hybrid_command(
        name="setlog",
        aliases=["setmodlog", "logchannel"],
        description="🛡️ Set the server audit and moderation log channel",
    )
    @app_commands.describe(channel="The text channel where server logs should be sent")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def setlog(self, ctx: commands.Context, channel: discord.TextChannel):
        """Configure the audit log channel for the current server."""
        perms = channel.permissions_for(ctx.guild.me)
        if not perms.send_messages or not perms.embed_links:
            return await ctx.send(
                f"❌ I lack permissions to send messages or embeds in {channel.mention}. "
                f"Please grant `Send Messages` and `Embed Links`.",
                ephemeral=True,
            )

        await self.set_configured_channel_id(ctx.guild.id, channel.id)

        # Send test message into the log channel
        test_embed = discord.Embed(
            title="🛡️ Server Logging Configured",
            description=(
                f"This channel has been successfully designated as the **official server log channel**.\n\n"
                f"• **Configured By:** {ctx.author.mention} (`{ctx.author}`)\n"
                f"• **Timestamp:** <t:{int(datetime.now(timezone.utc).timestamp())}:F>\n\n"
                f"All moderation actions (bans, kicks, mutes, warns, purges) and server events "
                f"(deletions, edits, member departures) will be safely recorded here."
            ),
            color=SUCCESS_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        test_embed.set_footer(text="Nexora Server Audit Engine · Active")
        try:
            await channel.send(embed=test_embed)
        except Exception as e:
            logger.warning(f"Could not dispatch test log to {channel.id}: {e}")

        # Respond to invoker
        view = NexoraView(user_id=ctx.author.id, color=SUCCESS_COLOR)
        view.add_text(
            f"# ✅ Log Channel Established\n"
            f"> Server logs will now be broadcast to {channel.mention}.\n\n"
            f"A verification ping was dispatched to ensure operational readiness."
        )
        view.add_footer("Nexora Server Logs · Configured")
        view.add_row(DismissButton(user_id=ctx.author.id))
        await send_view(ctx, view)

    @commands.command(
        name="removelog",
        aliases=["disablelog", "unsetlog"],
    )
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def removelog(self, ctx: commands.Context):
        """Disable explicit server logging channel."""
        await self.set_configured_channel_id(ctx.guild.id, None)

        view = NexoraView(user_id=ctx.author.id, color=WARNING_COLOR)
        view.add_text(
            "# 🛑 Server Log Channel Removed\n"
            "> Explicit server logging channel has been disabled for this server.\n"
            "-# Note: If a standard channel named `#mod-logs` or `#server-logs` exists, auto-detection may still route events there."
        )
        view.add_footer("Nexora Server Logs · Disabled")
        view.add_row(DismissButton(user_id=ctx.author.id))
        await send_view(ctx, view)

    @commands.command(
        name="logstatus",
    )
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def logstatus(self, ctx: commands.Context):
        """Display current server log channel status."""
        configured_id = await self.get_configured_channel_id(ctx.guild.id)
        resolved_channel = await self.get_log_channel(ctx.guild)

        status_lines = []
        if configured_id:
            cfg_ch = ctx.guild.get_channel(configured_id)
            if cfg_ch:
                status_lines.append(f"• **Configured Channel:** {cfg_ch.mention} (`#{cfg_ch.name}`)")
            else:
                status_lines.append(f"• **Configured Channel:** `ID {configured_id}` (Channel Deleted ❌)")
        else:
            status_lines.append("• **Configured Channel:** *None explicitly configured*")

        if resolved_channel:
            is_auto = (configured_id != resolved_channel.id)
            source = "Auto-detected by channel name" if is_auto else "Explicit configuration"
            status_lines.append(f"• **Active Destination:** {resolved_channel.mention} ({source})")
            status_lines.append("• **Bot Status:** Ready & Writable ✅")
        else:
            status_lines.append("• **Active Destination:** ❌ No valid log channel found")
            status_lines.append("-# Use `/setlog #channel` to designate an audit log channel.")

        view = NexoraView(user_id=ctx.author.id, color=BRAND_COLOR)
        view.add_text(
            f"# 📊 Server Log Status · {ctx.guild.name}\n"
            + "\n".join(status_lines)
        )
        view.add_footer("Nexora Server Audit Engine")
        view.add_row(DismissButton(user_id=ctx.author.id))
        await send_view(ctx, view)

    # ── Automatic Event Listeners ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message):
        """Audit deleted messages across servers."""
        if not message.guild or message.author.bot:
            return

        log_channel = await self.get_log_channel(message.guild)
        if not log_channel or message.channel.id == log_channel.id:
            return

        embed = discord.Embed(
            title="🗑️ Message Deleted",
            description=(
                f"**Author:** {message.author.mention} (`{message.author}` | `{message.author.id}`)\n"
                f"**Channel:** {message.channel.mention} (`#{message.channel.name}`)\n"
                f"**Message Content:**\n"
                f"> {message.content[:1500] if message.content else '*No text content (attachments/embed only)*'}"
            ),
            color=ERROR_COLOR,
            timestamp=datetime.now(timezone.utc),
        )

        if message.attachments:
            att_list = [f"[{att.filename}]({att.url})" for att in message.attachments[:5]]
            embed.add_field(name="📎 Attachments", value="\n".join(att_list), inline=False)

        embed.set_thumbnail(url=message.author.display_avatar.url)
        embed.set_footer(text=f"Message ID: {message.id}")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            logger.debug(f"Failed to post delete log in {message.guild.id}: {e}")

    @commands.Cog.listener()
    async def on_message_edit(self, before: discord.Message, after: discord.Message):
        """Audit edited messages across servers."""
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return

        log_channel = await self.get_log_channel(before.guild)
        if not log_channel or before.channel.id == log_channel.id:
            return

        embed = discord.Embed(
            title="✏️ Message Edited",
            description=(
                f"**Author:** {before.author.mention} (`{before.author}` | `{before.author.id}`)\n"
                f"**Channel:** {before.channel.mention} (`#{before.channel.name}`)\n"
                f"**Jump:** [Go to message]({after.jump_url})"
            ),
            color=0x5865F2,
            timestamp=datetime.now(timezone.utc),
        )

        b_content = before.content[:1000] if before.content else "*Empty*"
        a_content = after.content[:1000] if after.content else "*Empty*"

        embed.add_field(name="Before", value=f"> {b_content}", inline=False)
        embed.add_field(name="After", value=f"> {a_content}", inline=False)
        embed.set_thumbnail(url=before.author.display_avatar.url)
        embed.set_footer(text=f"Message ID: {after.id}")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            logger.debug(f"Failed to post edit log in {before.guild.id}: {e}")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        """Audit new member joins."""
        if not member.guild:
            return

        log_channel = await self.get_log_channel(member.guild)
        if not log_channel:
            return

        created_ts = int(member.created_at.timestamp())
        embed = discord.Embed(
            title="📥 Member Joined",
            description=(
                f"**User:** {member.mention} (`{member}` | `{member.id}`)\n"
                f"**Account Created:** <t:{created_ts}:R> (<t:{created_ts}:f>)\n"
                f"**Total Members:** `{member.guild.member_count:,}`"
            ),
            color=SUCCESS_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"User ID: {member.id}")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            logger.debug(f"Failed to post join log in {member.guild.id}: {e}")

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        """Audit member departures and kicks."""
        if not member.guild:
            return

        log_channel = await self.get_log_channel(member.guild)
        if not log_channel:
            return

        joined_str = ""
        if member.joined_at:
            jts = int(member.joined_at.timestamp())
            joined_str = f"\n**Joined Server:** <t:{jts}:R> (<t:{jts}:f>)"

        roles = [r.mention for r in member.roles if not r.is_default()][:10]
        roles_str = " ".join(roles) if roles else "*None*"

        embed = discord.Embed(
            title="📤 Member Left",
            description=(
                f"**User:** {member.mention} (`{member}` | `{member.id}`)"
                f"{joined_str}\n"
                f"**Roles:** {roles_str}\n"
                f"**Total Members:** `{member.guild.member_count:,}`"
            ),
            color=0xFF9F1C,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"User ID: {member.id}")

        try:
            await log_channel.send(embed=embed)
        except Exception as e:
            logger.debug(f"Failed to post remove log in {member.guild.id}: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerLogs(bot))

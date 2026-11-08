"""
cogs/utility/afk.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 AFK Management System
High-performance in-memory caching with MongoDB backing and local fallback.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import datetime
import json
import logging
import os
import re
import time
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    ERROR_COLOR,
    NexoraView,
    DismissButton,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)

AFK_DATA_FILE = "data/afk_data.json"


def _load_afk_local() -> dict:
    try:
        if os.path.exists(AFK_DATA_FILE):
            with open(AFK_DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
                return {int(k): v for k, v in raw.items() if str(k).isdigit()}
    except Exception as e:
        logger.warning("AFK: Failed to load local AFK file: %s", e)
    return {}


def _save_afk_local(data: dict):
    try:
        os.makedirs("data", exist_ok=True)
        with open(AFK_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump({str(k): v for k, v in data.items()}, f, indent=4)
    except Exception as e:
        logger.warning("AFK: Failed to save local AFK file: %s", e)


class AFKStatusSetView(NexoraView):
    """Components V2 card shown when a user goes AFK."""

    def __init__(self, user: discord.Member, reason: str, scope_str: str, timeout: float = 300):
        super().__init__(user_id=user.id, color=BRAND_COLOR, timeout=timeout)
        self.user = user
        self.reason = reason
        self.scope_str = scope_str
        self._build()

    def _build(self):
        self.clear_container()
        header = (
            f"# 💤 AFK Status Active\n"
            f"> **User:** {self.user.mention} (`@{self.user.name}`)\n"
            f"> **Scope:** {self.scope_str}"
        )
        self.add_section(header, thumbnail_url=str(self.user.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        body = (
            f"• **Reason:**\n  > {self.reason}\n\n"
            f"💡 *Send any message in chat or click the button below to return.*"
        )
        self.add_text(body)
        self.add_footer("Nexora AFK Network · Notifications active")

        btn_remove = discord.ui.Button(
            label="Remove AFK",
            emoji="👋",
            style=discord.ButtonStyle.success,
            custom_id="afk-quick-remove",
        )
        btn_remove.callback = self._on_remove

        dismiss = DismissButton(user_id=self.user.id)
        self.add_row(btn_remove, dismiss)

    async def _on_remove(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the AFK member can remove this status.", ephemeral=True)
            return

        cog = interaction.client.get_cog("AFK")
        if cog:
            data = await cog.get_afk(interaction.user.id)
            if data:
                await cog.remove_afk_status(interaction.user, interaction.guild, silent=True)
                self.clear_container()
                self.add_text(
                    f"# 👋 Welcome Back!\n"
                    f"> {interaction.user.mention}'s AFK status has been removed."
                )
                self.add_footer("Nexora AFK Network")
                await interaction.response.edit_message(view=self)
                return

        await interaction.response.send_message("❌ You are not currently AFK.", ephemeral=True)


class AFKInspectorView(NexoraView):
    """Components V2 view inspecting someone's AFK status."""

    def __init__(
        self,
        target: discord.Member,
        afk_data: dict,
        requester: discord.abc.User,
        timeout: float = 180,
    ):
        super().__init__(user_id=requester.id, color=BRAND_COLOR, timeout=timeout)
        self.target = target
        self.afk_data = afk_data
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()
        since_dt = datetime.datetime.fromisoformat(self.afk_data["time"])
        since_str = f"{ts_format(since_dt, 'R')} ({ts_format(since_dt, 't')})"

        header = (
            f"# 💤 {self.target.display_name} is AFK\n"
            f"> `@{self.target.name}` · Scope: **{'Global' if self.afk_data.get('global') else 'Server-Only'}**"
        )
        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        mentions_count = len(self.afk_data.get("mentions", []))
        body = (
            f"• **Reason:**\n  > {self.afk_data['reason']}\n"
            f"• **Away Since:** {since_str}\n"
            f"• **Mentions Recorded:** `{mentions_count}` times"
        )
        self.add_text(body)
        self.add_footer(f"Requested by {self.requester.display_name}")

        dismiss = DismissButton(user_id=self.requester.id)
        self.add_row(dismiss)


class AFKListView(NexoraView):
    """Components V2 card listing active AFK members."""

    def __init__(self, guild: discord.Guild, rows: list[str], requester: discord.abc.User):
        super().__init__(user_id=requester.id, color=BRAND_COLOR, timeout=180)
        self.clear_container()
        header = (
            f"# 💤 AFK Members · {guild.name}\n"
            f"> Total Active AFK: **{len(rows)}**"
        )
        self.add_section(header, thumbnail_url=str(guild.icon.url) if guild.icon else None)
        self.add_separator(discord.SeparatorSpacing.small)

        content = "\n".join(rows[:15])
        if len(rows) > 15:
            content += f"\n\n*(+{len(rows) - 15} more members)*"
        self.add_text(content)
        self.add_footer(f"Requested by {requester.display_name}")

        self.add_row(DismissButton(user_id=requester.id))


class AFK(commands.Cog):
    """AFK system — High-Performance In-Memory Cache backed by MongoDB"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.col = None
        self.active_afk_cache: set[int] = set()
        self.local_cache: dict[int, dict] = {}
        self.processing_removal: set[int] = set()
        self._mention_cooldowns: dict[tuple[int, int], float] = {}  # (user_id, channel_id) -> timestamp
        self._set_timestamps: dict[int, float] = {}  # user_id -> timestamp when AFK was set (grace period)

    async def cog_load(self):
        # 1. Pre-seed from local storage
        self.local_cache = _load_afk_local()
        for uid in self.local_cache:
            self.active_afk_cache.add(uid)

        # 2. Sync from MongoDB if connected
        mongo = getattr(self.bot, "mongo_db", None)
        if mongo is not None:
            self.col = mongo["afk"]
            try:
                cursor = self.col.find({})
                async for doc in cursor:
                    try:
                        uid = int(doc["_id"])
                        self.active_afk_cache.add(uid)
                        self.local_cache[uid] = doc
                    except Exception:
                        pass
                logger.info("AFK: Cached %d active AFK users into memory (Mongo + Local)", len(self.active_afk_cache))
            except Exception as e:
                logger.warning("AFK: Failed to pre-seed AFK cache from mongo: %s", e)
        else:
            logger.info("AFK: Cached %d active AFK users from local storage", len(self.active_afk_cache))
        logger.debug("Loaded AFK")

    # ── Database & Cache Helpers ───────────────────────────────────────────────

    async def get_afk(self, user_id: int) -> Optional[dict]:
        uid = int(user_id)
        # Fast hit: local cache
        if uid in self.local_cache:
            self.active_afk_cache.add(uid)
            return self.local_cache[uid]

        # Sync from MongoDB if connected
        if self.col is not None:
            try:
                doc = await self.col.find_one({"_id": uid})
                if not doc:
                    doc = await self.col.find_one({"_id": str(uid)})
                if doc:
                    self.active_afk_cache.add(uid)
                    self.local_cache[uid] = doc
                    return doc
            except Exception as e:
                logger.warning("AFK: MongoDB find error, falling back to local: %s", e)

        data = self.local_cache.get(uid)
        if data:
            self.active_afk_cache.add(uid)
            return data

        self.active_afk_cache.discard(uid)
        return None

    async def set_afk(self, user_id: int, data: dict):
        uid = int(user_id)
        self.active_afk_cache.add(uid)
        self.local_cache[uid] = data
        self._set_timestamps[uid] = time.time()
        _save_afk_local(self.local_cache)

        if self.col is not None:
            try:
                await self.col.update_one({"_id": uid}, {"$set": data}, upsert=True)
            except Exception as e:
                logger.warning("AFK: MongoDB save error: %s", e)

    async def delete_afk(self, user_id: int):
        uid = int(user_id)
        self.active_afk_cache.discard(uid)
        self.local_cache.pop(uid, None)
        self._set_timestamps.pop(uid, None)
        _save_afk_local(self.local_cache)

        if self.col is not None:
            try:
                await self.col.delete_one({"_id": uid})
                await self.col.delete_one({"_id": str(uid)})
            except Exception as e:
                logger.warning("AFK: MongoDB delete error: %s", e)

    def format_duration(self, delta: datetime.timedelta) -> str:
        seconds = int(delta.total_seconds())
        if seconds < 60:
            return f"{seconds}s"
        minutes, _ = divmod(seconds, 60)
        if minutes < 60:
            return f"{minutes}m"
        hours, minutes = divmod(minutes, 60)
        if hours < 24:
            return f"{hours}h {minutes}m"
        days, hours = divmod(hours, 24)
        return f"{days}d {hours}h"

    async def remove_afk_status(self, member: discord.Member, guild: discord.Guild, silent: bool = False):
        if member.id in self.processing_removal:
            return None
        afk_data = await self.get_afk(member.id)
        if not afk_data:
            return None
        try:
            self.processing_removal.add(member.id)
            await self.delete_afk(member.id)
            try:
                if member.display_name.startswith("[AFK] "):
                    old_nick = afk_data.get("old_nick")
                    await member.edit(nick=old_nick)
            except (discord.Forbidden, discord.HTTPException):
                pass

            if not silent and afk_data.get("dm_notifications", True) and afk_data.get("mentions"):
                try:
                    mentions = afk_data["mentions"]
                    mention_list = "\n".join(f"• {m}" for m in mentions[-10:])
                    view = NexoraView(color=BRAND_COLOR, timeout=120)
                    view.add_text(
                        f"# 📬 AFK Mention Summary\n"
                        f"> While away in **{guild.name}**, you were mentioned **{len(mentions)}** time(s):\n\n"
                        f"{mention_list}"
                    )
                    view.add_footer(f"Nexora AFK · {guild.name}")
                    await member.send(view=view)
                except discord.Forbidden:
                    pass
            return afk_data
        finally:
            self.processing_removal.discard(member.id)

    # ── Shared AFK Setup Logic ────────────────────────────────────────────────

    async def _set_afk_internal(
        self,
        member: discord.Member,
        guild: discord.Guild,
        reason: str,
        global_afk: bool,
        send_coro,
    ):
        if await self.get_afk(member.id):
            await send_coro("❌ You are already AFK! Send a message or use `/unafk` to return.", ephemeral=True)
            return

        reason = (reason or "AFK").strip()
        if len(reason) > 300:
            await send_coro("❌ Keep your AFK reason to **300 characters or fewer**.", ephemeral=True)
            return

        old_nick = member.nick
        original_name = member.display_name.replace("[AFK] ", "").strip()
        now = datetime.datetime.now(datetime.timezone.utc)
        await self.set_afk(member.id, {
            "reason": reason,
            "time": now.isoformat(),
            "name": original_name,
            "old_nick": old_nick,
            "guild_id": guild.id if not global_afk else None,
            "mentions": [],
            "global": global_afk,
            "dm_notifications": True,
        })
        try:
            await member.edit(nick=f"[AFK] {original_name}"[:32])
        except (discord.Forbidden, discord.HTTPException):
            pass

        scope = "🌐 Globally across all servers" if global_afk else f"🏰 In {guild.name}"
        view = AFKStatusSetView(member, reason, scope)
        await send_coro(view=view)

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.command(name="afk", description="💤 Set your AFK status")
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def afk_prefix(self, ctx: commands.Context, *, reason: Optional[str] = "AFK"):
        """Prefix command for setting AFK. Global by default; supports '-s' or '--server' flag for server-only."""
        raw = (reason or "AFK").strip()
        global_afk = True

        if raw.startswith(("-s ", "--server ")):
            global_afk = False
            raw = raw.split(" ", 1)[1].strip()
        elif raw in ("-s", "--server"):
            global_afk = False
            raw = "AFK"
        elif " -s" in raw or " --server" in raw:
            global_afk = False
            raw = raw.replace(" -s", "").replace(" --server", "").strip() or "AFK"
        elif raw.startswith(("-g ", "--global ")):
            global_afk = True
            raw = raw.split(" ", 1)[1].strip()
        elif raw in ("-g", "--global"):
            global_afk = True
            raw = "AFK"
        elif " -g" in raw or " --global" in raw:
            global_afk = True
            raw = raw.replace(" -g", "").replace(" --global", "").strip() or "AFK"

        async def send_fn(*args, **kwargs):
            kwargs.pop("ephemeral", None)
            if "view" in kwargs:
                await send_view(ctx, kwargs["view"])
            else:
                await ctx.send(*args, **kwargs)

        await self._set_afk_internal(ctx.author, ctx.guild, raw, global_afk, send_fn)

    @commands.command(name="gafk", description="🌐 Set your Global AFK status across all servers")
    @commands.guild_only()
    @commands.cooldown(1, 3, commands.BucketType.user)
    async def gafk_prefix(self, ctx: commands.Context, *, reason: Optional[str] = "AFK"):
        """Prefix shortcut command for setting global AFK."""
        async def send_fn(*args, **kwargs):
            kwargs.pop("ephemeral", None)
            if "view" in kwargs:
                await send_view(ctx, kwargs["view"])
            else:
                await ctx.send(*args, **kwargs)

        await self._set_afk_internal(ctx.author, ctx.guild, reason or "AFK", True, send_fn)

    @app_commands.command(name="afk", description="💤 Set your AFK status")
    @app_commands.describe(
        reason="Reason for going AFK",
        global_afk="Apply across all servers (default: true)"
    )
    @app_commands.guild_only()
    async def afk_slash(
        self,
        interaction: discord.Interaction,
        reason: Optional[str] = "AFK",
        global_afk: Optional[bool] = True,
    ):
        """Slash command for setting AFK with primary reason option."""
        async def send_fn(*args, **kwargs):
            if "view" in kwargs:
                await interaction.response.send_message(view=kwargs["view"], ephemeral=kwargs.get("ephemeral", False))
            else:
                await interaction.response.send_message(*args, **kwargs)

        await self._set_afk_internal(
            interaction.user,
            interaction.guild,
            reason or "AFK",
            bool(global_afk if global_afk is not None else True),
            send_fn,
        )

    @app_commands.command(name="unafk", description="👋 Manually remove your AFK status")
    @app_commands.guild_only()
    async def unafk_slash(self, interaction: discord.Interaction):
        """Slash command to manually return from AFK."""
        afk_data = await self.get_afk(interaction.user.id)
        if not afk_data:
            return await interaction.response.send_message("❌ You are not currently AFK!", ephemeral=True)

        try:
            delta = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(afk_data["time"])
            duration = self.format_duration(delta)
        except Exception:
            duration = "some time"

        await self.remove_afk_status(interaction.user, interaction.guild)

        view = NexoraView(color=SUCCESS_COLOR, timeout=60)
        view.add_text(
            f"# 👋 Welcome Back, {interaction.user.display_name}!\n"
            f"> Your AFK status was removed. You were away for **{duration}**."
        )
        view.add_footer("Nexora AFK Network")
        await interaction.response.send_message(view=view)

    @commands.command(name="unafk", description="👋 Manually remove your AFK status")
    @commands.guild_only()
    async def unafk(self, ctx: commands.Context):
        afk_data = await self.get_afk(ctx.author.id)
        if not afk_data:
            return await ctx.send("❌ You are not currently AFK!", ephemeral=True)

        delta = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(afk_data["time"])
        duration = self.format_duration(delta)
        await self.remove_afk_status(ctx.author, ctx.guild)

        view = NexoraView(color=SUCCESS_COLOR, timeout=60)
        view.add_text(
            f"# 👋 Welcome Back, {ctx.author.display_name}!\n"
            f"> Your AFK status was removed. You were away for **{duration}**."
        )
        view.add_footer("Nexora AFK Network")
        await send_view(ctx, view)

    @commands.command(name="afkstatus", description="🔍 Check AFK status of a user")
    @commands.guild_only()
    async def afkstatus(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        target = user or ctx.author
        afk_data = await self.get_afk(target.id)
        if not afk_data:
            return await ctx.send(f"{'You are' if target == ctx.author else f'{target.mention} is'} not currently AFK.", ephemeral=True)

        if not afk_data.get("global") and afk_data.get("guild_id") != ctx.guild.id:
            return await ctx.send(f"{'You are' if target == ctx.author else f'{target.mention} is'} not currently AFK in this server.", ephemeral=True)

        view = AFKInspectorView(target, afk_data, ctx.author)
        await send_view(ctx, view)

    @commands.command(name="afkclear", description="🛡️ Reset someone's AFK status (Moderator)")
    @commands.has_permissions(manage_nicknames=True)
    @commands.guild_only()
    async def afkclear(self, ctx: commands.Context, member: discord.Member):
        """Forcefully clears a member's AFK status."""
        afk_data = await self.get_afk(member.id)
        if not afk_data:
            return await ctx.send(f"❌ {member.mention} is not currently AFK.", ephemeral=True)

        await self.remove_afk_status(member, ctx.guild, silent=True)
        view = NexoraView(color=SUCCESS_COLOR, timeout=60)
        view.add_text(
            f"# 🛡️ AFK Status Cleared\n"
            f"> Moderator {ctx.author.mention} reset the AFK status of {member.mention}."
        )
        view.add_footer("Nexora Moderation Engine")
        await send_view(ctx, view)

    @commands.command(name="afklist", description="📋 List all AFK users in this server")
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def afklist(self, ctx: commands.Context):
        docs = []
        if self.col is not None:
            try:
                cursor = self.col.find({"$or": [{"global": True}, {"guild_id": ctx.guild.id}]})
                docs = [doc async for doc in cursor]
            except Exception as e:
                logger.warning("AFK: Failed to query mongo for afklist: %s", e)

        if not docs and self.local_cache:
            docs = [d for d in self.local_cache.values() if d.get("global") or d.get("guild_id") == ctx.guild.id]

        rows = []
        now = datetime.datetime.now(datetime.timezone.utc)
        for doc in docs:
            user_id = doc.get("_id") or doc.get("user_id")
            member = ctx.guild.get_member(user_id)
            if member:
                delta = now - datetime.datetime.fromisoformat(doc["time"])
                duration = self.format_duration(delta)
                rows.append(f"• **{member.display_name}** — {doc['reason']} *({duration})*")

        if not rows:
            return await ctx.send("📭 No members are currently AFK in this server.", ephemeral=True)

        view = AFKListView(ctx.guild, rows, ctx.author)
        await send_view(ctx, view)

    @commands.command(name="afksettings", description="⚙️ Toggle DM notifications for AFK mentions")
    @commands.guild_only()
    async def afksettings(self, ctx: commands.Context, dm_notifications: bool):
        if not await self.get_afk(ctx.author.id):
            return await ctx.send("❌ You must be AFK to adjust this setting!", ephemeral=True)
        if self.col:
            await self.col.update_one({"_id": ctx.author.id}, {"$set": {"dm_notifications": dm_notifications}})
        if ctx.author.id in self.local_cache:
            self.local_cache[ctx.author.id]["dm_notifications"] = dm_notifications
        status = "enabled" if dm_notifications else "disabled"
        await ctx.send(f"✅ DM mention notifications are now **{status}**.", ephemeral=True)

    # ── High Performance Listeners ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # O(1) fast-path exit: if no users are AFK anywhere, skip all parsing & lookups
        if not self.active_afk_cache and not self.local_cache:
            return

        now_ts = time.time()
        now_dt = datetime.datetime.now(datetime.timezone.utc)

        # 1. Clear the author's AFK status on their first normal message,
        # but respect a 10-second grace period so typing "bye", "brb", or
        # an immediate test message right after setting AFK doesn't instantly clear it.
        if message.author.id in self.active_afk_cache or message.author.id in self.local_cache:
            set_ts = self._set_timestamps.get(message.author.id, 0)
            if now_ts - set_ts >= 10.0:
                content_lower = message.content.strip().lower()
                is_afk_command = False
                for pfx in ("n!", "/", "!", "?", "."):
                    if content_lower.startswith(tuple(f"{pfx}{c}" for c in ("afk", "unafk", "gafk", "afkstatus", "afkclear", "afklist", "afksettings"))):
                        is_afk_command = True
                        break
                if self.bot.user and (
                    f"<@{self.bot.user.id}>" in content_lower
                    or f"<@!{self.bot.user.id}>" in content_lower
                ):
                    if any(f" {c}" in content_lower for c in ("afk", "unafk", "gafk", "afkstatus", "afkclear", "afklist", "afksettings")):
                        is_afk_command = True

                if not is_afk_command:
                    afk_data = await self.get_afk(message.author.id)
                    if afk_data:
                        target_guild = int(afk_data.get("guild_id") or 0)
                        if afk_data.get("global") or not target_guild or target_guild == message.guild.id:
                            delta = now_dt - datetime.datetime.fromisoformat(afk_data["time"])
                            duration = self.format_duration(delta)
                            removed = await self.remove_afk_status(message.author, message.guild)
                            if removed:
                                view = NexoraView(color=SUCCESS_COLOR, timeout=60)
                                mention_info = ""
                                if removed.get("mentions"):
                                    mention_info = f"\n• 📬 You were mentioned **{len(removed['mentions'])}** time(s) while away."
                                view.add_text(
                                    f"# 👋 Welcome back, {message.author.display_name}!\n"
                                    f"> Your AFK status has been removed (Away for **{duration}**).{mention_info}"
                                )
                                view.add_footer("Nexora AFK Network")
                                try:
                                    await message.channel.send(view=view)
                                except Exception as e:
                                    logger.warning("Failed to send AFK return notification: %s", e)

        # 2. Check if any mentioned users or reply reference target is AFK
        targets_to_check: list[discord.Member | discord.User] = []
        checked_ids: set[int] = set()

        # A) Explicit Discord mentions
        if message.mentions:
            for m in message.mentions:
                if not m.bot and m.id != message.author.id and m.id not in checked_ids:
                    targets_to_check.append(m)
                    checked_ids.add(m.id)

        # B) Raw regex mentions (<@id> and <@!id>) to catch members if uncached
        for raw_id_str in re.findall(r"<@!?(\d+)>", message.content):
            try:
                raw_id = int(raw_id_str)
                if raw_id != message.author.id and raw_id not in checked_ids:
                    member = message.guild.get_member(raw_id) or self.bot.get_user(raw_id)
                    if member and not getattr(member, "bot", False):
                        targets_to_check.append(member)
                        checked_ids.add(raw_id)
            except Exception:
                pass

        # C) Check if message is a reply to an AFK member
        if message.reference:
            ref = getattr(message.reference, "resolved", None)
            if not isinstance(ref, discord.Message):
                ref = getattr(message.reference, "cached_message", None)
            if not isinstance(ref, discord.Message) and getattr(message.reference, "message_id", None):
                try:
                    ref = await message.channel.fetch_message(message.reference.message_id)
                except Exception:
                    ref = None
            if isinstance(ref, discord.Message) and ref.author and not ref.author.bot and ref.author.id != message.author.id:
                if ref.author.id not in checked_ids:
                    member = message.guild.get_member(ref.author.id) or ref.author
                    targets_to_check.append(member)
                    checked_ids.add(ref.author.id)

        if not targets_to_check:
            return

        # Filter against O(1) active AFK memory cache (no per-message MongoDB round-trips)
        afk_mentioned_users: list[discord.Member | discord.User] = []
        for m in targets_to_check:
            uid = int(m.id)
            if uid in self.active_afk_cache or uid in self.local_cache:
                afk_mentioned_users.append(m)

        if not afk_mentioned_users:
            return

        alert_lines = []
        for mentioned in afk_mentioned_users:
            cooldown_key = (message.author.id, mentioned.id)
            last_alert = self._mention_cooldowns.get(cooldown_key, 0)
            if now_ts - last_alert < 4.0:
                continue

            afk_data = await self.get_afk(mentioned.id)
            if not afk_data:
                continue

            target_guild = int(afk_data.get("guild_id") or 0)
            if not afk_data.get("global") and target_guild and target_guild != message.guild.id:
                continue

            self._mention_cooldowns[cooldown_key] = now_ts
            time_str = afk_data.get("time")
            try:
                dt = datetime.datetime.fromisoformat(time_str)
                ts = int(dt.timestamp())
                time_badge = f"<t:{ts}:R>"
            except Exception:
                time_badge = "recently"

            reason_text = afk_data.get("reason", "AFK")
            alert_lines.append(
                f"💤 **{mentioned.display_name}** is AFK: {reason_text} — {time_badge}"
            )

            # Record mention safely
            try:
                mention_str = f"[{message.author.name} in #{message.channel.name}]({message.jump_url})"
                if self.col:
                    try:
                        await self.col.update_one({"_id": mentioned.id}, {"$push": {"mentions": mention_str}})
                    except Exception:
                        pass
                if mentioned.id in self.local_cache:
                    self.local_cache[mentioned.id].setdefault("mentions", []).append(mention_str)
                    _save_afk_local(self.local_cache)
            except Exception as rec_err:
                logger.debug("AFK mention recording failed: %s", rec_err)

            # Send optional DM notification
            if afk_data.get("dm_notifications", True):
                try:
                    view = NexoraView(color=BRAND_COLOR, timeout=180)
                    view.add_text(
                        f"# 📬 New Mention While AFK\n"
                        f"> In **{message.guild.name}** #{message.channel.name}\n\n"
                        f"• **Author:** {message.author.mention}\n"
                        f"• **Message:** {message.content[:200] or '*No text*'}\n"
                        f"• **Jump:** [View Message]({message.jump_url})"
                    )
                    view.add_footer("Nexora AFK Alerts")
                    await mentioned.send(view=view)
                except Exception as dm_err:
                    logger.debug("AFK DM notification skipped/failed: %s", dm_err)

        if alert_lines:
            if len(alert_lines) == 1:
                reply_text = alert_lines[0]
            else:
                formatted_items = [
                    f"• {line[2:].strip()}" if line.startswith("💤") else f"• {line}"
                    for line in alert_lines
                ]
                reply_text = "💤 **AFK Notice:**\n" + "\n".join(formatted_items)

            try:
                await message.reply(
                    reply_text,
                    mention_author=False,
                    allowed_mentions=discord.AllowedMentions.none(),
                    fail_if_not_exists=False,
                )
            except (discord.Forbidden, discord.HTTPException):
                try:
                    await message.channel.send(
                        reply_text,
                        allowed_mentions=discord.AllowedMentions.none(),
                    )
                except Exception as e:
                    logger.warning("AFK message send failed: %s", e)

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if after.bot or before.id not in self.active_afk_cache:
            return
        afk_data = await self.get_afk(before.id)
        if afk_data:
            try:
                if before.display_name.startswith("[AFK] ") and not after.display_name.startswith("[AFK] "):
                    await after.edit(nick=f"[AFK] {afk_data.get('name', '')}"[:32])
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(AFK(bot))
    logger.debug("Loaded AFK")

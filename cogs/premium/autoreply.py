"""
cogs/premium/autoreply.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Production-Grade Autoresponder System for Nexora.

Comparable in capability and polish to Carl-bot and Mimu:
  • Match Modes: exact, contains, startswith, endswith, whole_word, regex
  • Multi-trigger support & case sensitivity toggle
  • Safe ReDoS-protected regex engine
  • Variable placeholders ({user}, {server}, {channel}, {members}, etc.)
  • Rich Embed Builder & Multi-embed support
  • Reaction responses, response variations, and delays
  • Channel and Role restrictions & exclusions
  • Per-user, per-channel, and per-server cooldowns
  • Deterministic priority resolution & conflict modes
  • Full management: add, edit, remove, list, show, enable, disable,
    test, duplicate, import, export, settings, stats, help
  • Fast in-memory hot-path caching (zero DB queries on ordinary messages)
  • MongoDB persistence with local JSON fallback & legacy migration
  • Tier quotas and premium perks integrated with CharacterBot
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import io
import json
import logging
import random
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from utils.autoresponder_engine import (
    AutoResponderEngine,
    AutoResponderItem,
    GuildAutoResponderSettings,
    VALID_CONFLICT_MODES,
    VALID_MATCH_MODES,
    sanitize_regex,
)
from utils.autoresponder_storage import AutoResponderStorage
from utils.ui import (
    BRAND_COLOR,
    PREMIUM_COLOR,
    SUCCESS_COLOR,
    ERROR_COLOR,
    CYAN_COLOR,
    ts_format,
)

logger = logging.getLogger(__name__)


class AutoresponderCreateModal(discord.ui.Modal, title="Create Autoresponder"):
    """Interactive Discord modal for creating an autoresponder."""

    def __init__(self, cog: "AutoResponder", guild: discord.Guild, author_id: int):
        super().__init__(timeout=300)
        self.cog = cog
        self.guild = guild
        self.author_id = author_id

    trigger_input = discord.ui.TextInput(
        label="Trigger Keyword(s)",
        placeholder="e.g. hello, hey (comma-separated)",
        max_length=200,
        required=True,
    )
    reply_input = discord.ui.TextInput(
        label="Response Text",
        style=discord.TextStyle.paragraph,
        placeholder="Response text (supports {user}, {server}, {channel}, etc.)",
        max_length=2000,
        required=True,
    )
    match_mode_input = discord.ui.TextInput(
        label="Match Mode",
        placeholder="contains, exact, startswith, endswith, whole_word, regex",
        default="contains",
        max_length=20,
        required=False,
    )
    ping_input = discord.ui.TextInput(
        label="Ping Triggering User (ON / OFF)",
        placeholder="ON or OFF (default: OFF)",
        default="OFF",
        max_length=10,
        required=False,
    )
    reaction_input = discord.ui.TextInput(
        label="Trigger Reaction (Emoji or None)",
        placeholder="e.g. 👋, ⭐, or none",
        default="none",
        max_length=50,
        required=False,
    )

    async def on_submit(self, interaction: discord.Interaction):
        if not await self.cog._is_premium(self.guild.id):
            return await interaction.response.send_message(
                "❌ **Premium Required**: Server subscription needed. Upgrade with `/premium_price`!",
                ephemeral=True,
            )

        limit = await self.cog._get_tier_limit(self.guild.id)
        settings, items = await self.cog._get_guild_cached(self.guild.id)
        if limit != -1 and len(items) >= limit:
            return await interaction.response.send_message(
                f"❌ **Slot Limit Reached**: Your tier allows up to `{limit}` autoresponders.",
                ephemeral=True,
            )

        mode_val = self.match_mode_input.value.strip().lower()
        if mode_val not in VALID_MATCH_MODES:
            mode_val = "contains"

        tier = (
            await self.cog.bot.get_premium_tier(self.guild.id)
            if hasattr(self.cog.bot, "get_premium_tier")
            else "BASIC"
        )
        if mode_val == "regex" and str(tier).upper() in ("FREE", "BASIC"):
            return await interaction.response.send_message(
                "❌ **Pro Perk**: Regular expression triggers require a **PRO** tier subscription.",
                ephemeral=True,
            )

        raw_triggers = [t.strip() for t in self.trigger_input.value.split(",") if t.strip()]
        if not raw_triggers:
            return await interaction.response.send_message("❌ Trigger cannot be empty.", ephemeral=True)

        for t in raw_triggers:
            if len(t) > 100:
                return await interaction.response.send_message(
                    f"❌ Trigger `{t[:20]}…` exceeds 100 characters.", ephemeral=True
                )
            if mode_val == "regex":
                is_valid, err = sanitize_regex(t)
                if not is_valid:
                    return await interaction.response.send_message(
                        f"❌ Invalid regular expression: {err}", ephemeral=True
                    )

        clean_reply = self.reply_input.value.strip()
        if not clean_reply or len(clean_reply) > 2000:
            return await interaction.response.send_message(
                "❌ Reply must contain between 1 and 2,000 characters.", ephemeral=True
            )

        for existing in items:
            for t in raw_triggers:
                if any(ext.casefold() == t.casefold() for ext in existing.triggers):
                    return await interaction.response.send_message(
                        f"⚠️ A responder matching `{t}` already exists (`{existing.name or existing.id}`).",
                        ephemeral=True,
                    )

        ping_str = self.ping_input.value.strip().lower()
        ping_val = ping_str in ("on", "true", "yes", "1", "enable", "enabled")

        rx_str = self.reaction_input.value.strip()
        rx_val = None
        if rx_str and rx_str.lower() not in ("none", "off", "disable", "disabled", "false"):
            rx_val = rx_str

        new_item = AutoResponderItem(
            id=str(uuid.uuid4())[:8],
            name=raw_triggers[0][:30],
            triggers=raw_triggers,
            match_mode=mode_val,
            replies=[clean_reply],
            reply_to_message=True,
            ping_user=ping_val,
            mention_author=ping_val,
            trigger_reaction=rx_val,
            reactions=[rx_val] if rx_val else [],
            created_by=self.author_id,
        )

        items.append(new_item)
        await self.cog._update_guild_cache(self.guild.id, settings, items)

        embed = discord.Embed(
            title="✅ Autoresponder Created",
            description=f"Responder **{new_item.name}** (`{new_item.id}`) is now active!",
            color=SUCCESS_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Triggers", value=", ".join(f"`{t}`" for t in raw_triggers), inline=True)
        embed.add_field(name="Match Mode", value=f"`{mode_val}`", inline=True)
        embed.add_field(name="Ping User", value="🔔 ON" if ping_val else "🔕 OFF", inline=True)
        embed.add_field(name="Trigger Reaction", value=f"😃 `{rx_val}`" if rx_val else "*Disabled*", inline=True)
        embed.add_field(name="Response Preview", value=f"\"{clean_reply[:150]}\"", inline=False)
        embed.set_footer(text=f"Total: {len(items)} / {'Unlimited' if limit == -1 else limit}")
        await interaction.response.send_message(embed=embed)


class AutoresponderPaginationView(discord.ui.View):
    """Interactive paginated view for browsing and managing configured autoresponders."""

    def __init__(
        self,
        cog: "AutoResponder",
        guild: discord.Guild,
        items: List[AutoResponderItem],
        limit_str: str,
        author_id: int,
        page_size: int = 5,
    ):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild = guild
        self.items = items
        self.limit_str = limit_str
        self.author_id = author_id
        self.page_size = page_size
        self.current_page = 0
        self.total_pages = max(1, (len(items) + page_size - 1) // page_size)
        self._update_controls()

    def _update_controls(self):
        self.prev_button.disabled = self.current_page <= 0
        self.next_button.disabled = self.current_page >= self.total_pages - 1

    def make_embed(self) -> discord.Embed:
        embed = discord.Embed(
            title=f"🤖 Autoresponders · {self.guild.name}",
            description=(
                f"Configured autoresponders in this server.\n"
                f"**Active Slots:** `{len(self.items)} / {self.limit_str}` · "
                f"**Page:** `{self.current_page + 1}/{self.total_pages}`\n"
            ),
            color=PREMIUM_COLOR,
            timestamp=datetime.now(timezone.utc),
        )

        if not self.items:
            embed.description += (
                "\n*No autoresponders configured yet!*\n"
                "Use `/autoresponder add <trigger> <reply>` or click **➕ Add Responder** below."
            )
            return embed

        start = self.current_page * self.page_size
        page_items = self.items[start : start + self.page_size]

        for item in page_items:
            status = "🟢 Active" if item.enabled else "🔴 Disabled"
            triggers_str = ", ".join(f"`{t}`" for t in item.triggers[:3])
            if len(item.triggers) > 3:
                triggers_str += f" *(+{len(item.triggers) - 3} more)*"

            reply_preview = (
                item.replies[0][:60] + "…"
                if item.replies and len(item.replies[0]) > 60
                else (item.replies[0] if item.replies else "*[Embed only]*")
            )
            embed_badge = f" · 🖼️ `{len(item.embeds)} embed(s)`" if item.embeds else ""
            rx_val = item.trigger_reaction or (item.reactions[0] if item.reactions else None)
            rx_badge = f" · 😃 Reaction: `{rx_val}`" if rx_val else " · 😃 Reaction: `None`"
            ping_badge = " · 🔔 Ping: `ON`" if item.ping_user else " · 🔕 Ping: `OFF`"

            details = [
                f"• **Status:** {status} · **Mode:** `{item.match_mode}`{ping_badge}{rx_badge}",
                f"• **Triggers:** {triggers_str or '`None`'}",
                f"• **Reply:** *\"{reply_preview}\"*{embed_badge}",
                f"• **Stats:** ⚡ `{item.hits}` hits · ⏱️ `{item.cooldown_user}s` user cooldown",
            ]
            if item.channels:
                details.append(f"• **Channels:** {len(item.channels)} restricted")
            if item.roles:
                details.append(f"• **Roles:** {len(item.roles)} restricted")

            embed.add_field(
                name=f"📌 {item.name or item.id} (ID: `{item.id}`)",
                value="\n".join(details),
                inline=False,
            )

        embed.set_footer(text=f"Use /autoresponder show <id> for details · Total items: {len(self.items)}")
        return embed

    @discord.ui.button(label="◀ Previous", style=discord.ButtonStyle.secondary, custom_id="ar_prev")
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("Only the command author can browse pages.", ephemeral=True)
        if self.current_page > 0:
            self.current_page -= 1
            self._update_controls()
            await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="Next ▶", style=discord.ButtonStyle.secondary, custom_id="ar_next")
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("Only the command author can browse pages.", ephemeral=True)
        if self.current_page < self.total_pages - 1:
            self.current_page += 1
            self._update_controls()
            await interaction.response.edit_message(embed=self.make_embed(), view=self)

    @discord.ui.button(label="➕ Add Responder", style=discord.ButtonStyle.success, custom_id="ar_add_btn")
    async def add_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("Only the command author can use this button.", ephemeral=True)
        if not interaction.user.guild_permissions.manage_guild:
            return await interaction.response.send_message("You need 'Manage Server' permissions to add responders.", ephemeral=True)
        await interaction.response.send_modal(AutoresponderCreateModal(cog=self.cog, guild=self.guild, author_id=self.author_id))

    @discord.ui.button(label="⚙️ Settings", style=discord.ButtonStyle.secondary, custom_id="ar_settings_btn")
    async def settings_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.author_id:
            return await interaction.response.send_message("Only the command author can use this button.", ephemeral=True)
        settings, _ = await self.cog._get_guild_cached(self.guild.id)
        embed = discord.Embed(
            title=f"⚙️ Autoresponder Settings · {self.guild.name}",
            color=PREMIUM_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Engine State", value="🟢 Enabled" if settings.enabled else "🔴 Disabled", inline=True)
        embed.add_field(name="Conflict Mode", value=f"`{settings.conflict_mode}`", inline=True)
        embed.add_field(name="Default Cooldown", value=f"`{settings.default_cooldown}s`", inline=True)
        embed.add_field(name="Default Ping User", value="🔔 ON" if settings.default_ping else "🔕 OFF", inline=True)
        embed.set_footer(text="Use /autoresponder settings to configure server options")
        await interaction.response.send_message(embed=embed, ephemeral=True)


class AutoResponder(commands.Cog):
    """
    Production-grade autoresponder system with matching engine,
    rich templating, variable rendering, quotas, and cache layer.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.engine = AutoResponderEngine()
        self.storage = AutoResponderStorage(bot)
        # In-memory guild cache: guild_id -> (settings, items)
        self._guild_cache: Dict[int, Tuple[GuildAutoResponderSettings, List[AutoResponderItem]]] = {}
        self._cache_lock = asyncio.Lock()

    async def _get_guild_cached(
        self, guild_id: int
    ) -> Tuple[GuildAutoResponderSettings, List[AutoResponderItem]]:
        """Retrieve guild autoresponder configuration from memory cache, loading if needed."""
        async with self._cache_lock:
            if guild_id in self._guild_cache:
                return self._guild_cache[guild_id]

            settings, items = await self.storage.get_guild_data(guild_id)
            self._guild_cache[guild_id] = (settings, items)
            return settings, items

    async def _update_guild_cache(
        self,
        guild_id: int,
        settings: GuildAutoResponderSettings,
        items: List[AutoResponderItem],
    ) -> None:
        """Update both persistence storage and in-memory cache atomically."""
        async with self._cache_lock:
            await self.storage.save_guild_data(guild_id, settings, items)
            self._guild_cache[guild_id] = (settings, items)

    async def _is_premium(self, guild_id: int) -> bool:
        checker = getattr(self.bot, "is_premium_guild", None)
        if not callable(checker):
            return False
        try:
            res = checker(guild_id)
            if hasattr(res, "__await__"):
                res = await res
            return bool(res)
        except Exception as exc:
            logger.warning("Premium check error for guild %s: %s", guild_id, exc)
            return False

    async def _get_tier_limit(self, guild_id: int) -> int:
        tier_getter = getattr(self.bot, "get_premium_tier", None)
        tier = await tier_getter(guild_id) if tier_getter else "FREE"
        tier = str(tier or "FREE").upper()

        cfg_getter = getattr(self.bot, "get_tier_config", None)
        cfg = cfg_getter(tier) if cfg_getter else {}
        features = cfg.get("features", {}) if isinstance(cfg, dict) else {}
        value = features.get("custom_responses") if isinstance(features, dict) else None
        if value is None:
            value = {
                "FREE": 0,
                "BASIC": 10,
                "PRO": 30,
                "ENTERPRISE": -1,
                "CUSTOM": -1,
                "GRANDFATHERED": -1,
            }.get(tier, 0)
        if isinstance(value, bool):
            return 10 if value else 0
        try:
            limit = int(value)
        except (TypeError, ValueError):
            return 0
        return limit if limit == -1 or limit >= 0 else 0

    def _find_item(
        self, items: List[AutoResponderItem], identifier: str
    ) -> Optional[AutoResponderItem]:
        """Find responder item by ID or exact trigger match."""
        ident = identifier.strip().casefold()
        # Check by ID first
        for item in items:
            if item.id.casefold() == ident:
                return item
        # Check by name
        for item in items:
            if item.name.casefold() == ident:
                return item
        # Check by primary trigger
        for item in items:
            for trig in item.triggers:
                if trig.casefold() == ident:
                    return item
        return None

    # ── Hot-Path Message Listener ─────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        # Ignore bots, webhooks, or DM messages
        if message.author.bot or not message.guild or message.webhook_id:
            return

        # Skip if message invokes a valid bot command
        try:
            ctx = await self.bot.get_context(message)
            if ctx.valid:
                return
        except Exception:
            pass

        # Check premium entitlement
        if not await self._is_premium(message.guild.id):
            return

        # Evaluate against memory cache (zero DB operations)
        settings, items = await self._get_guild_cached(message.guild.id)
        if not settings.enabled or not items or not message.content.strip():
            return

        member_roles = (
            {r.id for r in message.author.roles}
            if isinstance(message.author, discord.Member)
            else set()
        )

        matches = self.engine.evaluate_message(
            message_content=message.content,
            responders=items,
            settings=settings,
            channel_id=message.channel.id,
            member_role_ids=member_roles,
            user_id=message.author.id,
            guild_id=message.guild.id,
            dry_run=False,
        )

        if not matches:
            return

        for matched_item, _ in matches:
            asyncio.create_task(self._dispatch_response(message, matched_item))

    async def _dispatch_response(
        self, message: discord.Message, item: AutoResponderItem
    ) -> None:
        """Safely render, delay, and dispatch the autoresponder action."""
        # Optional delay
        if item.delay_seconds > 0:
            await asyncio.sleep(min(item.delay_seconds, 10.0))

        # Build response text
        content: Optional[str] = None
        selected_template: Optional[str] = None
        if item.replies:
            selected_template = random.choice(item.replies)
            rendered = self.engine.render_variables(selected_template, message)
            if rendered.strip():
                content = rendered[:2000]

        # Build embeds
        embeds = self.engine.build_embeds(item.embeds, message) if item.embeds else []

        # Mentions & Ping behavior
        author_mention_in_text = (
            f"<@{message.author.id}>" in (content or "")
            or f"<@!{message.author.id}>" in (content or "")
            or (selected_template is not None and "{user.mention}" in selected_template)
        )

        if item.ping_user:
            if author_mention_in_text:
                # Text already mentions user: do not duplicate ping via reply header
                allowed_mentions = discord.AllowedMentions(
                    everyone=False,
                    roles=False,
                    users=[message.author],
                    replied_user=False,
                )
            else:
                if item.reply_to_message:
                    # Ping author via reply header
                    allowed_mentions = discord.AllowedMentions(
                        everyone=False,
                        roles=False,
                        users=[message.author],
                        replied_user=True,
                    )
                else:
                    # Prepend author mention once if not replying directly
                    content = f"{message.author.mention} {content}" if content else message.author.mention
                    allowed_mentions = discord.AllowedMentions(
                        everyone=False,
                        roles=False,
                        users=[message.author],
                        replied_user=False,
                    )
        else:
            # ping_user is False: Never ping unless explicitly in text template
            if author_mention_in_text:
                allowed_mentions = discord.AllowedMentions(
                    everyone=False,
                    roles=False,
                    users=[message.author],
                    replied_user=False,
                )
            else:
                allowed_mentions = discord.AllowedMentions(
                    everyone=False,
                    roles=False,
                    users=False,
                    replied_user=False,
                )

        # 1. Dispatch text reply or embed
        try:
            if content or embeds:
                if item.reply_to_message:
                    await message.reply(
                        content=content,
                        embeds=embeds,
                        allowed_mentions=allowed_mentions,
                    )
                else:
                    await message.channel.send(
                        content=content,
                        embeds=embeds,
                        allowed_mentions=allowed_mentions,
                    )
        except discord.Forbidden:
            logger.warning(
                "Missing permissions to send autoresponse in channel %s (guild %s)",
                message.channel.id,
                message.guild.id,
            )
        except discord.HTTPException as exc:
            logger.warning("Discord HTTP error sending autoresponse: %s", exc)

        # 2. Trigger reaction: React to the original message (failure NEVER blocks text response)
        reaction_to_add = (
            item.trigger_reaction
            if item.trigger_reaction and item.trigger_reaction.lower() not in ("none", "off", "disable", "disabled", "false")
            else (item.reactions[0] if item.reactions else None)
        )
        if reaction_to_add:
            try:
                await message.add_reaction(reaction_to_add)
            except (discord.HTTPException, TypeError, ValueError) as rx_err:
                logger.debug(
                    "Autoresponder: Could not add reaction '%s' to message %s: %s",
                    reaction_to_add,
                    message.id,
                    rx_err,
                )
            except Exception as rx_err:
                logger.debug(
                    "Autoresponder: Unexpected error adding reaction '%s' to message %s: %s",
                    reaction_to_add,
                    message.id,
                    rx_err,
                )

        # 3. Optional delete triggering message
        if item.delete_trigger:
            try:
                await message.delete()
            except (discord.HTTPException, discord.Forbidden):
                pass

        # 4. Record stats hit asynchronously
        item.hits += 1
        item.last_triggered_at = datetime.now(timezone.utc).isoformat()
        asyncio.create_task(self.storage.record_hit(message.guild.id, item.id))

    # ── Command Suite ─────────────────────────────────────────────────────────

    @commands.hybrid_group(
        name="autoresponder",
        description="Automated keyword triggers and rich responses",
        fallback="list",
        aliases=["ar", "autoreply", "custom_reply"],
    )
    @commands.guild_only()
    async def autoresponder(self, ctx: commands.Context):
        """View all active autoresponders configured in this server."""
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send(
                "❌ **Premium Required**: Autoresponders require an active server subscription. "
                "Use `/premium_price` to upgrade!",
                ephemeral=True,
            )

        settings, items = await self._get_guild_cached(ctx.guild.id)
        limit = await self._get_tier_limit(ctx.guild.id)
        limit_str = "Unlimited" if limit == -1 else str(limit)

        view = AutoresponderPaginationView(
            cog=self,
            guild=ctx.guild,
            items=items,
            limit_str=limit_str,
            author_id=ctx.author.id,
        )
        await ctx.send(embed=view.make_embed(), view=view)

    @autoresponder.command(name="add", description="Create a new autoresponder")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(
        trigger="Trigger keyword/phrase (or multiple comma-separated)",
        reply="Bot response text (supports {user}, {server}, {channel}, etc.)",
        match_mode="Matching mode (contains, exact, startswith, endswith, whole_word, regex)",
        ping_user="Whether to ping the triggering user (True=ON, False=OFF)",
        reaction="Optional emoji to react to the trigger message (or 'none')",
        name="Optional friendly name/label for this responder",
        reply_to="Whether to reply directly to the triggering message",
        channel="Restrict responder to a specific channel",
        role="Restrict responder to members with a specific role",
    )
    @app_commands.choices(match_mode=[
        app_commands.Choice(name="Contains (Anywhere in message)", value="contains"),
        app_commands.Choice(name="Exact Match (Whole message)", value="exact"),
        app_commands.Choice(name="Starts With (Beginning of message)", value="startswith"),
        app_commands.Choice(name="Ends With (End of message)", value="endswith"),
        app_commands.Choice(name="Whole Word (Distinct word match)", value="whole_word"),
        app_commands.Choice(name="Regex (Advanced Pattern)", value="regex"),
    ])
    async def ar_add(
        self,
        ctx: commands.Context,
        trigger: str,
        reply: str,
        match_mode: Optional[app_commands.Choice[str]] = None,
        ping_user: bool = False,
        reaction: Optional[str] = None,
        name: Optional[str] = None,
        reply_to: bool = True,
        channel: Optional[discord.TextChannel] = None,
        role: Optional[discord.Role] = None,
    ):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**: Server subscription needed.", ephemeral=True)

        mode_val = (
            match_mode.value
            if isinstance(match_mode, app_commands.Choice)
            else (str(match_mode or "contains").lower())
        )
        if mode_val not in VALID_MATCH_MODES:
            mode_val = "contains"

        # Tier-based quotas
        limit = await self._get_tier_limit(ctx.guild.id)
        settings, items = await self._get_guild_cached(ctx.guild.id)
        if limit != -1 and len(items) >= limit:
            return await ctx.send(
                f"❌ **Slot Limit Reached**: Your tier allows up to `{limit}` autoresponders. "
                "Use `/premium_price` to upgrade!",
                ephemeral=True,
            )

        # Regex feature entitlement check
        tier = await self.bot.get_premium_tier(ctx.guild.id) if hasattr(self.bot, "get_premium_tier") else "BASIC"
        if mode_val == "regex" and str(tier).upper() in ("FREE", "BASIC"):
            return await ctx.send(
                "❌ **Pro Perk**: Regular expression triggers require a **PRO** or higher tier subscription.",
                ephemeral=True,
            )

        # Split multiple triggers if comma-separated
        raw_triggers = [t.strip() for t in trigger.split(",") if t.strip()]
        if not raw_triggers:
            return await ctx.send("❌ Trigger cannot be empty.", ephemeral=True)

        # Validate triggers
        for t in raw_triggers:
            if len(t) > 100:
                return await ctx.send(f"❌ Trigger `{t[:20]}…` exceeds 100 characters.", ephemeral=True)
            if mode_val == "regex":
                is_valid, err = sanitize_regex(t)
                if not is_valid:
                    return await ctx.send(f"❌ Invalid regular expression: {err}", ephemeral=True)

        clean_reply = reply.strip()
        if not clean_reply or len(clean_reply) > 2000:
            return await ctx.send("❌ Reply must contain between 1 and 2,000 characters.", ephemeral=True)

        # Check duplicate
        for item in items:
            for t in raw_triggers:
                if any(existing.casefold() == t.casefold() for existing in item.triggers):
                    return await ctx.send(
                        f"⚠️ A responder matching `{t}` already exists (`{item.name or item.id}`). "
                        "Delete or edit it first.",
                        ephemeral=True,
                    )

        # Resolve reaction
        rx_val = None
        if reaction:
            cleaned_rx = reaction.strip()
            if cleaned_rx.lower() not in ("none", "off", "disable", "disabled", "false"):
                rx_val = cleaned_rx

        new_item = AutoResponderItem(
            id=str(uuid.uuid4())[:8],
            name=name.strip()[:40] if name else raw_triggers[0][:30],
            triggers=raw_triggers,
            match_mode=mode_val,
            replies=[clean_reply],
            reply_to_message=reply_to,
            ping_user=ping_user,
            mention_author=ping_user,
            trigger_reaction=rx_val,
            reactions=[rx_val] if rx_val else [],
            channels=[channel.id] if channel else [],
            roles=[role.id] if role else [],
            created_by=ctx.author.id,
        )

        items.append(new_item)
        await self._update_guild_cache(ctx.guild.id, settings, items)

        embed = discord.Embed(
            title="✅ Autoresponder Created",
            description=f"Responder **{new_item.name}** (`{new_item.id}`) is now active!",
            color=SUCCESS_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Triggers", value=", ".join(f"`{t}`" for t in raw_triggers), inline=True)
        embed.add_field(name="Match Mode", value=f"`{mode_val}`", inline=True)
        embed.add_field(name="Ping User", value="🔔 **ON**" if ping_user else "🔕 **OFF**", inline=True)
        embed.add_field(name="Trigger Reaction", value=f"😃 `{rx_val}`" if rx_val else "*Disabled*", inline=True)
        embed.add_field(name="Reply-To", value="Yes" if reply_to else "No", inline=True)
        if channel:
            embed.add_field(name="Channel Restriction", value=channel.mention, inline=True)
        if role:
            embed.add_field(name="Role Restriction", value=role.mention, inline=True)
        embed.add_field(name="Response Preview", value=f"\"{clean_reply[:150]}\"", inline=False)
        embed.set_footer(text=f"Total: {len(items)} / {'Unlimited' if limit == -1 else limit}")
        await ctx.send(embed=embed)

    @autoresponder.command(name="edit", description="Modify an existing autoresponder")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(
        identifier="ID, name, or primary trigger of the responder to edit",
        trigger="New trigger phrase (or comma-separated phrases)",
        reply="New response text",
        match_mode="New matching mode",
        ping_user="Toggle pinging the user on or off (True=ON, False=OFF)",
        reaction="New trigger reaction emoji (or 'none' to remove)",
        name="New friendly name",
        enabled="Enable or disable this responder",
        priority="Priority number (higher = matched first)",
        cooldown="User cooldown in seconds",
    )
    @app_commands.choices(match_mode=[
        app_commands.Choice(name="Contains", value="contains"),
        app_commands.Choice(name="Exact Match", value="exact"),
        app_commands.Choice(name="Starts With", value="startswith"),
        app_commands.Choice(name="Ends With", value="endswith"),
        app_commands.Choice(name="Whole Word", value="whole_word"),
        app_commands.Choice(name="Regex", value="regex"),
    ])
    async def ar_edit(
        self,
        ctx: commands.Context,
        identifier: str,
        trigger: Optional[str] = None,
        reply: Optional[str] = None,
        match_mode: Optional[app_commands.Choice[str]] = None,
        ping_user: Optional[bool] = None,
        reaction: Optional[str] = None,
        name: Optional[str] = None,
        enabled: Optional[bool] = None,
        priority: Optional[int] = None,
        cooldown: Optional[float] = None,
    ):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.", ephemeral=True)

        settings, items = await self._get_guild_cached(ctx.guild.id)
        target = self._find_item(items, identifier)
        if not target:
            return await ctx.send(f"❌ Could not find an autoresponder matching `{identifier}`.", ephemeral=True)

        changes = []
        if trigger is not None:
            raw_triggers = [t.strip() for t in trigger.split(",") if t.strip()]
            if not raw_triggers:
                return await ctx.send("❌ Trigger cannot be empty.", ephemeral=True)
            target.triggers = raw_triggers
            changes.append(f"• **Triggers:** {', '.join(f'`{t}`' for t in raw_triggers)}")

        if reply is not None:
            clean_reply = reply.strip()
            if not clean_reply or len(clean_reply) > 2000:
                return await ctx.send("❌ Reply must contain 1–2,000 characters.", ephemeral=True)
            target.replies = [clean_reply]
            changes.append(f"• **Reply:** \"{clean_reply[:60]}…\"")

        if match_mode is not None:
            mode_val = match_mode.value if isinstance(match_mode, app_commands.Choice) else str(match_mode).lower()
            if mode_val in VALID_MATCH_MODES:
                target.match_mode = mode_val
                changes.append(f"• **Match Mode:** `{mode_val}`")

        if ping_user is not None:
            target.ping_user = ping_user
            target.mention_author = ping_user
            changes.append(f"• **Ping User:** {'🔔 ON' if ping_user else '🔕 OFF'}")

        if reaction is not None:
            cleaned_rx = reaction.strip()
            if cleaned_rx.lower() in ("none", "off", "disable", "disabled", "remove", "clear"):
                target.trigger_reaction = None
                target.reactions = []
                changes.append("• **Trigger Reaction:** *Disabled*")
            else:
                target.trigger_reaction = cleaned_rx
                target.reactions = [cleaned_rx]
                changes.append(f"• **Trigger Reaction:** `{cleaned_rx}`")

        if name is not None:
            target.name = name.strip()[:40]
            changes.append(f"• **Name:** `{target.name}`")

        if enabled is not None:
            target.enabled = enabled
            changes.append(f"• **State:** {'🟢 Enabled' if enabled else '🔴 Disabled'}")

        if priority is not None:
            target.priority = priority
            changes.append(f"• **Priority:** `{priority}`")

        if cooldown is not None and cooldown >= 0.0:
            target.cooldown_user = cooldown
            changes.append(f"• **Cooldown:** `{cooldown}s`")

        if not changes:
            return await ctx.send("ℹ️ No changes were specified.", ephemeral=True)

        target.updated_at = datetime.now(timezone.utc).isoformat()
        await self._update_guild_cache(ctx.guild.id, settings, items)

        embed = discord.Embed(
            title=f"✏️ Autoresponder Updated · {target.name}",
            description="\n".join(changes),
            color=SUCCESS_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_footer(text=f"ID: {target.id}")
        await ctx.send(embed=embed)

    @autoresponder.command(name="delete", description="Remove an autoresponder", aliases=["remove"])
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(identifier="ID, name, or trigger of the responder to delete")
    async def ar_delete(self, ctx: commands.Context, identifier: str):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.", ephemeral=True)

        settings, items = await self._get_guild_cached(ctx.guild.id)
        target = self._find_item(items, identifier)
        if not target:
            return await ctx.send(f"❌ Could not find an autoresponder matching `{identifier}`.", ephemeral=True)

        items.remove(target)
        await self._update_guild_cache(ctx.guild.id, settings, items)

        embed = discord.Embed(
            title="🗑️ Autoresponder Deleted",
            description=f"Successfully deleted autoresponder **{target.name}** (`{target.id}`).",
            color=ERROR_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        await ctx.send(embed=embed)

    @autoresponder.command(name="show", description="Show detailed settings for an autoresponder", aliases=["info"])
    @commands.guild_only()
    @app_commands.describe(identifier="ID, name, or trigger of the responder to inspect")
    async def ar_show(self, ctx: commands.Context, identifier: str):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.", ephemeral=True)

        _, items = await self._get_guild_cached(ctx.guild.id)
        target = self._find_item(items, identifier)
        if not target:
            return await ctx.send(f"❌ Could not find an autoresponder matching `{identifier}`.", ephemeral=True)

        embed = discord.Embed(
            title=f"🔍 Autoresponder Dossier · {target.name}",
            color=CYAN_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Identifier", value=f"`{target.id}`", inline=True)
        embed.add_field(name="Status", value="🟢 Enabled" if target.enabled else "🔴 Disabled", inline=True)
        embed.add_field(name="Match Mode", value=f"`{target.match_mode}`", inline=True)

        triggers_val = ", ".join(f"`{t}`" for t in target.triggers) or "`None`"
        embed.add_field(name="Configured Triggers", value=triggers_val, inline=False)

        reply_val = target.replies[0] if target.replies else "*No text reply (embeds only)*"
        embed.add_field(name="Text Reply Template", value=f"```{reply_val[:800]}```", inline=False)

        embed.add_field(name="Ping Triggering User", value="🔔 ON" if target.ping_user else "🔕 OFF", inline=True)
        rx_val = target.trigger_reaction or (target.reactions[0] if target.reactions else None)
        embed.add_field(name="Trigger Reaction", value=f"😃 `{rx_val}`" if rx_val else "*None (Disabled)*", inline=True)
        embed.add_field(name="Reply to Message", value="Yes" if target.reply_to_message else "No", inline=True)

        embed.add_field(name="Priority", value=f"`{target.priority}`", inline=True)
        embed.add_field(name="User Cooldown", value=f"`{target.cooldown_user}s`", inline=True)
        embed.add_field(name="Hit Count", value=f"`{target.hits}` triggers", inline=True)

        # Restrictions
        ch_text = ", ".join(f"<#{c}>" for c in target.channels) if target.channels else "*All channels*"
        rl_text = ", ".join(f"<@&{r}>" for r in target.roles) if target.roles else "*All roles*"
        embed.add_field(name="Allowed Channels", value=ch_text, inline=True)
        embed.add_field(name="Allowed Roles", value=rl_text, inline=True)

        if target.embeds:
            embed.add_field(name="Rich Embeds", value=f"`{len(target.embeds)}` custom embed(s) attached", inline=False)

        embed.set_footer(text=f"Created {target.created_at[:10]}")
        await ctx.send(embed=embed)

    @autoresponder.command(name="enable", description="Enable a disabled autoresponder")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(identifier="ID, name, or trigger of the responder to enable")
    async def ar_enable(self, ctx: commands.Context, identifier: str):
        settings, items = await self._get_guild_cached(ctx.guild.id)
        target = self._find_item(items, identifier)
        if not target:
            return await ctx.send(f"❌ Responder `{identifier}` not found.", ephemeral=True)
        target.enabled = True
        await self._update_guild_cache(ctx.guild.id, settings, items)
        await ctx.send(f"🟢 Enabled autoresponder **{target.name}** (`{target.id}`).")

    @autoresponder.command(name="disable", description="Disable an active autoresponder")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(identifier="ID, name, or trigger of the responder to disable")
    async def ar_disable(self, ctx: commands.Context, identifier: str):
        settings, items = await self._get_guild_cached(ctx.guild.id)
        target = self._find_item(items, identifier)
        if not target:
            return await ctx.send(f"❌ Responder `{identifier}` not found.", ephemeral=True)
        target.enabled = False
        await self._update_guild_cache(ctx.guild.id, settings, items)
        await ctx.send(f"🔴 Disabled autoresponder **{target.name}** (`{target.id}`).")

    @autoresponder.command(name="test", description="Simulate a message and test autoresponder matching")
    @commands.guild_only()
    @app_commands.describe(
        message="The message text you want to test against autoresponders",
        channel="Optional channel to simulate (defaults to current channel)",
    )
    async def ar_test(
        self,
        ctx: commands.Context,
        message: str,
        channel: Optional[discord.TextChannel] = None,
    ):
        """Simulate how the matching engine evaluates a message without sending replies."""
        settings, items = await self._get_guild_cached(ctx.guild.id)
        sim_channel = channel or ctx.channel
        member_roles = (
            {r.id for r in ctx.author.roles}
            if isinstance(ctx.author, discord.Member)
            else set()
        )

        matches = self.engine.evaluate_message(
            message_content=message,
            responders=items,
            settings=settings,
            channel_id=sim_channel.id,
            member_role_ids=member_roles,
            user_id=ctx.author.id,
            guild_id=ctx.guild.id,
            dry_run=True,
        )

        embed = discord.Embed(
            title="🧪 Autoresponder Test Simulation",
            description=f"**Simulated Message:** \"{message}\"\n**Channel:** {sim_channel.mention}",
            color=BRAND_COLOR,
            timestamp=datetime.now(timezone.utc),
        )

        if not matches:
            embed.color = ERROR_COLOR
            embed.add_field(
                name="Result",
                value="❌ **No match found.** No autoresponder would trigger on this message.",
                inline=False,
            )
            return await ctx.send(embed=embed)

        embed.color = SUCCESS_COLOR
        embed.add_field(
            name="Result",
            value=f"✅ **{len(matches)} responder(s) matched!**",
            inline=False,
        )

        for item, trig in matches:
            rendered = (
                self.engine.render_variables(item.replies[0], ctx.message)
                if item.replies
                else "*[Embed only]*"
            )
            ping_info = "🔔 ON (User will be pinged)" if item.ping_user else "🔕 OFF (Silent)"
            rx_val = item.trigger_reaction or (item.reactions[0] if item.reactions else None)
            rx_info = f"`{rx_val}`" if rx_val else "*None*"

            embed.add_field(
                name=f"🎯 {item.name} (`{item.id}`)",
                value=(
                    f"• **Matched Trigger:** `{trig}` (`{item.match_mode}`)\n"
                    f"• **Priority:** `{item.priority}`\n"
                    f"• **Ping User:** {ping_info}\n"
                    f"• **Trigger Reaction:** {rx_info}\n"
                    f"• **Rendered Output:** \"{rendered[:120]}\""
                ),
                inline=False,
            )

        await ctx.send(embed=embed)

    @autoresponder.command(name="duplicate", description="Duplicate an existing autoresponder")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(
        identifier="ID, name, or trigger of responder to duplicate",
        new_trigger="Optional different trigger for the copy",
    )
    async def ar_duplicate(
        self,
        ctx: commands.Context,
        identifier: str,
        new_trigger: Optional[str] = None,
    ):
        settings, items = await self._get_guild_cached(ctx.guild.id)
        target = self._find_item(items, identifier)
        if not target:
            return await ctx.send(f"❌ Responder `{identifier}` not found.", ephemeral=True)

        limit = await self._get_tier_limit(ctx.guild.id)
        if limit != -1 and len(items) >= limit:
            return await ctx.send(f"❌ Cannot duplicate: server slot limit reached (`{limit}`).", ephemeral=True)

        copy_item = AutoResponderItem.from_dict(target.to_dict())
        copy_item.id = str(uuid.uuid4())[:8]
        copy_item.name = f"{target.name} (Copy)"
        copy_item.hits = 0
        copy_item.created_at = datetime.now(timezone.utc).isoformat()
        copy_item.updated_at = None

        if new_trigger:
            copy_item.triggers = [new_trigger.strip()]

        items.append(copy_item)
        await self._update_guild_cache(ctx.guild.id, settings, items)
        await ctx.send(f"✅ Duplicated **{target.name}** into **{copy_item.name}** (`{copy_item.id}`).")

    @autoresponder.command(name="settings", description="Configure server-wide autoresponder settings")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(
        enabled="Toggle autoresponder engine on or off server-wide",
        conflict_mode="How multiple matches are handled (first_match or all_matches)",
        default_cooldown="Default user cooldown in seconds",
        default_ping="Default ping setting for newly added responders (ON / OFF)",
    )
    @app_commands.choices(conflict_mode=[
        app_commands.Choice(name="First Match (Single highest priority reply)", value="first_match"),
        app_commands.Choice(name="All Matches (Trigger all matching responders)", value="all_matches"),
    ])
    async def ar_settings(
        self,
        ctx: commands.Context,
        enabled: Optional[bool] = None,
        conflict_mode: Optional[app_commands.Choice[str]] = None,
        default_cooldown: Optional[float] = None,
        default_ping: Optional[bool] = None,
    ):
        settings, items = await self._get_guild_cached(ctx.guild.id)
        updated = False

        if enabled is not None:
            settings.enabled = enabled
            updated = True
        if conflict_mode is not None:
            c_val = conflict_mode.value if isinstance(conflict_mode, app_commands.Choice) else str(conflict_mode).lower()
            if c_val in VALID_CONFLICT_MODES:
                settings.conflict_mode = c_val
                updated = True
        if default_cooldown is not None and default_cooldown >= 0.0:
            settings.default_cooldown = default_cooldown
            updated = True
        if default_ping is not None:
            settings.default_ping = default_ping
            updated = True

        if updated:
            await self._update_guild_cache(ctx.guild.id, settings, items)

        embed = discord.Embed(
            title=f"⚙️ Autoresponder Server Settings · {ctx.guild.name}",
            color=PREMIUM_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Engine Master Switch", value="🟢 Enabled" if settings.enabled else "🔴 Disabled", inline=True)
        embed.add_field(name="Conflict Mode", value=f"`{settings.conflict_mode}`", inline=True)
        embed.add_field(name="Default Cooldown", value=f"`{settings.default_cooldown}s`", inline=True)
        embed.add_field(name="Default Ping User", value="🔔 ON" if settings.default_ping else "🔕 OFF", inline=True)
        embed.add_field(
            name="Ignored Channels",
            value=f"`{len(settings.ignored_channels)}` channel(s) ignored",
            inline=True,
        )
        embed.add_field(
            name="Ignored Roles",
            value=f"`{len(settings.ignored_roles)}` role(s) ignored",
            inline=True,
        )
        await ctx.send(embed=embed)

    @autoresponder.command(name="export", description="Export server autoresponders as JSON")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def ar_export(self, ctx: commands.Context):
        settings, items = await self._get_guild_cached(ctx.guild.id)
        export_payload = {
            "version": 1,
            "guild_id": ctx.guild.id,
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "settings": settings.to_dict(),
            "responders": [item.to_dict() for item in items],
        }
        json_str = json.dumps(export_payload, indent=2, ensure_ascii=False)

        if len(json_str) < 1800:
            await ctx.send(f"📋 **Autoresponder Export ({len(items)} items):**\n```json\n{json_str}\n```")
        else:
            file = discord.File(
                io.BytesIO(json_str.encode("utf-8")),
                filename=f"nexora_autoresponders_{ctx.guild.id}.json",
            )
            await ctx.send(f"📁 Exported `{len(items)}` autoresponders for **{ctx.guild.name}**:", file=file)

    @autoresponder.command(name="import", description="Import autoresponders from a JSON configuration")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(json_data="Paste JSON exported from Nexora autoresponder")
    async def ar_import(self, ctx: commands.Context, json_data: str):
        try:
            payload = json.loads(json_data)
        except Exception as exc:
            return await ctx.send(f"❌ Invalid JSON string: {exc}", ephemeral=True)

        if not isinstance(payload, dict) or "responders" not in payload:
            return await ctx.send("❌ JSON must contain a `'responders'` array.", ephemeral=True)

        raw_items = payload.get("responders", [])
        if not isinstance(raw_items, list):
            return await ctx.send("❌ `'responders'` must be a list.", ephemeral=True)

        settings, current_items = await self._get_guild_cached(ctx.guild.id)
        limit = await self._get_tier_limit(ctx.guild.id)

        added = 0
        for r in raw_items:
            if not isinstance(r, dict):
                continue
            if limit != -1 and len(current_items) >= limit:
                break
            imported_item = AutoResponderItem.from_dict(r)
            imported_item.id = str(uuid.uuid4())[:8]  # Regenerate ID to guarantee uniqueness
            imported_item.hits = 0
            current_items.append(imported_item)
            added += 1

        await self._update_guild_cache(ctx.guild.id, settings, current_items)
        await ctx.send(f"✅ Successfully imported `{added}` autoresponders! (Total: `{len(current_items)}`)")

    @autoresponder.command(name="stats", description="View analytics for this server's autoresponders")
    @commands.guild_only()
    async def ar_stats(self, ctx: commands.Context):
        _, items = await self._get_guild_cached(ctx.guild.id)
        total_hits = sum(item.hits for item in items)
        active_count = sum(1 for item in items if item.enabled)

        embed = discord.Embed(
            title=f"📊 Autoresponder Analytics · {ctx.guild.name}",
            color=PREMIUM_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Total Responders", value=f"`{len(items)}`", inline=True)
        embed.add_field(name="Active Responders", value=f"`{active_count}`", inline=True)
        embed.add_field(name="Lifetime Triggers", value=f"`{total_hits}` hits", inline=True)

        # Top 5 most triggered responders
        sorted_by_hits = sorted(items, key=lambda x: x.hits, reverse=True)[:5]
        if sorted_by_hits and sorted_by_hits[0].hits > 0:
            lines = [
                f"`#{i+1}` **{item.name}** (`{item.triggers[0] if item.triggers else item.id}`) — ⚡ `{item.hits}` hits"
                for i, item in enumerate(sorted_by_hits)
                if item.hits > 0
            ]
            embed.add_field(name="🏆 Top Triggered Responders", value="\n".join(lines), inline=False)

        await ctx.send(embed=embed)

    @autoresponder.command(name="help", description="Autoresponder syntax guide, variables, and examples")
    async def ar_help(self, ctx: commands.Context):
        embed = discord.Embed(
            title="📖 Nexora Autoresponder Master Guide",
            description=(
                "Nexora's autoresponder lets you automate keyword replies, welcome messages, FAQs, "
                "and custom moderation notes without touching code!"
            ),
            color=BRAND_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(
            name="🎯 Matching Modes",
            value=(
                "• `contains` — Matches if trigger appears anywhere in the message\n"
                "• `exact` — Entire message must match trigger exactly\n"
                "• `startswith` — Message must begin with trigger\n"
                "• `endswith` — Message must end with trigger\n"
                "• `whole_word` — Matches trigger as an isolated word\n"
                "• `regex` — Advanced Python regular expressions (Pro Tier)"
            ),
            inline=False,
        )
        embed.add_field(
            name="🪄 Dynamic Template Variables",
            value=(
                "• `{user}` / `{user.mention}` — Author display name / mention\n"
                "• `{user.id}` / `{user.avatar}` — Author ID / avatar URL\n"
                "• `{server}` / `{server.id}` — Server name / ID\n"
                "• `{channel}` / `{channel.id}` — Channel mention / ID\n"
                "• `{members}` — Current server member count\n"
                "• `{created_at}` — Relative time of triggering message\n"
                "• `{random:1-100}` — Random number between min and max"
            ),
            inline=False,
        )
        embed.add_field(
            name="⚡ Quick Commands",
            value=(
                "• `/autoresponder add <trigger> <reply>` — Create responder\n"
                "• `/autoresponder test <message>` — Test matching without sending\n"
                "• `/autoresponder list` — Browse all configured responders\n"
                "• `/autoresponder edit <id> [options]` — Modify settings"
            ),
            inline=False,
        )
        embed.set_footer(text="Nexora Premium · Production Autoresponder Suite")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoResponder(bot))
    logger.debug("Loaded AutoResponder Cog")

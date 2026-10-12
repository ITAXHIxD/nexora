"""
cogs/premium/autoreply.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Smart Custom Auto-Responder Engine for Nexora Premium.

Enables servers to configure automated keyword triggers and responses
with dynamic template variables and tier-based slot quotas.

Tier limits:
  • Free: 0 slots
  • Basic: 10 slots
  • Pro: 30 slots
  • Enterprise / Custom / Grandfathered: Unlimited

Template variables:
  • {user}          — Author display name
  • {user.mention}  — Author @mention
  • {server}        — Guild name
  • {channel}       — Channel #mention
  • {members}       — Guild member count
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Optional, List, Dict
from types import SimpleNamespace

import discord
from discord import app_commands
from discord.ext import commands

from utils.premium_storage import load_premium_data, save_premium_data

from utils.ui import (
    BRAND_COLOR,
    PREMIUM_COLOR,
    SUCCESS_COLOR,
    ERROR_COLOR,
    CYAN_COLOR,
    ts_format,
)

logger = logging.getLogger(__name__)


class AutoResponder(commands.Cog):
    """Automated keyword responses with dynamic variables and anti-spam protection."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Cool down per guild + user, rather than suppressing that member in all servers.
        self._user_cooldowns: Dict[tuple[int, int], float] = {}

    def _get_col(self):
        db = getattr(self.bot, "mongo_db", None)
        return db["premium"] if db is not None else None

    async def _is_premium(self, guild_id: int) -> bool:
        checker = getattr(self.bot, "is_premium_guild", None)
        if not callable(checker):
            return False
        try:
            result = checker(guild_id)
            if hasattr(result, "__await__"):
                result = await result
            return bool(result)
        except Exception as exc:
            logger.warning("Auto-responder premium check failed for guild %s: %s", guild_id, exc)
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
                "FREE": 0, "BASIC": 10, "PRO": 30,
                "ENTERPRISE": -1, "CUSTOM": -1, "GRANDFATHERED": -1,
            }.get(tier, 0)
        if isinstance(value, bool):
            return 10 if value else 0
        try:
            limit = int(value)
        except (TypeError, ValueError):
            return 0
        return limit if limit == -1 or limit >= 0 else 0

    def _get_local_replies(self, guild_id: int) -> List[dict]:
        data = load_premium_data()
        subscription = data.get("subscriptions", {}).get(str(guild_id), {})
        if not isinstance(subscription, dict):
            return []
        replies = subscription.get("custom_replies", [])
        return replies if isinstance(replies, list) else []

    def _save_local_replies(self, guild_id: int, replies: List[dict]) -> None:
        data = load_premium_data()
        subscriptions = data.setdefault("subscriptions", {})
        key = str(guild_id)
        subscription = subscriptions.get(key)
        if not isinstance(subscription, dict):
            subscription = {}
        subscription["custom_replies"] = replies
        subscriptions[key] = subscription
        save_premium_data(data)

    async def _get_replies(self, guild_id: int) -> List[dict]:
        col = self._get_col()
        if col is not None:
            try:
                doc = await col.find_one({"_id": int(guild_id)})
                # Only use the Mongo document's list when it is attached to a
                # premium record. A bare upsert must not shadow local entitlement.
                if isinstance(doc, dict) and doc.get("tier") and isinstance(doc.get("custom_replies"), list):
                    return doc["custom_replies"]
            except Exception as exc:
                logger.warning("Auto-responder Mongo read failed; using local fallback: %s", exc)
        return self._get_local_replies(guild_id)

    async def _save_replies(self, guild_id: int, replies: List[dict]) -> None:
        col = self._get_col()
        if col is not None:
            try:
                # Do not upsert a partial document that hides a local premium grant
                # or overwrites the server's tier metadata.
                doc = await col.find_one({"_id": int(guild_id)})
                if isinstance(doc, dict) and doc.get("tier"):
                    await col.update_one({"_id": int(guild_id)}, {"$set": {"custom_replies": replies}})
                    return
            except Exception as exc:
                logger.warning("Auto-responder Mongo write failed; saving locally: %s", exc)
        self._save_local_replies(guild_id, replies)

    async def _record_hit(self, guild_id: int, reply_id: str) -> None:
        col = self._get_col()
        if col is not None:
            try:
                result = await col.update_one(
                    {"_id": int(guild_id), "custom_replies.id": reply_id},
                    {"$inc": {"custom_replies.$.hits": 1}},
                )
                if getattr(result, "matched_count", 0):
                    return
            except Exception as exc:
                logger.debug("Auto-responder hit counter update failed: %s", exc)
        try:
            replies = self._get_local_replies(guild_id)
            for item in replies:
                if item.get("id") == reply_id:
                    item["hits"] = int(item.get("hits", 0)) + 1
                    break
            self._save_local_replies(guild_id, replies)
        except Exception as exc:
            logger.debug("Auto-responder local hit counter update failed: %s", exc)

    def _format_reply(self, template: str, message: discord.Message) -> str:
        guild = message.guild
        replacements = {
            "{user.mention}": message.author.mention,
            "{user}": message.author.display_name,
            "{user.id}": str(message.author.id),
            "{server}": guild.name,
            "{guild.id}": str(guild.id),
            "{channel}": message.channel.mention,
            "{channel.id}": str(message.channel.id),
            "{members}": str(guild.member_count or len(guild.members)),
            "{created_at}": discord.utils.format_dt(message.created_at, style="R"),
        }
        text = template
        for token in sorted(replacements, key=len, reverse=True):
            text = text.replace(token, replacements[token])
        return text[:1997] + "..." if len(text) > 2000 else text

    # ── Listener for Automatic Response ───────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Resolve real prefix rules (including callable and mention-based prefixes).
        try:
            ctx = await self.bot.get_context(message)
            if ctx.valid:
                return
        except Exception as exc:
            logger.debug("Auto-responder command detection failed: %s", exc)

        if not await self._is_premium(message.guild.id):
            return

        replies = await self._get_replies(message.guild.id)
        content_clean = message.content.casefold().strip()
        if not replies or not content_clean:
            return

        matches = []
        priorities = {"exact": 3, "startswith": 2, "contains": 1}
        for item in replies:
            trigger = str(item.get("trigger", "")).casefold().strip()
            mode = str(item.get("match_mode", "contains")).casefold()
            if not trigger or mode not in priorities:
                continue
            matched = (
                (mode == "exact" and content_clean == trigger)
                or (mode == "startswith" and content_clean.startswith(trigger))
                or (mode == "contains" and trigger in content_clean)
            )
            if matched:
                # Prefer exact matches, then prefix matches, then substring matches.
                matches.append((priorities[mode], len(trigger), item))

        if not matches:
            return

        now = datetime.now(timezone.utc).timestamp()
        cooldown_key = (message.guild.id, message.author.id)
        if now - self._user_cooldowns.get(cooldown_key, 0.0) < 3.0:
            return

        _, _, matched_reply = max(matches, key=lambda item: (item[0], item[1]))
        formatted = self._format_reply(str(matched_reply.get("reply", "")), message)
        if not formatted.strip():
            return

        try:
            await message.channel.send(
                formatted,
                allowed_mentions=discord.AllowedMentions(
                    everyone=False, roles=False, users=True, replied_user=False
                ),
            )
            self._user_cooldowns[cooldown_key] = now
            await self._record_hit(message.guild.id, str(matched_reply.get("id", "")))
        except discord.Forbidden:
            logger.warning(
                "Auto-responder cannot send in channel %s (guild %s)",
                message.channel.id, message.guild.id
            )
        except discord.HTTPException as exc:
            logger.warning("Auto-responder failed to send: %s", exc)

    # ── Hybrid Custom Reply Group ─────────────────────────────────────────────

    @commands.hybrid_group(name="custom_reply", description="Automated keyword responses and auto-responders", fallback="list", aliases=["autoreply"])
    @commands.guild_only()
    async def custom_reply(self, ctx: commands.Context):
        """List active custom auto-responders in this server."""
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**: Custom Auto-Responders require an active server subscription. Use `/premium_price` to upgrade!", ephemeral=True)

        replies = await self._get_replies(ctx.guild.id)
        limit = await self._get_tier_limit(ctx.guild.id)
        limit_str = "Unlimited" if limit == -1 else str(limit)

        embed = discord.Embed(
            title=f"🤖 Custom Auto-Responders · {ctx.guild.name}",
            description=f"Automated keyword responses active in this server. (Slots: `{len(replies)} / {limit_str}`)",
            color=PREMIUM_COLOR,
            timestamp=datetime.now(timezone.utc),
        )

        if replies:
            lines = []
            for item in replies[:15]:
                trigger = item.get("trigger")
                reply_preview = item.get("reply", "")[:35] + ("…" if len(item.get("reply", "")) > 35 else "")
                mode = item.get("match_mode", "contains")
                hits = item.get("hits", 0)
                lines.append(f"• `{trigger}` (`{mode}`) ➔ *\"{reply_preview}\"* · `⚡ {hits} hits`")
            embed.add_field(name="Active Triggers", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Active Triggers", value="*No auto-responders configured yet. Use `/custom_reply add` to create one!*", inline=False)

        embed.add_field(
            name="💡 Quick Guide",
            value="• Add: `/custom_reply add <trigger> <reply> [mode]`\n• Delete: `/custom_reply delete <trigger>`\n• Test: `/custom_reply test <trigger>`",
            inline=False,
        )
        embed.set_footer(text="Nexora Premium · Smart Server Automation")
        await ctx.send(embed=embed)

    @custom_reply.command(name="add", description="Add a new custom auto-responder")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(
        trigger="The word or phrase that triggers the bot response",
        reply="The response text (supports user, server, channel, IDs, member count, and relative time variables)",
        match_mode="Match type (contains, exact, startswith)",
    )
    @app_commands.choices(match_mode=[
        app_commands.Choice(name="Contains (Anywhere in message)", value="contains"),
        app_commands.Choice(name="Exact Match (Whole message)", value="exact"),
        app_commands.Choice(name="Starts With (Beginning of message)", value="startswith"),
    ])
    async def reply_add(self, ctx: commands.Context, trigger: str, reply: str, match_mode: Optional[str] = "contains"):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.", ephemeral=True)

        limit = await self._get_tier_limit(ctx.guild.id)
        replies = await self._get_replies(ctx.guild.id)

        if limit != -1 and len(replies) >= limit:
            return await ctx.send(f"❌ **Slot Limit Reached**: Your current tier allows up to `{limit}` auto-responders. Use `/premium_price` to upgrade!", ephemeral=True)

        clean_trigger = trigger.casefold().strip()
        clean_reply = reply.strip()
        mode = str(match_mode or "contains").casefold().strip()

        if not clean_trigger or len(clean_trigger) > 100:
            return await ctx.send("Trigger must contain 1–100 characters.", ephemeral=True)
        if not clean_reply or len(clean_reply) > 1800:
            return await ctx.send("Reply must contain 1–1,800 characters.", ephemeral=True)
        if mode not in {"contains", "exact", "startswith"}:
            return await ctx.send("Match mode must be contains, exact, or startswith.", ephemeral=True)

        if any(str(item.get("trigger", "")).casefold().strip() == clean_trigger for item in replies):
            return await ctx.send(f"An auto-responder for {clean_trigger!r} already exists. Delete it first to replace it.", ephemeral=True)

        new_entry = {
            "id": str(uuid.uuid4())[:8],
            "trigger": clean_trigger,
            "reply": clean_reply,
            "match_mode": mode,
            "created_by": ctx.author.id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "hits": 0,
        }
        replies.append(new_entry)
        await self._save_replies(ctx.guild.id, replies)

        embed = discord.Embed(
            title="✅ Auto-Responder Created",
            description=f"When a member's message matches `{clean_trigger}`, Nexora will automatically respond!",
            color=SUCCESS_COLOR,
        )
        embed.add_field(name="Trigger Keyword", value=f"`{clean_trigger}`", inline=True)
        embed.add_field(name="Match Mode", value=f"`{mode}`", inline=True)
        embed.add_field(name="Response Template", value=f"\"{clean_reply}\"", inline=False)
        embed.set_footer(text=f"Slots Remaining: {'Unlimited' if limit == -1 else limit - len(replies) - 1}")
        await ctx.send(embed=embed)

    @custom_reply.command(name="delete", description="Delete an existing custom auto-responder")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(trigger="The trigger keyword to remove")
    async def reply_delete(self, ctx: commands.Context, trigger: str):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.", ephemeral=True)

        clean_trigger = trigger.casefold().strip()
        replies = await self._get_replies(ctx.guild.id)
        updated = [
            item for item in replies
            if str(item.get("trigger", "")).casefold().strip() != clean_trigger
        ]
        if len(updated) == len(replies):
            return await ctx.send(f"No auto-responder found for {clean_trigger!r}.", ephemeral=True)

        await self._save_replies(ctx.guild.id, updated)
        await ctx.send(f"Removed auto-responder for {clean_trigger!r}.")

    @custom_reply.command(name="test", description="Test how an auto-responder formats variables")
    @commands.guild_only()
    @app_commands.describe(trigger="Trigger to test")
    async def reply_test(self, ctx: commands.Context, trigger: str):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("Premium is required to test custom auto-responders.", ephemeral=True)
        if not ctx.author.guild_permissions.manage_guild:
            return await ctx.send("You need Manage Server permission to test auto-responders.", ephemeral=True)

        replies = await self._get_replies(ctx.guild.id)
        clean_trigger = trigger.casefold().strip()
        matched = None
        for r in replies:
            if r.get("trigger") == clean_trigger:
                matched = r
                break

        if not matched:
            return await ctx.send(f"❌ Trigger `{clean_trigger}` not found.", ephemeral=True)

        preview_message = SimpleNamespace(
            author=ctx.author,
            guild=ctx.guild,
            channel=ctx.channel,
            created_at=getattr(ctx.message, "created_at", datetime.now(timezone.utc)),
        )
        formatted = self._format_reply(matched["reply"], preview_message)
        embed = discord.Embed(
            title=f"🧪 Auto-Reply Preview: `{clean_trigger}`",
            description=formatted,
            color=CYAN_COLOR,
        )
        embed.add_field(name="Raw Template", value=f"`{matched['reply']}`", inline=False)
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(AutoResponder(bot))
    logger.debug("Loaded AutoResponder Cog")

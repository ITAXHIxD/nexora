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

import discord
from discord import app_commands
from discord.ext import commands

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
        self._user_cooldowns: Dict[int, float] = {}

    def _get_col(self):
        db = getattr(self.bot, "mongo_db", None)
        return db["premium"] if db is not None else None

    async def _is_premium(self, guild_id: int) -> bool:
        checker = getattr(self.bot, "is_premium_guild", None)
        if checker:
            return await checker(guild_id)
        return False

    async def _get_tier_limit(self, guild_id: int) -> int:
        tier_getter = getattr(self.bot, "get_premium_tier", None)
        tier = await tier_getter(guild_id) if tier_getter else "FREE"
        cfg_getter = getattr(self.bot, "get_tier_config", None)
        cfg = cfg_getter(tier) if cfg_getter else {}
        return cfg.get("features", {}).get("custom_responses", 0)

    async def _get_replies(self, guild_id: int) -> List[dict]:
        col = self._get_col()
        if col is None:
            return []
        doc = await col.find_one({"_id": guild_id})
        if not doc:
            return []
        return doc.get("custom_replies", [])

    def _format_reply(self, template: str, message: discord.Message) -> str:
        text = template
        text = text.replace("{user.mention}", message.author.mention)
        text = text.replace("{user}", message.author.display_name)
        text = text.replace("{server}", message.guild.name)
        text = text.replace("{channel}", message.channel.mention)
        text = text.replace("{members}", str(message.guild.member_count))
        return text

    # ── Listener for Automatic Response ───────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return

        # Avoid triggering on bot command prefix
        prefix = getattr(self.bot, "command_prefix", "n!")
        if isinstance(prefix, str) and message.content.startswith(prefix):
            return

        if not await self._is_premium(message.guild.id):
            return

        replies = await self._get_replies(message.guild.id)
        if not replies:
            return

        # Anti-spam cooldown per user (3 seconds)
        now = datetime.now(timezone.utc).timestamp()
        last_time = self._user_cooldowns.get(message.author.id, 0)
        if now - last_time < 3.0:
            return

        content_clean = message.content.lower().strip()
        matched_reply = None

        for item in replies:
            trigger = item.get("trigger", "").lower().strip()
            mode = item.get("match_mode", "contains")

            if mode == "exact" and content_clean == trigger:
                matched_reply = item
                break
            elif mode == "startswith" and content_clean.startswith(trigger):
                matched_reply = item
                break
            elif mode == "contains" and trigger in content_clean:
                matched_reply = item
                break

        if matched_reply:
            self._user_cooldowns[message.author.id] = now
            formatted_text = self._format_reply(matched_reply["reply"], message)
            try:
                await message.channel.send(formatted_text)
                # Increment hit counter
                col = self._get_col()
                if col:
                    await col.update_one(
                        {"_id": message.guild.id, "custom_replies.id": matched_reply.get("id")},
                        {"$inc": {"custom_replies.$.hits": 1}},
                    )
            except Exception as e:
                logger.debug("Auto-reply dispatch error: %s", e)

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
        reply="The message the bot will send (supports {user}, {server}, {channel}, {members})",
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

        clean_trigger = trigger.lower().strip()
        # Check duplicate
        if any(r.get("trigger", "").lower() == clean_trigger for r in replies):
            return await ctx.send(f"❌ An auto-responder for `{clean_trigger}` already exists! Delete it first if you want to replace it.", ephemeral=True)

        col = self._get_col()
        if col is None:
            return await ctx.send("❌ Database unavailable.", ephemeral=True)

        new_entry = {
            "id": str(uuid.uuid4())[:8],
            "trigger": clean_trigger,
            "reply": reply.strip(),
            "match_mode": match_mode or "contains",
            "created_by": ctx.author.id,
            "created_at": datetime.now(timezone.utc),
            "hits": 0,
        }

        await col.update_one({"_id": ctx.guild.id}, {"$push": {"custom_replies": new_entry}}, upsert=True)

        embed = discord.Embed(
            title="✅ Auto-Responder Created",
            description=f"When a member's message matches `{clean_trigger}`, Nexora will automatically respond!",
            color=SUCCESS_COLOR,
        )
        embed.add_field(name="Trigger Keyword", value=f"`{clean_trigger}`", inline=True)
        embed.add_field(name="Match Mode", value=f"`{match_mode}`", inline=True)
        embed.add_field(name="Response Template", value=f"\"{reply.strip()}\"", inline=False)
        embed.set_footer(text=f"Slots Remaining: {'Unlimited' if limit == -1 else limit - len(replies) - 1}")
        await ctx.send(embed=embed)

    @custom_reply.command(name="delete", description="Delete an existing custom auto-responder")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    @app_commands.describe(trigger="The trigger keyword to remove")
    async def reply_delete(self, ctx: commands.Context, trigger: str):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.", ephemeral=True)

        col = self._get_col()
        if col is None:
            return await ctx.send("❌ Database unavailable.", ephemeral=True)

        clean_trigger = trigger.lower().strip()
        res = await col.update_one(
            {"_id": ctx.guild.id},
            {"$pull": {"custom_replies": {"trigger": clean_trigger}}},
        )
        if res.modified_count == 0:
            return await ctx.send(f"❌ No auto-responder found matching trigger `{clean_trigger}`.", ephemeral=True)

        await ctx.send(f"✅ Removed auto-responder for `{clean_trigger}`.")

    @custom_reply.command(name="test", description="Test how an auto-responder formats variables")
    @commands.guild_only()
    @app_commands.describe(trigger="Trigger to test")
    async def reply_test(self, ctx: commands.Context, trigger: str):
        replies = await self._get_replies(ctx.guild.id)
        clean_trigger = trigger.lower().strip()
        matched = None
        for r in replies:
            if r.get("trigger") == clean_trigger:
                matched = r
                break

        if not matched:
            return await ctx.send(f"❌ Trigger `{clean_trigger}` not found.", ephemeral=True)

        formatted = self._format_reply(matched["reply"], ctx.message)
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

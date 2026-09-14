"""
cogs/utility/remind.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Smart Reminder Engine
Persistent reminders backed by MongoDB with background async worker.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import datetime
import logging
import secrets
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.moderation.mod_utils import fmt_duration, parse_duration
from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)


class RemindersListView(NexoraView):
    """Components V2 view displaying active reminders for a user."""

    def __init__(
        self,
        bot: commands.Bot,
        reminders: list[dict],
        requester: discord.abc.User,
        timeout: float = 180,
    ):
        super().__init__(bot=bot, user_id=requester.id, color=BRAND_COLOR, timeout=timeout)
        self.reminders = reminders
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()

        if not self.reminders:
            self.add_section(
                f"# ⏰ No Active Reminders\n"
                f"> You have no scheduled reminders right now. Use `/remind` to set one!"
            )
            self.add_row(DismissButton(user_id=self.requester.id))
            return

        header = (
            f"# ⏰ Your Scheduled Reminders\n"
            f"> Active Reminders: **{len(self.reminders)}**\n"
            f"-# You can cancel any reminder with `/delreminder <id>`"
        )
        self.add_section(header, thumbnail_url=str(self.requester.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        lines = []
        for r in self.reminders:
            rid = r.get("id", "N/A")
            due_dt = datetime.datetime.fromisoformat(r["due_at"])
            due_str = f"{ts_format(due_dt, 'R')} ({ts_format(due_dt, 't')})"
            reason = r.get("reason", "No note provided.")
            jump = r.get("jump_url")
            jump_str = f" · [Jump]({jump})" if jump else ""
            lines.append(f"• **`#{rid}`** · Due {due_str}{jump_str}\n  > {reason}")

        self.add_text("\n\n".join(lines[:10]))
        if len(lines) > 10:
            self.add_footer(f"(+{len(lines) - 10} more reminders) · Requested by {self.requester.display_name}")
        else:
            self.add_footer(f"Requested by {self.requester.display_name}")

        self.add_row(DismissButton(user_id=self.requester.id))


class Remind(commands.Cog):
    """Smart persistent reminder system."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.col = None
        self.local_reminders: list[dict] = []
        self.check_reminders_task.start()

    async def cog_load(self):
        mongo = getattr(self.bot, "mongo_db", None)
        if mongo is not None:
            self.col = mongo["reminders"]
            logger.info("Remind ready — MongoDB collection 'reminders'")
        else:
            logger.warning("Remind: MongoDB not available, running in-memory fallback")

    def cog_unload(self):
        self.check_reminders_task.cancel()

    # ── Database Operations ───────────────────────────────────────────────────

    async def add_reminder(
        self,
        user_id: int,
        channel_id: int,
        guild_id: Optional[int],
        due_at: datetime.datetime,
        reason: str,
        jump_url: Optional[str] = None,
    ) -> str:
        rid = secrets.token_hex(3).upper()
        now = datetime.datetime.now(datetime.timezone.utc)
        doc = {
            "id": rid,
            "user_id": user_id,
            "channel_id": channel_id,
            "guild_id": guild_id,
            "reason": reason,
            "jump_url": jump_url,
            "created_at": now.isoformat(),
            "due_at": due_at.isoformat(),
        }

        if self.col is not None:
            try:
                await self.col.insert_one(doc)
            except Exception as e:
                logger.warning("Remind: Mongo insert error: %s", e)

        self.local_reminders.append(doc)
        return rid

    async def get_user_reminders(self, user_id: int) -> list[dict]:
        if self.col is not None:
            try:
                cursor = self.col.find({"user_id": user_id}).sort("due_at", 1)
                return [doc async for doc in cursor]
            except Exception as e:
                logger.warning("Remind: Mongo fetch error: %s", e)

        return [r for r in self.local_reminders if r["user_id"] == user_id]

    async def delete_reminder(self, user_id: int, rid: str) -> bool:
        rid_clean = rid.strip().replace("#", "").upper()
        deleted = False

        if self.col is not None:
            try:
                res = await self.col.delete_one({"user_id": user_id, "id": rid_clean})
                deleted = res.deleted_count > 0
            except Exception as e:
                logger.warning("Remind: Mongo delete error: %s", e)

        orig_len = len(self.local_reminders)
        self.local_reminders = [r for r in self.local_reminders if not (r["user_id"] == user_id and r["id"] == rid_clean)]
        if len(self.local_reminders) < orig_len:
            deleted = True

        return deleted

    # ── Background Task ───────────────────────────────────────────────────────

    @tasks.loop(seconds=10)
    async def check_reminders_task(self):
        await self.bot.wait_until_ready()
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now_dt.isoformat()

        due_docs = []
        if self.col is not None:
            try:
                cursor = self.col.find({"due_at": {"$lte": now_iso}})
                due_docs = [doc async for doc in cursor]
            except Exception as e:
                logger.warning("Remind: Mongo query due error: %s", e)
        else:
            due_docs = [r for r in self.local_reminders if r["due_at"] <= now_iso]

        if not due_docs:
            return

        for doc in due_docs:
            rid = doc.get("id")
            user_id = doc.get("user_id")
            channel_id = doc.get("channel_id")
            reason = doc.get("reason", "Reminder!")
            created_dt = datetime.datetime.fromisoformat(doc.get("created_at", now_iso))
            time_ago = fmt_duration(now_dt - created_dt)
            jump_url = doc.get("jump_url")

            # Remove from DB / memory
            if self.col is not None:
                try:
                    await self.col.delete_one({"id": rid})
                except Exception:
                    pass
            self.local_reminders = [r for r in self.local_reminders if r.get("id") != rid]

            # Deliver notification
            user = self.bot.get_user(user_id)
            if not user:
                try:
                    user = await self.bot.fetch_user(user_id)
                except Exception:
                    continue

            dm_view = NexoraView(color=BRAND_COLOR, timeout=300)
            header = (
                f"# ⏰ Reminder Alert\n"
                f"> You asked to be reminded **{time_ago}** ago."
            )
            dm_view.add_section(header, thumbnail_url=str(user.display_avatar.url))
            dm_view.add_separator(discord.SeparatorSpacing.small)
            dm_view.add_text(f"### 📋 Note\n> {reason}")

            row_items = []
            if jump_url:
                row_items.append(discord.ui.Button(label="Jump to Message", url=jump_url, style=discord.ButtonStyle.link, emoji="🔗"))
            row_items.append(DismissButton(user_id=user.id))
            dm_view.add_row(*row_items)

            dm_sent = False
            try:
                await user.send(view=dm_view)
                dm_sent = True
            except (discord.Forbidden, discord.HTTPException):
                pass

            # Fallback to channel ping if DM is closed
            if not dm_sent and channel_id:
                channel = self.bot.get_channel(channel_id)
                if channel and hasattr(channel, "send"):
                    try:
                        await channel.send(
                            f"⏰ {user.mention} **Reminder:** {reason} *(Requested {time_ago} ago)*",
                            view=dm_view,
                        )
                    except Exception:
                        pass

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="remind",
        aliases=["remindme"],
        description="⏰ Set a scheduled reminder with human durations (e.g. 10m, 2h, 1d)",
    )
    @app_commands.describe(
        time="When to remind you (e.g. 10m, 30m, 1h, 12h, 1d, 7d)",
        reason="What you want to be reminded about",
    )
    async def remind(
        self,
        ctx: commands.Context,
        time: str,
        *,
        reason: str,
    ):
        td = parse_duration(time)
        if td is None:
            return await ctx.send(
                "❌ Invalid duration format! Examples: `10m`, `30m`, `1h`, `4h`, `1d`, `7d`",
                ephemeral=True,
            )

        if td.total_seconds() > 365 * 86400:
            return await ctx.send("❌ Reminders cannot be set more than 1 year in advance.", ephemeral=True)

        due_at = datetime.datetime.now(datetime.timezone.utc) + td
        dur_str = fmt_duration(td)
        jump_url = ctx.message.jump_url if ctx.message else None

        rid = await self.add_reminder(
            user_id=ctx.author.id,
            channel_id=ctx.channel.id if ctx.channel else 0,
            guild_id=ctx.guild.id if ctx.guild else None,
            due_at=due_at,
            reason=reason.strip(),
            jump_url=jump_url,
        )

        view = NexoraView(color=SUCCESS_COLOR, timeout=120)
        view.add_section(
            f"# ⏰ Reminder Scheduled · `#{rid}`\n"
            f"> I will remind you in **{dur_str}** ({ts_format(due_at, 'R')}).\n\n"
            f"• **Note:** {reason.strip()}\n"
            f"• **Due:** {ts_format(due_at, 'F')}"
        )
        view.add_footer(f"Nexora Reminders · Cancel anytime with /delreminder {rid}")
        view.add_row(DismissButton(user_id=ctx.author.id))

        await send_view(ctx, view)
        logger.info("Remind: %s set reminder #%s for %s", ctx.author, rid, dur_str)

    @remind.autocomplete("time")
    async def remind_autocomplete(self, interaction: discord.Interaction, current: str):
        presets = [
            ("5 Minutes", "5m"),
            ("10 Minutes", "10m"),
            ("15 Minutes", "15m"),
            ("30 Minutes", "30m"),
            ("1 Hour", "1h"),
            ("2 Hours", "2h"),
            ("4 Hours", "4h"),
            ("8 Hours", "8h"),
            ("1 Day", "1d"),
            ("3 Days", "3d"),
            ("1 Week", "7d"),
        ]
        return [
            app_commands.Choice(name=label, value=val)
            for label, val in presets
            if current.lower() in label.lower() or current.lower() in val.lower()
        ][:25]

    @commands.hybrid_command(
        name="reminders",
        description="📋 View your scheduled active reminders",
    )
    async def reminders(self, ctx: commands.Context):
        user_rems = await self.get_user_reminders(ctx.author.id)
        view = RemindersListView(self.bot, user_rems, ctx.author)
        await send_view(ctx, view)

    @commands.command(
        name="delreminder",
        aliases=["unremind", "cancelreminder"],
        description="🗑️ Cancel a scheduled reminder by ID",
    )
    async def delreminder(self, ctx: commands.Context, id: str):
        success = await self.delete_reminder(ctx.author.id, id)
        if not success:
            return await ctx.send(f"❌ Could not find active reminder `#{id.upper()}` belonging to you.")

        view = NexoraView(color=SUCCESS_COLOR, timeout=60)
        view.add_text(f"# 🗑️ Reminder Cancelled\n> Reminder `#{id.upper()}` was deleted.")
        view.add_footer("Nexora Reminders")
        await send_view(ctx, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Remind(bot))
    logger.debug("Loaded Remind")

"""
cogs/utility/remind.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Smart Reminder Engine
Persistent reminders backed by MongoDB + O(1) in-memory cache with
interactive 1-click cancellation controls.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

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


class ReminderCreatedView(NexoraView):
    """Components V2 card shown when a reminder is created, with a 1-click Cancel button."""

    def __init__(
        self,
        cog: "Remind",
        user_id: int,
        rid: str,
        dur_str: str,
        due_at: datetime.datetime,
        reason: str,
        timeout: float = 180,
    ):
        super().__init__(bot=cog.bot, user_id=user_id, color=SUCCESS_COLOR, timeout=timeout)
        self.cog = cog
        self.rid = rid
        self.dur_str = dur_str
        self.due_at = due_at
        self.reason = reason
        self._cancelled = False
        self._build()

    def _build(self):
        self.clear_container()
        if self._cancelled:
            self.add_section(
                f"# 🗑️ Reminder Cancelled · `#{self.rid}`\n"
                f"> Your scheduled reminder has been cancelled."
            )
            self.add_footer("Nexora Reminders")
            self.add_row(DismissButton(user_id=self.user_id))
            return

        self.add_section(
            f"# ⏰ Reminder Scheduled · `#{self.rid}`\n"
            f"> I will remind you in **{self.dur_str}** ({ts_format(self.due_at, 'R')}).\n\n"
            f"• **Note:** {self.reason}\n"
            f"• **Due:** {ts_format(self.due_at, 'F')}"
        )
        self.add_footer(f"Nexora Reminders · Click 'Cancel Reminder' below or use n!delreminder {self.rid}")

        btn_cancel = discord.ui.Button(
            label="Cancel Reminder",
            emoji="🗑️",
            style=discord.ButtonStyle.danger,
        )
        btn_cancel.callback = self._on_cancel
        self.add_row(btn_cancel, DismissButton(user_id=self.user_id))

    async def _on_cancel(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message(
                "❌ Only the person who set this reminder can cancel it.", ephemeral=True
            )
        await self.cog.delete_reminder(self.user_id, self.rid)
        self._cancelled = True
        self._build()
        await interaction.response.edit_message(view=self)


class RemindersListView(NexoraView):
    """Components V2 view displaying active reminders for a user with interactive cancellation."""

    def __init__(
        self,
        cog: "Remind",
        reminders: list[dict],
        requester: discord.abc.User,
        timeout: float = 180,
    ):
        super().__init__(bot=cog.bot, user_id=requester.id, color=BRAND_COLOR, timeout=timeout)
        self.cog = cog
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
            f"-# Select a reminder from the menu below to cancel it instantly"
        )
        self.add_section(header, thumbnail_url=str(self.requester.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        lines = []
        options = []
        for r in self.reminders[:10]:
            rid = r.get("id", "N/A")
            due_dt = datetime.datetime.fromisoformat(r["due_at"])
            due_str = f"{ts_format(due_dt, 'R')} ({ts_format(due_dt, 't')})"
            reason = r.get("reason", "No note provided.")
            jump = r.get("jump_url")
            jump_str = f" · [Jump]({jump})" if jump else ""
            lines.append(f"• **`#{rid}`** · Due {due_str}{jump_str}\n  > {reason}")
            options.append(
                discord.SelectOption(
                    label=f"Cancel #{rid}",
                    value=str(rid),
                    description=reason[:95],
                    emoji="🗑️",
                )
            )

        self.add_text("\n\n".join(lines))
        if len(self.reminders) > 10:
            self.add_footer(f"(+{len(self.reminders) - 10} more reminders) · Requested by {self.requester.display_name}")
        else:
            self.add_footer(f"Requested by {self.requester.display_name}")

        if options:
            select = discord.ui.Select(
                placeholder="🗑️ Select a reminder to cancel…",
                options=options[:25],
                min_values=1,
                max_values=1,
            )

            async def _on_select(interaction: discord.Interaction):
                if interaction.user.id != self.requester.id:
                    return await interaction.response.send_message(
                        "❌ Only the owner of these reminders can cancel them.", ephemeral=True
                    )
                chosen_id = select.values[0]
                await self.cog.delete_reminder(self.requester.id, chosen_id)
                self.reminders = [r for r in self.reminders if r.get("id") != chosen_id]
                self._build()
                await interaction.response.edit_message(view=self)

            select.callback = _on_select
            self.add_row(select)

        self.add_row(DismissButton(user_id=self.requester.id))


class Remind(commands.Cog):
    """Smart persistent reminder system with O(1) in-memory scheduling cache."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.col = None
        self.local_reminders: list[dict] = []
        self.check_reminders_task.start()

    async def cog_load(self):
        mongo = getattr(self.bot, "mongo_db", None)
        if mongo is not None:
            self.col = mongo["reminders"]
            try:
                self.local_reminders = [doc async for doc in self.col.find({})]
                logger.info("Remind ready — Cached %d reminders from MongoDB", len(self.local_reminders))
            except Exception as e:
                logger.warning("Remind: Could not pre-load reminders from MongoDB: %s", e)
        else:
            logger.warning("Remind: MongoDB not available, running in-memory fallback")

    def cog_unload(self):
        self.check_reminders_task.cancel()

    # ── Database Operations (O(1) Memory Cached) ──────────────────────────────

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

        self.local_reminders.append(doc)
        if self.col is not None:
            try:
                await self.col.insert_one(dict(doc))
            except Exception as e:
                logger.warning("Remind: Mongo insert error: %s", e)

        return rid

    async def get_user_reminders(self, user_id: int) -> list[dict]:
        user_rems = [r for r in self.local_reminders if r.get("user_id") == user_id]
        user_rems.sort(key=lambda r: r.get("due_at", ""))
        return user_rems

    async def delete_reminder(self, user_id: int, rid: str) -> bool:
        rid_clean = rid.strip().replace("#", "").upper()
        deleted = False

        orig_len = len(self.local_reminders)
        self.local_reminders = [
            r for r in self.local_reminders if not (r.get("user_id") == user_id and r.get("id") == rid_clean)
        ]
        if len(self.local_reminders) < orig_len:
            deleted = True

        if self.col is not None:
            try:
                res = await self.col.delete_one({"user_id": user_id, "id": rid_clean})
                if res.deleted_count > 0:
                    deleted = True
            except Exception as e:
                logger.warning("Remind: Mongo delete error: %s", e)

        return deleted

    # ── Background Task (Zero Idle MongoDB Queries) ───────────────────────────

    @tasks.loop(seconds=10)
    async def check_reminders_task(self):
        if not self.local_reminders:
            return

        now_dt = datetime.datetime.now(datetime.timezone.utc)
        now_iso = now_dt.isoformat()

        due_docs = [r for r in self.local_reminders if r.get("due_at", "") <= now_iso]
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

            # Remove from memory & DB
            self.local_reminders = [r for r in self.local_reminders if r.get("id") != rid]
            if self.col is not None:
                try:
                    await self.col.delete_one({"id": rid})
                except Exception:
                    pass

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
                row_items.append(
                    discord.ui.Button(
                        label="Jump to Message",
                        url=jump_url,
                        style=discord.ButtonStyle.link,
                        emoji="🔗",
                    )
                )
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

    @check_reminders_task.before_loop
    async def before_check_reminders(self):
        await self.bot.wait_until_ready()

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

        existing = await self.get_user_reminders(ctx.author.id)
        is_vip = False
        if hasattr(self.bot, "is_premium_user"):
            is_vip = await self.bot.is_premium_user(ctx.author.id)
        max_reminders = 50 if is_vip else 5
        if len(existing) >= max_reminders:
            return await ctx.send(
                f"❌ **Reminder Limit Reached**: You currently have `{len(existing)}/{max_reminders}` scheduled reminders.\n"
                f"{'Use `/reminders` to cancel one.' if is_vip else '⭐ Upgrade to **Nexora VIP** (`/premium_price`) to unlock up to **50** reminders!'}",
                ephemeral=True,
            )

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

        view = ReminderCreatedView(self, ctx.author.id, rid, dur_str, due_at, reason.strip())
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
        description="📋 View and manage your scheduled active reminders",
    )
    async def reminders(self, ctx: commands.Context):
        user_rems = await self.get_user_reminders(ctx.author.id)
        view = RemindersListView(self, user_rems, ctx.author)
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

"""
cogs/moderation/warn.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Infraction & Warning Engine
Persistent warnings backed by MongoDB with in-memory fallback.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import datetime
import logging
import secrets
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.mod_utils import (
    ModActionView,
    ModConfirmLayoutView,
    can_action,
    dm_embed,
    log_mod_action,
    try_dm,
)
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


class WarningsPaginationView(NexoraView):
    """Components V2 paginated warning history view."""

    def __init__(
        self,
        bot: commands.Bot,
        target: discord.Member,
        warnings: list[dict],
        requester: discord.abc.User,
        timeout: float = 180,
    ):
        super().__init__(bot=bot, user_id=requester.id, color=WARNING_COLOR, timeout=timeout)
        self.target = target
        self.warnings = warnings
        self.requester = requester
        self.per_page = 4
        self.current_page = 0
        self.max_pages = max(1, (len(warnings) + self.per_page - 1) // self.per_page)
        self._build()

    def _build(self):
        self.clear_container()

        if not self.warnings:
            self.add_section(
                f"# 🛡️ Clean Record · @{self.target.name}\n"
                f"> {self.target.mention} has no active warnings or infractions in this server."
            )
            self.add_row(DismissButton(user_id=self.requester.id))
            return

        header = (
            f"# ⚠️ Infraction History · @{self.target.name}\n"
            f"> Target: {self.target.mention} (`{self.target.id}`)\n"
            f"> Total Infractions: **{len(self.warnings)}**"
        )
        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        start = self.current_page * self.per_page
        end = start + self.per_page
        page_items = self.warnings[start:end]

        warn_lines = []
        for w in page_items:
            case = w.get("case_id", "N/A")
            dt = datetime.datetime.fromisoformat(w["timestamp"])
            ts_str = ts_format(dt, "R")
            mod_id = w.get("moderator_id")
            mod_mention = f"<@{mod_id}>" if mod_id else "Unknown"
            reason = w.get("reason", "No reason provided.")
            warn_lines.append(
                f"### 📋 Case `#{case}` · {ts_str}\n"
                f"• **Moderator:** {mod_mention}\n"
                f"• **Reason:** {reason}"
            )

        self.add_text("\n\n".join(warn_lines))
        self.add_footer(
            f"Page {self.current_page + 1} of {self.max_pages} · "
            f"Requested by {self.requester.display_name}"
        )

        prev_btn = discord.ui.Button(
            label="Previous",
            emoji="◀️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page == 0),
        )
        prev_btn.callback = self._on_prev

        next_btn = discord.ui.Button(
            label="Next",
            emoji="▶️",
            style=discord.ButtonStyle.secondary,
            disabled=(self.current_page >= self.max_pages - 1),
        )
        next_btn.callback = self._on_next

        dismiss_btn = DismissButton(user_id=self.requester.id)

        if self.max_pages > 1:
            self.add_row(prev_btn, next_btn, dismiss_btn)
        else:
            self.add_row(dismiss_btn)

    async def _on_prev(self, interaction: discord.Interaction):
        if self.current_page > 0:
            self.current_page -= 1
            self._build()
            await interaction.response.edit_message(view=self)

    async def _on_next(self, interaction: discord.Interaction):
        if self.current_page < self.max_pages - 1:
            self.current_page += 1
            self._build()
            await interaction.response.edit_message(view=self)


class Warn(commands.Cog):
    """Warning and infraction management."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.col = None
        self.local_warns: dict[tuple[int, int], list[dict]] = {}  # (guild_id, user_id) -> list of warnings

    async def cog_load(self):
        mongo = getattr(self.bot, "mongo_db", None)
        if mongo is not None:
            self.col = mongo["warnings"]
            logger.info("Warn ready — MongoDB collection 'warnings'")
        else:
            logger.warning("Warn: MongoDB not available, running in-memory fallback")

    # ── Database Helpers ───────────────────────────────────────────────────────

    async def get_warnings(self, guild_id: int, user_id: int) -> list[dict]:
        if self.col is not None:
            try:
                cursor = self.col.find({"guild_id": guild_id, "user_id": user_id}).sort("timestamp", -1)
                return [doc async for doc in cursor]
            except Exception as e:
                logger.warning("Warn: MongoDB fetch error: %s", e)

        return self.local_warns.get((guild_id, user_id), [])

    async def add_warning(self, guild_id: int, user_id: int, moderator_id: int, reason: str) -> str:
        case_id = secrets.token_hex(3).upper()
        doc = {
            "case_id": case_id,
            "guild_id": guild_id,
            "user_id": user_id,
            "moderator_id": moderator_id,
            "reason": reason,
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        if self.col is not None:
            try:
                await self.col.insert_one(doc)
            except Exception as e:
                logger.warning("Warn: MongoDB save error: %s", e)

        key = (guild_id, user_id)
        if key not in self.local_warns:
            self.local_warns[key] = []
        self.local_warns[key].insert(0, doc)

        return case_id

    async def delete_warning(self, guild_id: int, user_id: int, case_id: str) -> bool:
        deleted = False
        if self.col is not None:
            try:
                res = await self.col.delete_one({"guild_id": guild_id, "user_id": user_id, "case_id": case_id.upper()})
                deleted = res.deleted_count > 0
            except Exception as e:
                logger.warning("Warn: MongoDB delete error: %s", e)

        key = (guild_id, user_id)
        if key in self.local_warns:
            orig_len = len(self.local_warns[key])
            self.local_warns[key] = [w for w in self.local_warns[key] if w.get("case_id") != case_id.upper()]
            if len(self.local_warns[key]) < orig_len:
                deleted = True

        return deleted

    async def clear_all_warnings(self, guild_id: int, user_id: int) -> int:
        count = 0
        if self.col is not None:
            try:
                res = await self.col.delete_many({"guild_id": guild_id, "user_id": user_id})
                count = res.deleted_count
            except Exception as e:
                logger.warning("Warn: MongoDB clear error: %s", e)

        key = (guild_id, user_id)
        if key in self.local_warns:
            count = max(count, len(self.local_warns[key]))
            self.local_warns[key] = []

        return count

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="warn",
        description="⚠️ Issue a formal warning to a server member",
    )
    @app_commands.describe(
        member="The member to warn",
        reason="Reason for the warning",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def warn(
        self,
        ctx: commands.Context,
        member: discord.Member,
        *,
        reason: str,
    ):
        err = can_action(ctx.author, member)
        if err:
            return await ctx.send(err, ephemeral=True)

        reason_text = reason.strip()
        case_id = await self.add_warning(ctx.guild.id, member.id, ctx.author.id, reason_text)

        # Dispatch DM warning to member
        dm_view = NexoraView(color=WARNING_COLOR, timeout=180)
        dm_view.add_text(
            f"# ⚠️ Warning Received · {ctx.guild.name}\n"
            f"> You have been officially warned by **{ctx.author.name}**.\n\n"
            f"• **Case ID:** `#{case_id}`\n"
            f"• **Reason:** {reason_text}\n\n"
            f"-# Please review the server guidelines to prevent further moderation actions."
        )
        await try_dm(member, dm_view)

        # Output audit card in channel
        result_view = ModActionView(
            action="warn",
            target=member,
            moderator=ctx.author,
            reason=reason_text,
            extra=f"Infraction Case ID: `#{case_id}`",
        )
        await send_view(ctx, result_view)
        await log_mod_action(
            ctx.guild,
            "warn",
            member,
            ctx.author,
            reason_text,
            extra=f"Infraction Case ID: `#{case_id}`",
            bot=self.bot,
        )
        logger.info("Warn: %s warned %s (Case #%s) | reason: %s", ctx.author, member, case_id, reason_text)

    @commands.hybrid_command(
        name="warnings",
        aliases=["warns", "infractions"],
        description="📋 View warning history and active infractions for a member",
    )
    @app_commands.describe(member="Member to check (leave blank for yourself)")
    @commands.guild_only()
    async def warnings(
        self,
        ctx: commands.Context,
        member: Optional[discord.Member] = None,
    ):
        target = member or ctx.author
        warns = await self.get_warnings(ctx.guild.id, target.id)

        view = WarningsPaginationView(
            bot=self.bot,
            target=target,
            warnings=warns,
            requester=ctx.author,
        )
        await send_view(ctx, view)

    @commands.command(
        name="delwarn",
        description="🗑️ Delete a specific warning by Case ID",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.guild_only()
    async def delwarn(
        self,
        ctx: commands.Context,
        member: discord.Member,
        case_id: str,
    ):
        case_id_clean = case_id.strip().replace("#", "").upper()
        success = await self.delete_warning(ctx.guild.id, member.id, case_id_clean)

        if not success:
            return await ctx.send(f"❌ Could not find warning `#{case_id_clean}` for {member.mention}.", ephemeral=True)

        view = NexoraView(color=SUCCESS_COLOR, timeout=60)
        view.add_text(
            f"# 🗑️ Warning Deleted\n"
            f"> Infraction Case `#{case_id_clean}` for {member.mention} was removed by {ctx.author.mention}."
        )
        view.add_footer("Nexora Moderation Engine")
        await send_view(ctx, view)
        await log_mod_action(
            ctx.guild,
            "delwarn",
            member,
            ctx.author,
            f"Deleted infraction case #{case_id_clean}",
            bot=self.bot,
        )
        logger.info("Delwarn: %s deleted warning #%s for %s", ctx.author, case_id_clean, member)

    @commands.command(
        name="clearwarns",
        description="🧹 Clear all warnings and infractions for a member",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.guild_only()
    async def clearwarns(
        self,
        ctx: commands.Context,
        member: discord.Member,
    ):
        warns = await self.get_warnings(ctx.guild.id, member.id)
        if not warns:
            return await ctx.send(f"❌ {member.mention} has no warnings to clear.", ephemeral=True)

        confirm_view = ModConfirmLayoutView(
            action="clearwarns",
            target=member,
            moderator=ctx.author,
            reason="Clearing all accumulated infractions",
            details=f"This will permanently delete all `{len(warns)}` warning record(s).",
            timeout=30.0,
        )
        msg = await send_view(ctx, confirm_view)
        await confirm_view.wait()

        if not confirm_view.confirmed:
            return

        count = await self.clear_all_warnings(ctx.guild.id, member.id)

        view = NexoraView(color=SUCCESS_COLOR, timeout=60)
        view.add_text(
            f"# 🧹 All Warnings Cleared\n"
            f"> Successfully deleted **{count}** warning(s) for {member.mention}.\n"
            f"🛡️ **Moderator:** {ctx.author.mention}"
        )
        view.add_footer("Nexora Moderation Engine")
        if msg:
            try:
                await msg.edit(view=view)
            except Exception:
                await ctx.send(view=view)
        else:
            await ctx.send(view=view)

        await log_mod_action(
            ctx.guild,
            "delwarn",
            member,
            ctx.author,
            f"Cleared all {count} warning(s)",
            bot=self.bot,
        )
        logger.info("Clearwarns: %s cleared %d warnings for %s", ctx.author, count, member)

    @warn.error
    @delwarn.error
    @clearwarns.error
    async def warn_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need moderation permissions to manage warnings.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Warn(bot))
    logger.debug("Loaded Warn")

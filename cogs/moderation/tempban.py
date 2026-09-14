"""
cogs/moderation/tempban.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Temporary Ban Command with Auto-Unban
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.mod_utils import (
    ModActionView,
    ModConfirmLayoutView,
    can_action,
    dm_embed,
    fmt_duration,
    log_mod_action,
    parse_duration,
    try_dm,
)
from utils.ui import send_view

logger = logging.getLogger(__name__)
MAX_TEMPBAN_DAYS = 365


class TempBan(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._pending: dict = {}

    async def cog_unload(self):
        for task in self._pending.values():
            task.cancel()

    async def _unban_later(self, guild: discord.Guild, user_id: int, seconds: float):
        try:
            await asyncio.sleep(seconds)
            user = await self.bot.fetch_user(user_id)
            await guild.unban(user, reason="Temp-ban duration expired")
            logger.info("Auto-unbanned %s from %s", user, guild.name)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            logger.error("Failed to auto-unban %s in %s: %s", user_id, guild.name, exc)
        finally:
            self._pending.pop((guild.id, user_id), None)

    @commands.hybrid_command(
        name="tempban",
        description="⏱️ Temporarily ban a member — automatically unbanned after duration expires",
    )
    @app_commands.describe(
        member="The member to temp-ban",
        duration="Duration of ban (e.g. 30m, 2h, 1d, 7d)",
        reason="Reason for the ban",
        delete_messages="Days of messages to delete (0–7)",
    )
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def tempban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: str,
        reason: Optional[str] = None,
        delete_messages: int = 0,
    ):
        td = parse_duration(duration)
        if td is None:
            return await ctx.send(
                "❌ Invalid duration. Examples: `30m` `2h` `1d` `1h30m` `7d`",
                ephemeral=True,
            )

        if td.days > MAX_TEMPBAN_DAYS:
            return await ctx.send(
                f"❌ Maximum temp-ban duration is **{MAX_TEMPBAN_DAYS} days**.",
                ephemeral=True,
            )

        err = can_action(ctx.author, member)
        if err:
            return await ctx.send(err, ephemeral=True)

        delete_messages = max(0, min(delete_messages, 7))
        reason_text = reason or "No reason provided."
        dur_str = fmt_duration(td)

        confirm_view = ModConfirmLayoutView(
            action="tempban",
            target=member,
            moderator=ctx.author,
            reason=reason_text,
            details=f"Duration: **{dur_str}** · Messages purge: `{delete_messages}` day(s)",
            timeout=30.0,
        )
        msg = await send_view(ctx, confirm_view)
        await confirm_view.wait()

        if not confirm_view.confirmed:
            return

        await try_dm(member, dm_embed("tempban", ctx.guild, ctx.author, reason_text, duration=td))

        await ctx.guild.ban(
            member,
            reason=f"[{ctx.author}] Tempban ({dur_str}): {reason_text}",
            delete_message_days=delete_messages,
        )

        task = asyncio.create_task(self._unban_later(ctx.guild, member.id, td.total_seconds()))
        self._pending[(ctx.guild.id, member.id)] = task

        result_view = ModActionView(
            action="tempban",
            target=member,
            moderator=ctx.author,
            reason=reason_text,
            duration=td,
            extra=f"Auto-unban scheduled in {dur_str}",
        )
        if msg:
            try:
                await msg.edit(view=result_view)
            except Exception:
                await ctx.send(view=result_view)
        else:
            await ctx.send(view=result_view)

        await log_mod_action(
            ctx.guild,
            "tempban",
            member,
            ctx.author,
            reason_text,
            duration=td,
            extra=f"Auto-unban scheduled in {dur_str}",
            bot=self.bot,
        )
        logger.info("Tempban: %s temp-banned %s for %s | reason: %s", ctx.author, member, dur_str, reason_text)

    @tempban.error
    async def tempban_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need the **Ban Members** permission.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need the **Ban Members** permission.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(TempBan(bot))
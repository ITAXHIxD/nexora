"""
cogs/moderation/tempban.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Command: n!tempban / /tempban

  Bans a member for a specified duration, then automatically
  unbans them when the time expires via a background task.

Duration format: 30m  2h  1d  1h30m  7d  etc.
Maximum: 365 days

Permissions required:
  Bot  → Ban Members
  User → Ban Members
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands, tasks

from cogs.moderation.mod_utils import (
    ConfirmView, can_action, dm_embed, expiry_ts,
    fmt_duration, mod_embed, parse_duration, try_dm,
)

logger = logging.getLogger(__name__)

MAX_TEMPBAN_DAYS = 365


class TempBan(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot      = bot
        # {(guild_id, user_id): asyncio.Task}
        self._pending: dict = {}

    async def cog_unload(self):
        for task in self._pending.values():
            task.cancel()

    # ── /tempban ──────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="tempban",
        description="Temporarily ban a member — they're unbanned automatically when the time expires",
    )
    @app_commands.describe(
        member="The member to temp-ban",
        duration="How long to ban them (e.g. 30m, 2h, 1d, 7d)",
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
        delete_messages: int  = 0,
    ):
        # ── Parse duration ─────────────────────────────────────────────────────
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

        # ── Safety checks ─────────────────────────────────────────────────────
        err = can_action(ctx.author, member)
        if err:
            return await ctx.send(err, ephemeral=True)

        delete_messages = max(0, min(delete_messages, 7))
        reason_text     = reason or "No reason provided."
        dur_str         = fmt_duration(td)

        # ── Confirmation embed ─────────────────────────────────────────────────
        confirm_embed = discord.Embed(
            title="⏱️ Confirm Temp-Ban",
            description=(
                f"Are you sure you want to **temp-ban** {member.mention}?\n\n"
                f"> They will be unbanned automatically after **{dur_str}**.\n\n"
                f"**User:** `{member}` ({member.id})\n"
                f"**Duration:** {dur_str}\n"
                f"**Expires:** {expiry_ts(td)}\n"
                f"**Reason:** {reason_text}\n"
                f"**Messages deleted:** last {delete_messages} day(s)"
            ),
            color=discord.Color.from_rgb(220, 100, 50),
        )
        confirm_embed.set_thumbnail(url=member.display_avatar.url)
        confirm_embed.set_footer(text="This action will expire in 30 seconds if not confirmed.")

        view = ConfirmView(ctx.author.id)
        msg  = await ctx.send(embed=confirm_embed, view=view)
        await view.wait()

        if not view.confirmed:
            cancelled = discord.Embed(
                description="❌ **Temp-ban cancelled.**",
                color=discord.Color.greyple(),
            )
            return await msg.edit(embed=cancelled, view=view)

        # ── DM target before banning ───────────────────────────────────────────
        await try_dm(
            member,
            dm_embed("tempban", ctx.guild, ctx.author, reason_text, duration=td),
        )

        # ── Execute ────────────────────────────────────────────────────────────
        user_id  = member.id
        guild_id = ctx.guild.id

        await ctx.guild.ban(
            member,
            reason=f"[TEMPBAN {dur_str}] [{ctx.author}] {reason_text}",
            delete_message_days=delete_messages,
        )

        # Schedule auto-unban
        key  = (guild_id, user_id)
        task = asyncio.create_task(
            self._schedule_unban(ctx.guild, user_id, td.total_seconds(), reason_text)
        )
        self._pending[key] = task

        result_embed = mod_embed(
            "tempban", member, ctx.author, reason_text,
            duration=td,
            extra=f"Auto-unban scheduled {expiry_ts(td)}",
        )
        await msg.edit(embed=result_embed, view=view)
        logger.info(
            "TempBan: %s temp-banned %s for %s | reason: %s",
            ctx.author, member, dur_str, reason_text,
        )

    # ── Auto-unban task ────────────────────────────────────────────────────────

    async def _schedule_unban(
        self,
        guild: discord.Guild,
        user_id: int,
        seconds: float,
        reason: str,
    ):
        try:
            await asyncio.sleep(seconds)
            user = discord.Object(id=user_id)
            await guild.unban(user, reason=f"[TEMPBAN EXPIRED] {reason}")
            logger.info("TempBan: auto-unbanned %d in guild %d", user_id, guild.id)
        except asyncio.CancelledError:
            pass
        except discord.NotFound:
            pass  # already unbanned manually
        except Exception as e:
            logger.error("TempBan auto-unban failed: %s", e)
        finally:
            self._pending.pop((guild.id, user_id), None)

    # ── Error handler ──────────────────────────────────────────────────────────

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
    logger.info("Loaded TempBan")
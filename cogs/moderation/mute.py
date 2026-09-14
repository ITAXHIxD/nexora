"""
cogs/moderation/mute.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Mute (Timeout) & Unmute Commands
Uses Discord's native member timeouts (up to 28 days).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from datetime import datetime, timedelta, timezone
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
from utils.ui import send_view, ts_format

logger = logging.getLogger(__name__)
MAX_TIMEOUT_DAYS = 28  # Discord API limit for timeouts


class Mute(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="mute",
        description="🔇 Timeout/mute a member in the server for a specified duration",
        aliases=["timeout"],
    )
    @app_commands.describe(
        member="The member to timeout/mute",
        duration="Duration of timeout (e.g. 10m, 1h, 1d, 7d — default: 1h)",
        reason="Reason for timeout",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def mute(
        self,
        ctx: commands.Context,
        member: discord.Member,
        duration: Optional[str] = "1h",
        reason: Optional[str] = None,
    ):
        td = parse_duration(duration or "1h")
        if td is None:
            return await ctx.send(
                "❌ Invalid duration format. Examples: `10m`, `30m`, `1h`, `12h`, `1d`, `7d`",
                ephemeral=True,
            )

        if td.total_seconds() > MAX_TIMEOUT_DAYS * 86400:
            return await ctx.send(
                f"❌ Maximum timeout duration is **{MAX_TIMEOUT_DAYS} days**.",
                ephemeral=True,
            )

        err = can_action(ctx.author, member)
        if err:
            return await ctx.send(err, ephemeral=True)

        reason_text = reason or "No reason provided."
        dur_str = fmt_duration(td)

        details_lines = [f"Target will be timed out for **{dur_str}**."]
        if member.is_timed_out() and member.timed_out_until:
            details_lines.append(f"*(Overwrites current timeout expiring {ts_format(member.timed_out_until, 'R')})*")

        confirm_view = ModConfirmLayoutView(
            action="mute",
            target=member,
            moderator=ctx.author,
            reason=reason_text,
            details=" ".join(details_lines),
            timeout=30.0,
        )
        msg = await send_view(ctx, confirm_view)
        await confirm_view.wait()

        if not confirm_view.confirmed:
            return

        until = datetime.now(timezone.utc) + td

        # ── Execute Timeout First (Safety order) ───────────────────────────────
        try:
            await member.timeout(until, reason=f"[{ctx.author}] {reason_text}")
        except discord.Forbidden:
            return await ctx.send("❌ Discord rejected timeout. My role must be higher than the target's highest role.", ephemeral=True)
        except Exception as e:
            return await ctx.send(f"❌ Failed to apply timeout: `{e}`", ephemeral=True)

        # ── Send DM notification after API success ────────────────────────────
        await try_dm(member, dm_embed("mute", ctx.guild, ctx.author, reason_text, duration=td))

        result_view = ModActionView(
            action="mute",
            target=member,
            moderator=ctx.author,
            reason=reason_text,
            duration=td,
            extra=f"Expires {ts_format(until, 'R')}",
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
            "mute",
            member,
            ctx.author,
            reason_text,
            duration=td,
            bot=self.bot,
        )
        logger.info("Mute: %s timed out %s for %s | reason: %s", ctx.author, member, dur_str, reason_text)

    @mute.autocomplete("duration")
    async def duration_autocomplete(self, interaction: discord.Interaction, current: str):
        presets = [
            ("1 minute", "1m"),
            ("5 minutes", "5m"),
            ("10 minutes", "10m"),
            ("30 minutes", "30m"),
            ("1 hour", "1h"),
            ("6 hours", "6h"),
            ("12 hours", "12h"),
            ("1 day", "1d"),
            ("3 days", "3d"),
            ("7 days", "7d"),
            ("14 days", "14d"),
            ("28 days (Max)", "28d"),
        ]
        return [
            app_commands.Choice(name=f"{label} ({val})", value=val)
            for label, val in presets
            if current.lower() in label.lower() or current.lower() in val.lower()
        ][:25]

    @commands.hybrid_command(
        name="unmute",
        description="🔊 Remove timeout / unmute a member",
        aliases=["untimeout"],
    )
    @app_commands.describe(
        member="The member to unmute",
        reason="Reason for removing the timeout",
    )
    @commands.has_permissions(moderate_members=True)
    @commands.bot_has_permissions(moderate_members=True)
    @commands.guild_only()
    async def unmute(
        self,
        ctx: commands.Context,
        member: discord.Member,
        reason: Optional[str] = None,
    ):
        err = can_action(ctx.author, member)
        if err:
            return await ctx.send(err, ephemeral=True)

        if not member.is_timed_out():
            return await ctx.send(f"❌ {member.mention} is not currently timed out.", ephemeral=True)

        reason_text = reason or "Timeout removed by moderator."
        await member.timeout(None, reason=f"[{ctx.author}] {reason_text}")

        result_view = ModActionView(
            action="unmute",
            target=member,
            moderator=ctx.author,
            reason=reason_text,
        )
        await send_view(ctx, result_view)
        await log_mod_action(
            ctx.guild,
            "unmute",
            member,
            ctx.author,
            reason_text,
            bot=self.bot,
        )
        logger.info("Unmute: %s unmuted %s | reason: %s", ctx.author, member, reason_text)

    @mute.error
    @unmute.error
    async def mute_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need the **Moderate Members (Timeout)** permission.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need the **Moderate Members (Timeout)** permission to manage timeouts.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Mute(bot))
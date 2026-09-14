"""
cogs/moderation/lockdown.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Channel Lockdown & Slowmode Engine
Fast channel permission overrides and slowmode configuration.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.mod_utils import fmt_duration, log_mod_action, parse_duration
from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)


class Lockdown(commands.Cog):
    """Channel lockdown and slowmode commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Channel Lock ──────────────────────────────────────────────────────────
    @commands.hybrid_command(
        name="lock",
        description="🔒 Lock down a channel, preventing members from sending messages",
    )
    @app_commands.describe(
        channel="Channel to lock (defaults to current channel)",
        reason="Reason for locking the channel",
    )
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def lock(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
        *,
        reason: Optional[str] = "No reason provided.",
    ):
        target_channel = channel or ctx.channel
        everyone_role = ctx.guild.default_role
        current_perms = target_channel.overwrites_for(everyone_role)

        if current_perms.send_messages is False:
            return await ctx.send(f"⚠️ {target_channel.mention} is already locked!", ephemeral=True)

        current_perms.send_messages = False
        audit_reason = f"[Lock by {ctx.author}] {reason}"
        await target_channel.set_permissions(everyone_role, overwrite=current_perms, reason=audit_reason)

        view = NexoraView(color=ERROR_COLOR, timeout=300)
        view.add_section(
            f"# 🔒 Channel Locked · #{target_channel.name}\n"
            f"> This channel has been locked by {ctx.author.mention}.\n\n"
            f"• **Reason:** {reason}\n\n"
            f"-# Standard members cannot send messages until unlocked by staff."
        )
        view.add_footer("Nexora Security & Lockdown Engine")
        view.add_row(DismissButton(user_id=ctx.author.id, label="Dismiss Alert"))

        await target_channel.send(view=view)
        if target_channel != ctx.channel:
            await ctx.send(f"✅ Successfully locked {target_channel.mention}.", ephemeral=True)

        await log_mod_action(
            ctx.guild,
            "lock",
            target_channel,
            ctx.author,
            reason,
            bot=self.bot,
        )
        logger.info("Lock: %s locked #%s | reason: %s", ctx.author, target_channel.name, reason)

    # ── Channel Unlock ────────────────────────────────────────────────────────
    @commands.hybrid_command(
        name="unlock",
        description="🔓 Unlock a locked channel, restoring regular chatting permissions",
    )
    @app_commands.describe(
        channel="Channel to unlock (defaults to current channel)",
        reason="Reason for unlocking the channel",
    )
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def unlock(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
        *,
        reason: Optional[str] = "No reason provided.",
    ):
        target_channel = channel or ctx.channel
        everyone_role = ctx.guild.default_role
        current_perms = target_channel.overwrites_for(everyone_role)

        if current_perms.send_messages is not False:
            return await ctx.send(f"⚠️ {target_channel.mention} is not currently locked.", ephemeral=True)

        # Reset send_messages to neutral (inherits category/default)
        current_perms.send_messages = None
        audit_reason = f"[Unlock by {ctx.author}] {reason}"
        await target_channel.set_permissions(everyone_role, overwrite=current_perms, reason=audit_reason)

        view = NexoraView(color=SUCCESS_COLOR, timeout=180)
        view.add_section(
            f"# 🔓 Channel Unlocked · #{target_channel.name}\n"
            f"> Normal messaging permissions have been restored by {ctx.author.mention}.\n\n"
            f"• **Reason:** {reason}"
        )
        view.add_footer("Nexora Security & Lockdown Engine")
        view.add_row(DismissButton(user_id=ctx.author.id))

        await target_channel.send(view=view)
        if target_channel != ctx.channel:
            await ctx.send(f"✅ Successfully unlocked {target_channel.mention}.", ephemeral=True)

        await log_mod_action(
            ctx.guild,
            "unlock",
            target_channel,
            ctx.author,
            reason,
            bot=self.bot,
        )
        logger.info("Unlock: %s unlocked #%s | reason: %s", ctx.author, target_channel.name, reason)

    # ── Slowmode ──────────────────────────────────────────────────────────────
    @commands.hybrid_command(
        name="slowmode",
        description="🐢 Configure channel slowmode delay (e.g. 5s, 30s, 1m, 1h, off)",
    )
    @app_commands.describe(
        duration="Slowmode delay (e.g. 5s, 10s, 30s, 1m, 1h, or off / 0)",
        channel="Channel to configure (defaults to current channel)",
    )
    @commands.has_permissions(manage_channels=True)
    @commands.bot_has_permissions(manage_channels=True)
    @commands.guild_only()
    async def slowmode(
        self,
        ctx: commands.Context,
        duration: str,
        channel: Optional[discord.TextChannel] = None,
    ):
        target_channel = channel or ctx.channel
        clean_dur = duration.strip().lower()

        if clean_dur in ("off", "0", "0s", "none", "disable", "reset"):
            seconds = 0
        else:
            td = parse_duration(clean_dur)
            if td is None:
                return await ctx.send(
                    "❌ Invalid duration format. Examples: `5s`, `15s`, `1m`, `5m`, `1h`, `off`",
                    ephemeral=True,
                )
            seconds = int(td.total_seconds())

        # Discord limit: 0 to 21600 seconds (6 hours)
        if seconds > 21600:
            return await ctx.send("❌ Discord slowmode cannot exceed **6 hours (21600s)**.", ephemeral=True)

        audit_reason = f"[Slowmode by {ctx.author}]"
        await target_channel.edit(slowmode_delay=seconds, reason=audit_reason)

        view = NexoraView(color=BRAND_COLOR if seconds > 0 else SUCCESS_COLOR, timeout=120)
        if seconds == 0:
            view.add_section(
                f"# 🚀 Slowmode Disabled · #{target_channel.name}\n"
                f"> Slowmode delay was turned off by {ctx.author.mention}. Messages can be sent without cooldown."
            )
        else:
            view.add_section(
                f"# 🐢 Slowmode Enabled · #{target_channel.name}\n"
                f"> Delay configured to **{clean_dur}** (`{seconds}` seconds) by {ctx.author.mention}."
            )
        view.add_footer("Nexora Moderation Engine")
        view.add_row(DismissButton(user_id=ctx.author.id))

        await send_view(ctx, view)
        await log_mod_action(
            ctx.guild,
            "slowmode",
            target_channel,
            ctx.author,
            f"Configured slowmode delay to {dur_display}",
            bot=self.bot,
        )
        logger.info("Slowmode: %s set slowmode to %ds in #%s", ctx.author, seconds, target_channel.name)

    @slowmode.autocomplete("duration")
    async def slowmode_autocomplete(self, interaction: discord.Interaction, current: str):
        options = [
            ("Disable / Off", "off"),
            ("5 Seconds", "5s"),
            ("10 Seconds", "10s"),
            ("15 Seconds", "15s"),
            ("30 Seconds", "30s"),
            ("1 Minute", "1m"),
            ("2 Minutes", "2m"),
            ("5 Minutes", "5m"),
            ("10 Minutes", "10m"),
            ("15 Minutes", "15m"),
            ("30 Minutes", "30m"),
            ("1 Hour", "1h"),
            ("2 Hours", "2h"),
            ("6 Hours (Max)", "6h"),
        ]
        return [
            app_commands.Choice(name=label, value=val)
            for label, val in options
            if current.lower() in label.lower() or current.lower() in val.lower()
        ][:25]

    @lock.error
    @unlock.error
    @slowmode.error
    async def lockdown_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need the **Manage Channels** permission to use this command.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need the **Manage Channels** permission to perform this action.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Lockdown(bot))
    logger.debug("Loaded Lockdown")

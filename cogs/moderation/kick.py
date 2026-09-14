"""
cogs/moderation/kick.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Kick Command
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from typing import Optional

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
from utils.ui import send_view

logger = logging.getLogger(__name__)


class Kick(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="kick",
        description="👢 Kick a member from the server (removes them, but they may rejoin with an invite)",
    )
    @app_commands.describe(
        member="The member to kick",
        reason="Reason for the kick (shown in audit log and DM)",
    )
    @commands.has_permissions(kick_members=True)
    @commands.bot_has_permissions(kick_members=True)
    @commands.guild_only()
    async def kick(
        self,
        ctx: commands.Context,
        member: discord.Member,
        reason: Optional[str] = None,
    ):
        # ── Hierarchy / Safety checks ─────────────────────────────────────────
        err = can_action(ctx.author, member)
        if err:
            return await ctx.send(err, ephemeral=True)

        reason_text = reason or "No reason provided."
        details_text = "Target can rejoin if provided with an invite link."

        # ── Interactive Components V2 Confirmation ─────────────────────────────
        confirm_view = ModConfirmLayoutView(
            action="kick",
            target=member,
            moderator=ctx.author,
            reason=reason_text,
            details=details_text,
            timeout=30.0,
        )
        msg = await send_view(ctx, confirm_view)
        await confirm_view.wait()

        if not confirm_view.confirmed:
            return

        # ── DM target before kicking ───────────────────────────────────────────
        await try_dm(member, dm_embed("kick", ctx.guild, ctx.author, reason_text))

        # ── Execute Kick ───────────────────────────────────────────────────────
        await member.kick(reason=f"[{ctx.author}] {reason_text}")

        result_view = ModActionView(
            action="kick",
            target=member,
            moderator=ctx.author,
            reason=reason_text,
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
            "kick",
            member,
            ctx.author,
            reason_text,
            bot=self.bot,
        )
        logger.info("Kick: %s kicked %s | reason: %s", ctx.author, member, reason_text)

    @kick.error
    async def kick_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need the **Kick Members** permission.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need the **Kick Members** permission.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found. Try mentioning them or using their ID.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Kick(bot))
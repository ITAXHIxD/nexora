"""
cogs/moderation/ban.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Moderation: Ban, Hackban, Unban & Softban
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
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
from utils.ui import send_view

logger = logging.getLogger(__name__)


class Ban(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── Universal Ban / Hackban ───────────────────────────────────────────────
    @commands.hybrid_command(
        name="ban",
        description="🔨 Ban a member or user ID from the server with audit confirmation",
    )
    @app_commands.describe(
        user="The member or user ID to ban (can ban users who left)",
        reason="Reason for the ban (shown in audit log and DM)",
        delete_messages="How many days of messages to delete (0–7)",
    )
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(
        self,
        ctx: commands.Context,
        user: Union[discord.Member, discord.User],
        reason: Optional[str] = None,
        delete_messages: int = 0,
    ):
        # ── Hierarchy / Safety checks ─────────────────────────────────────────
        err = can_action(ctx.author, user)
        if err:
            return await ctx.send(err, ephemeral=True)

        delete_days = max(0, min(delete_messages, 7))
        delete_seconds = delete_days * 86400
        reason_text = reason or "No reason provided."
        details_text = f"Clearing last `{delete_days}` day(s) of messages."

        # ── Interactive Components V2 Confirmation ─────────────────────────────
        confirm_view = ModConfirmLayoutView(
            action="ban",
            target=user,
            moderator=ctx.author,
            reason=reason_text,
            details=details_text,
            timeout=30.0,
        )
        msg = await send_view(ctx, confirm_view)
        await confirm_view.wait()

        if not confirm_view.confirmed:
            return

        # ── Try DMing target before banning (only works if still in mutual server / open DMs)
        if isinstance(user, discord.Member):
            await try_dm(user, dm_embed("ban", ctx.guild, ctx.author, reason_text))

        # ── Execute Ban ────────────────────────────────────────────────────────
        audit_reason = f"[{ctx.author}] {reason_text}"
        await ctx.guild.ban(
            user,
            reason=audit_reason,
            delete_message_seconds=delete_seconds,
        )

        result_view = ModActionView(
            action="ban",
            target=user,
            moderator=ctx.author,
            reason=reason_text,
            extra=f"Purged {delete_days} day(s) of messages" if delete_days > 0 else None,
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
            "ban",
            user,
            ctx.author,
            reason_text,
            extra=f"Purged {delete_days} day(s) of messages" if delete_days > 0 else None,
            bot=self.bot,
        )
        logger.info("Ban: %s banned %s | reason: %s", ctx.author, user, reason_text)

    # ── Unban ─────────────────────────────────────────────────────────────────
    @commands.hybrid_command(
        name="unban",
        description="🔓 Lift a ban for a user by ID or tag",
    )
    @app_commands.describe(
        user="The user or ID to unban",
        reason="Reason for the unban",
    )
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def unban(
        self,
        ctx: commands.Context,
        user: discord.User,
        reason: Optional[str] = None,
    ):
        reason_text = reason or "No reason provided."
        audit_reason = f"[{ctx.author}] {reason_text}"

        try:
            await ctx.guild.unban(user, reason=audit_reason)
        except discord.NotFound:
            return await ctx.send(f"❌ User **{user}** is not banned in this server.", ephemeral=True)
        except Exception as e:
            return await ctx.send(f"❌ Failed to unban {user}: `{e}`", ephemeral=True)

        result_view = ModActionView(
            action="unban",
            target=user,
            moderator=ctx.author,
            reason=reason_text,
        )
        await send_view(ctx, result_view)
        await log_mod_action(
            ctx.guild,
            "unban",
            user,
            ctx.author,
            reason_text,
            bot=self.bot,
        )
        logger.info("Unban: %s unbanned %s | reason: %s", ctx.author, user, reason_text)

    # ── Softban ───────────────────────────────────────────────────────────────
    @commands.hybrid_command(
        name="softban",
        description="🧹 Softban a member (bans and immediately unbans to purge their messages)",
    )
    @app_commands.describe(
        member="The member to softban",
        reason="Reason for the softban",
        delete_messages="How many days of messages to delete (1–7, defaults to 1)",
    )
    @commands.has_permissions(ban_members=True, kick_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def softban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        reason: Optional[str] = None,
        delete_messages: int = 1,
    ):
        # ── Hierarchy / Safety checks ─────────────────────────────────────────
        err = can_action(ctx.author, member)
        if err:
            return await ctx.send(err, ephemeral=True)

        delete_days = max(1, min(delete_messages, 7))
        delete_seconds = delete_days * 86400
        reason_text = reason or "No reason provided."
        details_text = f"Purges messages from the last `{delete_days}` day(s) and re-allows joining."

        # ── Interactive Components V2 Confirmation ─────────────────────────────
        confirm_view = ModConfirmLayoutView(
            action="softban",
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

        # ── Try DMing target before banning ───────────────────────────────────
        await try_dm(member, dm_embed("softban", ctx.guild, ctx.author, reason_text))

        result_view = ModActionView(
            action="softban",
            target=member,
            moderator=ctx.author,
            reason=reason_text,
            extra=f"Purged {delete_days} day(s) of messages and kicked",
        )
        if msg:
            try:
                await msg.edit(view=result_view)
            except Exception:
                await ctx.send(view=result_view)
        else:
            await ctx.send(view=result_view)

        logger.info("Softban: %s softbanned %s | reason: %s", ctx.author, member, reason_text)

    # ── Error handler ─────────────────────────────────────────────────────────
    @ban.error
    @unban.error
    @softban.error
    async def ban_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You do not have permission to use this command.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need the **Ban Members** permission to execute this.", ephemeral=True)
        elif isinstance(error, (commands.MemberNotFound, commands.UserNotFound)):
            await ctx.send("❌ User not found. Try mentioning them or using their User ID.", ephemeral=True)
        elif isinstance(error, commands.BadUnionArgument):
            await ctx.send("❌ Invalid user specified. Please provide a mention or valid user ID.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Ban(bot))
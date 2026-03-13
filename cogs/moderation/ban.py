"""
cogs/moderation/ban.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Command: n!ban / /ban

  Permanently bans a member from the server.
  Shows a confirmation embed before acting.
  DMs the target before banning.

Permissions required:
  Bot  → Ban Members
  User → Ban Members
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.mod_utils import (
    ConfirmView, can_action, dm_embed, mod_embed, try_dm,
)

logger = logging.getLogger(__name__)


class Ban(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /ban ──────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="ban", description="Permanently ban a member from the server")
    @app_commands.describe(
        member="The member to ban",
        reason="Reason for the ban (shown in audit log and DM)",
        delete_messages="How many days of messages to delete (0–7)",
    )
    @commands.has_permissions(ban_members=True)
    @commands.bot_has_permissions(ban_members=True)
    @commands.guild_only()
    async def ban(
        self,
        ctx: commands.Context,
        member: discord.Member,
        reason: Optional[str] = None,
        delete_messages: int  = 0,
    ):
        # ── Safety checks ─────────────────────────────────────────────────────
        err = can_action(ctx.author, member)
        if err:
            return await ctx.send(err, ephemeral=True)

        delete_messages = max(0, min(delete_messages, 7))
        reason_text     = reason or "No reason provided."

        # ── Confirmation embed ─────────────────────────────────────────────────
        confirm_embed = discord.Embed(
            title="🔨 Confirm Ban",
            description=(
                f"Are you sure you want to **permanently ban** {member.mention}?\n\n"
                f"> This will remove them from the server and prevent them from rejoining.\n\n"
                f"**User:** `{member}` ({member.id})\n"
                f"**Reason:** {reason_text}\n"
                f"**Messages deleted:** last {delete_messages} day(s)"
            ),
            color=discord.Color.from_rgb(220, 50, 50),
        )
        confirm_embed.set_thumbnail(url=member.display_avatar.url)
        confirm_embed.set_footer(text="This action will expire in 30 seconds if not confirmed.")

        view = ConfirmView(ctx.author.id)
        msg  = await ctx.send(embed=confirm_embed, view=view)
        await view.wait()

        if not view.confirmed:
            cancelled = discord.Embed(
                description="❌ **Ban cancelled.**",
                color=discord.Color.greyple(),
            )
            return await msg.edit(embed=cancelled, view=view)

        # ── DM target before banning ───────────────────────────────────────────
        await try_dm(member, dm_embed("ban", ctx.guild, ctx.author, reason_text))

        # ── Execute ────────────────────────────────────────────────────────────
        await ctx.guild.ban(
            member,
            reason=f"[{ctx.author}] {reason_text}",
            delete_message_days=delete_messages,
        )

        result_embed = mod_embed("ban", member, ctx.author, reason_text)
        await msg.edit(embed=result_embed, view=view)
        logger.info("Ban: %s banned %s | reason: %s", ctx.author, member, reason_text)

    # ── Error handler ──────────────────────────────────────────────────────────

    @ban.error
    async def ban_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need the **Ban Members** permission.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need the **Ban Members** permission.", ephemeral=True)
        elif isinstance(error, commands.MemberNotFound):
            await ctx.send("❌ Member not found. Try mentioning them or using their ID.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Ban(bot))
    logger.info("Loaded Ban")
"""
cogs/moderation/kick.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Command: n!kick / /kick

  Kicks a member from the server (they can rejoin).
  Shows a clear confirmation embed — prevents accidental
  kicks when people meant to use n!kicks (the fun gif command).

Permissions required:
  Bot  → Kick Members
  User → Kick Members
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


class Kick(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    # ── /kick ─────────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="kick", description="Kick a member from the server (they can rejoin)")
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
        # ── Safety checks ─────────────────────────────────────────────────────
        err = can_action(ctx.author, member)
        if err:
            return await ctx.send(err, ephemeral=True)

        reason_text = reason or "No reason provided."

        # ── Confirmation embed ─────────────────────────────────────────────────
        # Extra note clarifying this is the MOD kick, not n!kicks (gif command)
        confirm_embed = discord.Embed(
            title="👢 Confirm Kick",
            description=(
                f"Are you sure you want to **kick** {member.mention}?\n\n"
                f"> They will be removed from the server but **can rejoin** with an invite.\n\n"
                f"**User:** `{member}` ({member.id})\n"
                f"**Reason:** {reason_text}\n\n"
                f"⚠️ **Looking for the gif command?** Use `n!kicks` instead.\n"
                f"This is the **moderation kick** — it removes the user from the server."
            ),
            color=discord.Color.from_rgb(220, 160, 50),
        )
        confirm_embed.set_thumbnail(url=member.display_avatar.url)
        confirm_embed.set_footer(text="This action will expire in 30 seconds if not confirmed.")

        view = ConfirmView(ctx.author.id)
        msg  = await ctx.send(embed=confirm_embed, view=view)
        await view.wait()

        if not view.confirmed:
            cancelled = discord.Embed(
                description="❌ **Kick cancelled.**",
                color=discord.Color.greyple(),
            )
            return await msg.edit(embed=cancelled, view=view)

        # ── DM target before kicking ───────────────────────────────────────────
        await try_dm(member, dm_embed("kick", ctx.guild, ctx.author, reason_text))

        # ── Execute ────────────────────────────────────────────────────────────
        await member.kick(reason=f"[{ctx.author}] {reason_text}")

        result_embed = mod_embed("kick", member, ctx.author, reason_text)
        await msg.edit(embed=result_embed, view=view)
        logger.info("Kick: %s kicked %s | reason: %s", ctx.author, member, reason_text)

    # ── Error handler ──────────────────────────────────────────────────────────

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
    logger.info("Loaded Kick")
"""
cogs/moderation/purge.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 High-Performance Purge Engine
Fast multi-filter message deletion with auto-dismissing confirmation.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import datetime
import logging
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.mod_utils import log_mod_action
from utils.ui import (
    CYAN_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)
URL_REGEX = re.compile(r"https?://[^\s]+", re.IGNORECASE)


class PurgeResultView(NexoraView):
    """Components V2 auto-dismissing purge summary card."""

    def __init__(
        self,
        deleted_count: int,
        channel: discord.TextChannel,
        moderator: discord.abc.User,
        filters_applied: list[str],
        timeout: float = 15.0,
    ):
        super().__init__(user_id=moderator.id, color=CYAN_COLOR, timeout=timeout)
        self.deleted_count = deleted_count
        self.channel = channel
        self.moderator = moderator
        self.filters_applied = filters_applied
        self._build()

    def _build(self):
        self.clear_container()
        header = (
            f"# 🧹 Purge Completed · #{self.channel.name}\n"
            f"> Successfully purged **{self.deleted_count}** message(s)\n"
            f"🛡️ **Moderator:** {self.moderator.mention}"
        )
        self.add_section(header)
        self.add_separator(discord.SeparatorSpacing.small)

        filter_desc = ", ".join(self.filters_applied) if self.filters_applied else "None (All messages)"
        details = (
            f"• **Channel:** {self.channel.mention}\n"
            f"• **Messages Deleted:** `{self.deleted_count}`\n"
            f"• **Filters Applied:** `{filter_desc}`\n\n"
            f"-# ⏱️ *This notification will automatically vanish in 5 seconds.*"
        )
        self.add_text(details)
        self.add_row(DismissButton(user_id=self.moderator.id, label="Dismiss Now"))


class Purge(commands.Cog):
    """Message cleanup and purge engine."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="purge",
        aliases=["clear", "clean"],
        description="🧹 Bulk delete messages with advanced filters and auto-clean card",
    )
    @app_commands.describe(
        amount="Number of messages to scan/delete (1–1000, default: 10)",
        user="Only delete messages from this member",
        bots="Only delete messages sent by bots",
        contains="Only delete messages containing this text",
        links="Only delete messages containing web links",
        attachments="Only delete messages containing file/media attachments",
        pinned="Delete pinned messages too (default: False)",
    )
    @commands.has_permissions(manage_messages=True)
    @commands.bot_has_permissions(manage_messages=True, read_message_history=True)
    @commands.guild_only()
    async def purge(
        self,
        ctx: commands.Context,
        amount: int = 10,
        user: Optional[discord.Member] = None,
        bots: Optional[bool] = False,
        contains: Optional[str] = None,
        links: Optional[bool] = False,
        attachments: Optional[bool] = False,
        pinned: Optional[bool] = False,
    ):
        if amount < 1:
            return await ctx.send("❌ Please specify an amount greater than 0.", ephemeral=True)

        # Cap scan to 1000
        scan_limit = min(amount, 1000)

        # Defer interaction if slash
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)

        filters_applied = []
        if user:
            filters_applied.append(f"User: @{user.name}")
        if bots:
            filters_applied.append("Bots Only")
        if contains:
            filters_applied.append(f"Contains: '{contains}'")
        if links:
            filters_applied.append("Links Only")
        if attachments:
            filters_applied.append("Attachments Only")
        if pinned:
            filters_applied.append("Include Pinned")

        cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=14)

        def check(msg: discord.Message) -> bool:
            # Cannot bulk delete messages older than 14 days in Discord
            if msg.created_at < cutoff:
                return False
            # Preserve pinned messages unless explicitly requested
            if not pinned and msg.pinned:
                return False
            if user and msg.author.id != user.id:
                return False
            if bots and not msg.author.bot:
                return False
            if contains and contains.lower() not in msg.content.lower():
                return False
            if links and not URL_REGEX.search(msg.content):
                return False
            if attachments and not (msg.attachments or msg.embeds):
                return False
            return True

        # If prefix command, delete caller message first
        if not ctx.interaction and ctx.message:
            try:
                await ctx.message.delete()
            except Exception:
                pass

        deleted_messages = []
        try:
            # Delete in chunks
            deleted_messages = await ctx.channel.purge(
                limit=scan_limit,
                check=check,
                bulk=True,
            )
        except discord.Forbidden:
            return await ctx.send("❌ I lack permission to delete messages in this channel.", ephemeral=True)
        except discord.HTTPException as e:
            return await ctx.send(f"❌ Discord API error during purge: `{e}`", ephemeral=True)

        count = len(deleted_messages)
        view = PurgeResultView(
            deleted_count=count,
            channel=ctx.channel,
            moderator=ctx.author,
            filters_applied=filters_applied,
            timeout=10.0,
        )

        resp_msg = await send_view(ctx, view, ephemeral=False)

        await log_mod_action(
            ctx.guild,
            "purge",
            ctx.channel,
            ctx.author,
            f"Purged {count} message(s)",
            extra=f"Filters: {', '.join(filters_applied) if filters_applied else 'None (All messages)'}",
            bot=self.bot,
        )

        # Self-destruct feedback card after 5 seconds to keep chat spotless
        await asyncio.sleep(5)
        try:
            if resp_msg:
                await resp_msg.delete()
            elif view.message:
                await view.message.delete()
        except Exception:
            pass

    @purge.error
    async def purge_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingPermissions):
            await ctx.send("❌ You need the **Manage Messages** permission to purge messages.", ephemeral=True)
        elif isinstance(error, commands.BotMissingPermissions):
            await ctx.send("❌ I need the **Manage Messages** permission to purge messages.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Purge(bot))
    logger.debug("Loaded Purge")

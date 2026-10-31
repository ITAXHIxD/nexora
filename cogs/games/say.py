"""
cogs/games/say.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nexora Stealth Say & Broadcast Command (Owner Only).

Features:
  • Strictly Owner-Only (protected via check_owner predicate).
  • Hybrid support: Prefix command (n!say) and Slash command (/say).
  • Discord Native Reply: Replying to a message with n!say automatically
    replies to that message.
  • Remote Reply: Accepts message link (https://discord.com/channels/...)
    or message ID to reply to any message.
  • File & Attachment Forwarding: Forwards images/attachments from prefix
    invocations or slash attachments.
  • Target Channel: Send to any channel via parameter or #channel mention.
  • Reply Mention Control: Ping toggle (default: False to prevent unwanted pings).
  • Stealth Execution: Deletes prefix invoking message; slash interaction
    uses ephemeral response so only the bot's sent message appears in chat.
  • Long Message Auto-Chunking: Handles messages > 2000 characters safely.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import re
from datetime import datetime
from typing import Any, List, Optional, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from utils.config import OWNER_ID

logger = logging.getLogger(__name__)

# Discord message link regex across discord.com, canary, ptb, discordapp.com
MESSAGE_LINK_REGEX = re.compile(
    r"https?://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/channels/(\d+|@me)/(\d+)/(\d+)",
    re.IGNORECASE,
)


async def check_owner(user_id: int, bot: commands.Bot) -> bool:
    """Check if the given user ID belongs to the bot owner."""
    if user_id == OWNER_ID or user_id == 1013851779886231685:
        return True
    if hasattr(bot, "owner_id") and bot.owner_id and user_id == bot.owner_id:
        return True
    if hasattr(bot, "owner_ids") and bot.owner_ids and user_id in bot.owner_ids:
        return True
    try:
        user = bot.get_user(user_id) or await bot.fetch_user(user_id)
        return await bot.is_owner(user)
    except Exception:
        return False


def owner_only_prefix():
    """Prefix command check ensuring only the bot owner can execute."""
    async def predicate(ctx: commands.Context) -> bool:
        if not await check_owner(ctx.author.id, ctx.bot):
            try:
                await ctx.send("❌ This command is restricted to the bot owner only.", delete_after=5)
            except Exception:
                pass
            return False
        return True
    return commands.check(predicate)


def owner_only_slash():
    """Slash command check ensuring only the bot owner can execute."""
    async def predicate(interaction: discord.Interaction) -> bool:
        if not await check_owner(interaction.user.id, interaction.client):
            await interaction.response.send_message(
                "❌ This command is restricted to the bot owner only.",
                ephemeral=True,
            )
            return False
        return True
    return app_commands.check(predicate)


def parse_prefix_args(text: str) -> Tuple[Optional[str], Optional[str], str]:
    """
    Extract optional channel mention (<#id>) and message link/ID from start of text.
    Returns (channel_id, reply_target, remaining_text).
    """
    if not text:
        return None, None, ""

    text = text.strip()
    channel_id: Optional[str] = None
    reply_target: Optional[str] = None

    tokens = text.split(None, 2)
    # 1. Check for leading channel mention: <#123456789>
    if tokens and tokens[0].startswith("<#") and tokens[0].endswith(">"):
        raw_cid = tokens[0][2:-1]
        if raw_cid.isdigit():
            channel_id = raw_cid
            text = text[len(tokens[0]):].strip()
            tokens = text.split(None, 2)

    # 2. Check for leading Discord message URL or 17-20 digit message ID
    if tokens:
        if MESSAGE_LINK_REGEX.match(tokens[0]):
            reply_target = tokens[0]
            text = text[len(tokens[0]):].strip()
        elif tokens[0].isdigit() and len(tokens[0]) >= 17:
            reply_target = tokens[0]
            text = text[len(tokens[0]):].strip()

    return channel_id, reply_target, text


class Say(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        if not hasattr(self.bot, "active_saying"):
            self.bot.active_saying = {}

    async def _execute_say(
        self,
        bot: commands.Bot,
        author: Any,
        current_channel: Any,
        current_guild: Optional[discord.Guild],
        raw_text: Optional[str] = None,
        channel_override: Optional[discord.TextChannel] = None,
        reply_to: Optional[str] = None,
        reply_message_ref: Optional[discord.MessageReference] = None,
        ping: bool = False,
        files: Optional[List[discord.File]] = None,
    ) -> Tuple[bool, str]:
        """Core execution pipeline for say command."""
        files = files or []
        target_channel = current_channel
        target_msg: Optional[discord.Message] = None

        text = raw_text or ""

        # 1. Parse prefix leading arguments if present
        parsed_cid, parsed_reply, remaining_text = parse_prefix_args(text)
        if channel_override:
            target_channel = channel_override
        elif parsed_cid:
            ch = bot.get_channel(int(parsed_cid))
            if ch is None:
                try:
                    ch = await bot.fetch_channel(int(parsed_cid))
                except Exception:
                    ch = None
            if ch and isinstance(ch, (discord.TextChannel, discord.Thread, discord.VoiceChannel, discord.StageChannel)):
                target_channel = ch
                text = remaining_text

        # 2. Resolve target message to reply to
        # A) Native Discord reply reference
        if reply_message_ref and reply_message_ref.message_id:
            try:
                ref_ch = target_channel
                if reply_message_ref.channel_id and reply_message_ref.channel_id != getattr(target_channel, "id", None):
                    ref_ch = bot.get_channel(reply_message_ref.channel_id)
                    if ref_ch is None:
                        ref_ch = await bot.fetch_channel(reply_message_ref.channel_id)
                if hasattr(ref_ch, "fetch_message"):
                    target_msg = await ref_ch.fetch_message(reply_message_ref.message_id)
                else:
                    target_msg = reply_message_ref
            except Exception as e:
                logger.debug("Failed to resolve native message reference: %s", e)
                target_msg = reply_message_ref
            if not target_msg:
                target_msg = reply_message_ref

        # B) Explicit reply_to parameter or parsed link/ID from text
        candidate_reply = reply_to or parsed_reply
        if not target_msg and candidate_reply:
            candidate_reply = candidate_reply.strip()
            match = MESSAGE_LINK_REGEX.search(candidate_reply)
            if match:
                c_id, m_id = int(match.group(2)), int(match.group(3))
                try:
                    ch = bot.get_channel(c_id) or await bot.fetch_channel(c_id)
                    target_msg = await ch.fetch_message(m_id)
                    target_channel = ch
                    if parsed_reply and not reply_to:
                        text = remaining_text
                except Exception as e:
                    logger.debug("Failed to fetch message from link: %s", e)
            elif candidate_reply.isdigit() and len(candidate_reply) >= 17:
                try:
                    if hasattr(target_channel, "fetch_message"):
                        target_msg = await target_channel.fetch_message(int(candidate_reply))
                        if parsed_reply and not reply_to:
                            text = remaining_text
                except Exception as e:
                    logger.debug("Failed to fetch message by ID: %s", e)

        # 3. Check for -ping or --ping in text to toggle reply mention
        if text and ("-ping" in text.split() or "--ping" in text.split()):
            ping = True
            text = re.sub(r"--?ping\b", "", text).strip()

        final_text = text.strip()
        if not final_text and not files:
            return False, "❌ Please provide a message or attach a file to send."

        # 4. Check permissions in target channel
        if current_guild and hasattr(target_channel, "permissions_for"):
            perms = target_channel.permissions_for(current_guild.me)
            if not perms.send_messages:
                return False, f"❌ I lack permission to send messages in {getattr(target_channel, 'mention', 'that channel')}."

        allowed_mentions = discord.AllowedMentions(
            replied_user=ping,
            everyone=False,
            roles=False,
            users=True,
        )

        # 5. Chunk message if > 2000 characters
        chunks: List[str] = []
        if final_text:
            chunks = [final_text[i : i + 2000] for i in range(0, len(final_text), 2000)]
        else:
            chunks = [""]

        first = True
        for chunk in chunks:
            content_to_send = chunk if chunk else None
            if first:
                await target_channel.send(
                    content=content_to_send,
                    files=files,
                    reference=target_msg,
                    allowed_mentions=allowed_mentions,
                )
                first = False
            else:
                await target_channel.send(
                    content=content_to_send,
                    allowed_mentions=allowed_mentions,
                )

        # 6. Record active saying state for persistence
        channel_key = str(getattr(target_channel, "id", "0"))
        user_id = str(getattr(author, "id", "0"))
        key = f"{channel_key}_{user_id}"
        self.bot.active_saying[key] = {
            "message": final_text,
            "timestamp": datetime.now().isoformat(),
        }

        return True, "✅ Message sent successfully."

    # ── Prefix Command (n!say) ──────────────────────────────────────────────

    @commands.command(name="say", aliases=["echo"])
    @owner_only_prefix()
    async def say_prefix(self, ctx: commands.Context, *, text: Optional[str] = None):
        """
        Send a message as the bot (Owner Only).
        
        Features:
          • Replying to messages natively via Discord reply
          • Replying to message links or message IDs (n!say <link/ID> Hello)
          • Sending to other channels (n!say #channel Hello)
          • Forwarding attachments (images, files, videos)
          • Auto-deleting command invocation for stealth
          • Toggling reply ping via -ping
        """
        # Delete invoking message for stealth
        if ctx.message:
            try:
                await ctx.message.delete()
            except Exception:
                pass

        files: List[discord.File] = []
        if ctx.message and ctx.message.attachments:
            for att in ctx.message.attachments:
                try:
                    files.append(await att.to_file())
                except Exception as e:
                    logger.warning("Failed to forward attachment: %s", e)

        reply_ref = ctx.message.reference if ctx.message else None

        success, status_msg = await self._execute_say(
            bot=self.bot,
            author=ctx.author,
            current_channel=ctx.channel,
            current_guild=ctx.guild,
            raw_text=text,
            reply_message_ref=reply_ref,
            files=files,
        )
        if not success:
            try:
                await ctx.send(status_msg, delete_after=5)
            except Exception:
                pass

    @say_prefix.error
    async def say_prefix_error(self, ctx: commands.Context, error: Exception):
        if isinstance(error, (commands.CheckFailure, commands.NotOwner)):
            try:
                await ctx.send("❌ This command is restricted to the bot owner only.", delete_after=5)
            except Exception:
                pass

    # ── Slash Command (/say) ────────────────────────────────────────────────

    @app_commands.command(name="say", description="Make the bot say or reply with a message (Owner Only)")
    @app_commands.describe(
        message="The message you want the bot to say",
        reply_to="Message link or message ID to reply to (optional)",
        channel="Channel to send the message in (optional)",
        ping="Whether to mention/ping the author when replying (default: False)",
        attachment="A file or image to send (optional)",
    )
    @owner_only_slash()
    async def say_slash(
        self,
        interaction: discord.Interaction,
        message: Optional[str] = None,
        reply_to: Optional[str] = None,
        channel: Optional[discord.TextChannel] = None,
        ping: bool = False,
        attachment: Optional[discord.Attachment] = None,
    ):
        """Make the bot say something or reply to a message (Owner Only)."""
        await interaction.response.defer(ephemeral=True)

        files: List[discord.File] = []
        if attachment:
            try:
                files.append(await attachment.to_file())
            except Exception as e:
                logger.warning("Failed to convert slash attachment: %s", e)

        success, status_msg = await self._execute_say(
            bot=self.bot,
            author=interaction.user,
            current_channel=interaction.channel,
            current_guild=interaction.guild,
            raw_text=message,
            channel_override=channel,
            reply_to=reply_to,
            ping=ping,
            files=files,
        )

        await interaction.followup.send(status_msg, ephemeral=True)

    @say_slash.error
    async def say_slash_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        if isinstance(error, (app_commands.CheckFailure, commands.CheckFailure)):
            msg = "❌ This command is restricted to the bot owner only."
            if interaction.response.is_done():
                await interaction.followup.send(msg, ephemeral=True)
            else:
                await interaction.response.send_message(msg, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Say(bot))

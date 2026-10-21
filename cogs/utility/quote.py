"""
cogs/utility/quote.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nexora Complete Production-Grade Quote System.

Features:
  • High-fidelity dark atmospheric quote card generation (PIL) inspired
    by "Make it a Quote", with automatic fallback to rich Discord embeds.
  • /quote send [link], prefix n!quote (with replied-to message or link),
    and native Discord Message Context Menu: Apps ➔ "Quote Message".
  • Real Discord jump link to the source message.
  • Stateless [ 🗑️ Remove my Quote ] button: quoter user ID is encoded
    directly in the button custom_id (quote:delete:<user_id>).
    Strict ownership verification and moderator override with zero database bloat.
  • Full administrator configuration panel (/quote settings, /quote channel,
    /quote toggle, /quote exclude, /quote logchannel).
  • Permission validation & channel privacy protection: users cannot quote
    from channels they lack permission to view.
  • Mass-mention suppression (disallows @everyone, @here, and role pings).
  • Lightweight server settings persistence (MongoDB + local JSON fallback).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import io
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.quote_card import compose_image_quote, generate_quote_card
from utils.quote_storage import GuildQuoteSettings, QuoteStorage
from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    CYAN_COLOR,
)

logger = logging.getLogger(__name__)

# Regex matching Discord message links across discord.com, canary, ptb, discordapp.com
MESSAGE_LINK_REGEX = re.compile(
    r"https?://(?:(?:canary|ptb)\.)?discord(?:app)?\.com/channels/(\d+|@me)/(\d+)/(\d+)",
    re.IGNORECASE,
)


def parse_message_link(link: str) -> Optional[Tuple[int, int, int]]:
    """Extract (guild_id, channel_id, message_id) from a Discord message link."""
    if not link:
        return None
    match = MESSAGE_LINK_REGEX.search(link.strip())
    if not match:
        return None
    raw_guild, raw_channel, raw_message = match.groups()
    if raw_guild == "@me" or not raw_guild.isdigit():
        return None
    return int(raw_guild), int(raw_channel), int(raw_message)


class QuoteCardView(discord.ui.View):
    """
    Stateless view attached to each posted quote card.
    Encodes the quoter's user ID directly into the button custom_id.
    """

    def __init__(self, quoter_id: int):
        super().__init__(timeout=None)
        self.add_item(
            discord.ui.Button(
                label="Remove my Quote",
                emoji="🗑️",
                style=discord.ButtonStyle.secondary,
                custom_id=f"quote:delete:{quoter_id}",
            )
        )


class QuoteSettingsView(discord.ui.View):
    """Interactive settings control view for server administrators."""

    def __init__(self, cog: "Quote", guild_id: int, user_id: int):
        super().__init__(timeout=120)
        self.cog = cog
        self.guild_id = guild_id
        self.user_id = user_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ Only the administrator who opened this settings panel may interact with it.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(
        label="Toggle Status",
        emoji="🔄",
        style=discord.ButtonStyle.primary,
        custom_id="quote_cfg:toggle",
    )
    async def toggle_status(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        settings = await self.cog.storage.get_settings(self.guild_id)
        settings.enabled = not settings.enabled
        await self.cog.storage.save_settings(self.guild_id, settings)

        embed = await self.cog.build_settings_embed(interaction.guild, settings)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="Toggle Style (Card / Embed)",
        emoji="🎨",
        style=discord.ButtonStyle.secondary,
        custom_id="quote_cfg:style",
    )
    async def toggle_style(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        settings = await self.cog.storage.get_settings(self.guild_id)
        settings.render_style = "embed" if settings.render_style == "card" else "card"
        await self.cog.storage.save_settings(self.guild_id, settings)

        embed = await self.cog.build_settings_embed(interaction.guild, settings)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(
        label="Diagnostics",
        emoji="🧪",
        style=discord.ButtonStyle.success,
        custom_id="quote_cfg:diag",
    )
    async def run_diagnostics(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        settings = await self.cog.storage.get_settings(self.guild_id)
        diag_lines = []

        # Check destination channel permissions
        dest_channel = None
        if settings.destination_channel_id:
            dest_channel = interaction.guild.get_channel(settings.destination_channel_id)

        if dest_channel:
            bot_member = interaction.guild.me
            perms = dest_channel.permissions_for(bot_member)
            diag_lines.append(f"**Destination Channel:** {dest_channel.mention}")
            diag_lines.append(f"• Send Messages: {'✅' if perms.send_messages else '❌'}")
            diag_lines.append(f"• Embed Links: {'✅' if perms.embed_links else '❌'}")
            diag_lines.append(f"• Attach Files: {'✅' if perms.attach_files else '❌'}")
            diag_lines.append(f"• Read Message History: {'✅' if perms.read_message_history else '❌'}")
        else:
            diag_lines.append("ℹ️ **Destination Channel:** Not configured (Quotes post in command channel)")

        diag_lines.append(f"**Quote System:** {'🟢 Active' if settings.enabled else '🔴 Disabled'}")
        diag_lines.append(f"**Total Quotes Created:** `{settings.quotes_count}`")

        diag_embed = discord.Embed(
            title="🔍 Quote System Diagnostics",
            description="\n".join(diag_lines),
            color=CYAN_COLOR,
        )
        diag_embed.set_footer(text="NEXORA System Audit • All checks verified")
        await interaction.response.send_message(embed=diag_embed, ephemeral=True)


class Quote(commands.Cog):
    """
    Production-grade Quote System for NEXORA.
    Supports quoting messages via replies, links, and context menu.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storage = QuoteStorage(bot)

        # Context menu registration (Message context menu)
        self.ctx_menu = app_commands.ContextMenu(
            name="Quote Message",
            callback=self._context_menu_quote,
        )
        self.bot.tree.add_command(self.ctx_menu)

    async def cog_unload(self):
        try:
            self.bot.tree.remove_command(self.ctx_menu.name, type=self.ctx_menu.type)
        except Exception as exc:
            logger.debug("Error removing quote context menu: %s", exc)

    # ── Stateless Button Listener ──────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_interaction(self, interaction: discord.Interaction):
        """Dispatches quote deletion interactions with zero database overhead."""
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data.get("custom_id", "")
            if custom_id.startswith("quote:delete:"):
                await self.handle_quote_removal(interaction, custom_id)

    # ── Context Menu Callback ──────────────────────────────────────────────────

    async def _context_menu_quote(
        self, interaction: discord.Interaction, message: discord.Message
    ):
        """Right-click or long-press on any message ➔ Apps ➔ Quote Message."""
        await interaction.response.defer(ephemeral=True)
        await self._execute_quote(
            user=interaction.user,
            guild=interaction.guild,
            source_message=message,
            respond_func=interaction.followup.send,
            is_interaction=True,
        )

    # ── Removal Handling ───────────────────────────────────────────────────────

    async def handle_quote_removal(
        self, interaction: discord.Interaction, custom_id: str
    ):
        """
        Processes the [ 🗑️ Remove my Quote ] button click statelessly.
        Extracts quoter_id directly from custom_id: quote:delete:<quoter_id>.
        """
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Quotes can only be managed within a server.", ephemeral=True
            )
            return

        raw_id = custom_id.split("quote:delete:")[-1]
        quoter_id = int(raw_id) if raw_id.isdigit() else 0

        user = interaction.user
        is_owner = user.id == quoter_id
        is_mod = (
            user.guild_permissions.manage_messages
            or user.guild_permissions.administrator
            or user.id == self.bot.owner_id
        )

        # Check footer fallback for legacy quotes if quoter_id is 0
        if not is_owner and interaction.message and interaction.message.embeds:
            emb = interaction.message.embeds[0]
            if emb.footer and emb.footer.text and f"Quoted by {user.display_name}" in emb.footer.text:
                is_owner = True

        if not is_owner and not is_mod:
            await interaction.response.send_message(
                "❌ Only the member who created this quote or a server moderator can remove it.",
                ephemeral=True,
            )
            return

        # Authorized! Delete quote message
        try:
            await interaction.message.delete()
        except discord.NotFound:
            pass
        except discord.Forbidden:
            await interaction.response.send_message(
                "❌ I lack permissions to delete this quote card in this channel.",
                ephemeral=True,
            )
            return
        except Exception as exc:
            logger.error("Failed to delete quote card: %s", exc)
            await interaction.response.send_message(
                f"❌ Error deleting quote: {exc}", ephemeral=True
            )
            return

        # Audit / Moderation logging if configured
        settings = await self.storage.get_settings(interaction.guild.id)
        if settings.log_channel_id:
            log_chan = interaction.guild.get_channel(settings.log_channel_id)
            if log_chan and log_chan.permissions_for(interaction.guild.me).send_messages:
                log_embed = discord.Embed(
                    title="🗑️ Quote Removed",
                    color=WARNING_COLOR,
                    timestamp=datetime.now(timezone.utc),
                )
                log_embed.add_field(
                    name="Removed By",
                    value=f"{user.mention} (`{user.id}`)" + (" [Moderator]" if is_mod and not is_owner else ""),
                    inline=True,
                )
                if quoter_id:
                    log_embed.add_field(
                        name="Original Quoter",
                        value=f"<@{quoter_id}> (`{quoter_id}`)",
                        inline=True,
                    )
                try:
                    await log_chan.send(embed=log_embed)
                except Exception:
                    pass

        await interaction.response.send_message(
            "✅ Quote successfully removed.", ephemeral=True
        )

    # ── Settings UI Builder ────────────────────────────────────────────────────

    async def build_settings_embed(
        self, guild: discord.Guild, settings: GuildQuoteSettings
    ) -> discord.Embed:
        dest_mention = (
            f"<#{settings.destination_channel_id}>"
            if settings.destination_channel_id
            else "`Current Channel (Default)`"
        )
        status_badge = "🟢 **Enabled**" if settings.enabled else "🔴 **Disabled**"
        style_badge = "🖼️ **Atmospheric Card (Image + Embed)**" if settings.render_style == "card" else "📄 **Pure Embed**"

        roles_desc = (
            ", ".join(f"<@&{r}>" for r in settings.allowed_roles)
            if settings.allowed_roles
            else "`@everyone (All members)`"
        )
        excluded_desc = (
            ", ".join(f"<#{c}>" for c in settings.excluded_channels)
            if settings.excluded_channels
            else "`None`"
        )
        log_desc = (
            f"<#{settings.log_channel_id}>"
            if settings.log_channel_id
            else "`Disabled`"
        )

        embed = discord.Embed(
            title="⚙️ Quote System Configuration",
            description=f"Server configuration and controls for **{guild.name}**.",
            color=BRAND_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="System Status", value=status_badge, inline=True)
        embed.add_field(name="Destination Channel", value=dest_mention, inline=True)
        embed.add_field(name="Card Style", value=style_badge, inline=True)
        embed.add_field(name="Allowed Quoter Roles", value=roles_desc, inline=False)
        embed.add_field(name="Excluded Channels", value=excluded_desc, inline=False)
        embed.add_field(name="Moderation Log Channel", value=log_desc, inline=True)
        embed.add_field(name="Total Quotes Sent", value=f"`{settings.quotes_count}` quotes", inline=True)

        embed.set_footer(
            text="Use the buttons below or slash commands like /quote channel to configure."
        )
        return embed

    # ── Core Quote Processing ──────────────────────────────────────────────────

    async def _execute_quote(
        self,
        user: discord.Member,
        guild: discord.Guild,
        source_message: discord.Message,
        respond_func,
        is_interaction: bool = False,
    ):
        """Validates permissions, renders the quote card/embed, posts it, and persists settings."""
        if not guild:
            await respond_func("❌ Quotes can only be generated within a server.")
            return

        settings = await self.storage.get_settings(guild.id)

        # 1. System enabled check
        if not settings.enabled:
            await respond_func(
                "❌ The quote system is currently disabled in this server. An administrator can enable it with `/quote toggle`."
            )
            return

        # 2. Allowed roles check
        if settings.allowed_roles:
            user_role_ids = {r.id for r in getattr(user, "roles", [])}
            if not any(r in user_role_ids for r in settings.allowed_roles) and not user.guild_permissions.administrator:
                await respond_func(
                    "❌ You do not possess an authorized role to quote messages in this server."
                )
                return

        # 3. Source channel exclusion check
        source_channel = source_message.channel
        if source_channel.id in settings.excluded_channels:
            await respond_func(
                "❌ Quoting messages from this channel has been restricted by server administrators."
            )
            return

        # 4. PRIVACY CHECK: Can the quoter view the source channel?
        perms = source_channel.permissions_for(user)
        if not perms.read_messages or not perms.read_message_history:
            await respond_func(
                "❌ You do not have permission to view or quote messages from that channel."
            )
            return

        # 5. Determine destination channel
        dest_channel = None
        if settings.destination_channel_id:
            dest_channel = guild.get_channel(settings.destination_channel_id)
            if not dest_channel:
                try:
                    dest_channel = await self.bot.fetch_channel(settings.destination_channel_id)
                except Exception:
                    dest_channel = None

        # Fallback to source channel or interaction channel if dest_channel unset or missing
        if not dest_channel:
            dest_channel = source_channel

        # 6. Check Bot permissions in destination channel
        bot_member = guild.me
        dest_perms = dest_channel.permissions_for(bot_member)
        if not dest_perms.send_messages:
            await respond_func(
                f"❌ I do not have permission to send messages in the quote channel {dest_channel.mention}."
            )
            return
        if not dest_perms.embed_links:
            await respond_func(
                f"❌ I require the **Embed Links** permission in {dest_channel.mention} to post quote cards."
            )
            return

        # 7. Extract message details safely
        author = source_message.author
        author_display_name = getattr(author, "display_name", author.name)
        author_handle = getattr(author, "name", str(author))
        content = source_message.clean_content or ""

        # Check for image attachments vs other media/files
        image_attachment = None
        other_attachments = []
        for att in source_message.attachments:
            is_img = (att.content_type and att.content_type.startswith("image/")) or att.filename.lower().endswith(
                (".png", ".jpg", ".jpeg", ".webp", ".gif")
            )
            if is_img and not image_attachment:
                image_attachment = att
            else:
                other_attachments.append(att)

        # Real Discord message jump link
        jump_url = f"https://discord.com/channels/{guild.id}/{source_channel.id}/{source_message.id}"
        msg_dt = (
            source_message.created_at
            if isinstance(getattr(source_message, "created_at", None), datetime)
            else datetime.now(timezone.utc)
        )
        timestamp_str = msg_dt.strftime("%b %d, %Y")
        channel_name = getattr(source_channel, "name", "channel")

        quote_file: Optional[discord.File] = None
        embed: Optional[discord.Embed] = None

        # Extra attachments formatted gracefully
        extra_att_lines = []
        for att in other_attachments:
            is_media = (att.content_type and att.content_type.startswith("image/")) or att.filename.lower().endswith(
                (".png", ".jpg", ".jpeg", ".webp", ".gif")
            )
            icon = "🖼️" if is_media else "📎"
            extra_att_lines.append(f"{icon} [{att.filename}]({att.url})")
        extra_att_str = ("\n" + "\n".join(extra_att_lines)) if extra_att_lines else ""

        # ── LAYOUT ROUTING ──────────────────────────────────────────────────
        if image_attachment is not None:
            # ── CASE A: ORIGINAL MESSAGE CONTAINS AN IMAGE ──────────────────
            # In "card" style, intelligently compose image with ambient dark canvas & rounded corners
            if settings.render_style == "card":
                img_bytes: Optional[bytes] = None
                try:
                    img_bytes = await image_attachment.read()
                except Exception as e:
                    logger.warning("Failed to download image attachment for card composition: %s", e)

                if img_bytes:
                    try:
                        card_buf = await asyncio.to_thread(compose_image_quote, img_bytes)
                        if card_buf:
                            quote_file = discord.File(card_buf, filename="quote.png")
                    except Exception as e:
                        logger.error("compose_image_quote failed: %s", e)
                        quote_file = None

            embed_desc_lines = [f"[Jump to original message]({jump_url})"]
            if content:
                embed_desc_lines.append(f"\n>>> {content}")
            if extra_att_str:
                embed_desc_lines.append(extra_att_str)

            embed = discord.Embed(
                description="\n".join(embed_desc_lines),
                color=0x2B2D31,
                timestamp=msg_dt,
            )
            embed.set_author(
                name=f"{author_display_name} (@{author_handle})",
                icon_url=author.display_avatar.url,
            )
            if quote_file:
                embed.set_image(url="attachment://quote.png")
            else:
                embed.set_image(url=image_attachment.url)

            embed.set_footer(
                text=f"Quoted by {user.display_name} • #{channel_name}",
                icon_url=user.display_avatar.url,
            )

        elif settings.render_style == "card" and content:
            # ── CASE B: TEXT-ONLY MESSAGE (ATMOSPHERIC PIL CARD) ───────────
            avatar_bytes: Optional[bytes] = None
            try:
                avatar_bytes = await author.display_avatar.read()
            except Exception as e:
                logger.debug("Failed to read author avatar bytes: %s", e)

            try:
                card_buf = await asyncio.to_thread(
                    generate_quote_card,
                    author_name=author_display_name,
                    author_handle=author_handle,
                    text=content,
                    avatar_bytes=avatar_bytes,
                    channel_name=channel_name,
                    timestamp_str=timestamp_str,
                )
                if card_buf:
                    quote_file = discord.File(card_buf, filename="quote.png")
            except Exception as e:
                logger.error("PIL card generation failed: %s", e)
                quote_file = None

            if quote_file:
                embed_desc_lines = [f"[Jump to original message]({jump_url})"]
                if extra_att_str:
                    embed_desc_lines.append(extra_att_str)

                embed = discord.Embed(
                    description="\n".join(embed_desc_lines),
                    color=0x2B2D31,
                    timestamp=msg_dt,
                )
                # Author is already visually baked into the card (name, handle, avatar),
                # so omit embed.set_author to avoid duplicate redundant headers.
                embed.set_image(url="attachment://quote.png")
                embed.set_footer(
                    text=f"Quoted by {user.display_name} • #{channel_name}",
                    icon_url=user.display_avatar.url,
                )

        # ── CASE C: FALLBACK OR NON-IMAGE ATTACHMENT ONLY ───────────────────
        if embed is None:
            embed_desc_lines = [f"[Jump to original message]({jump_url})"]
            if content:
                embed_desc_lines.append(f"\n>>> {content}")
            elif other_attachments:
                embed_desc_lines.append("\n> _[Shared an attachment]_")
            if extra_att_str:
                embed_desc_lines.append(extra_att_str)

            embed = discord.Embed(
                description="\n".join(embed_desc_lines),
                color=0x2B2D31,
                timestamp=msg_dt,
            )
            embed.set_author(
                name=f"{author_display_name} (@{author_handle})",
                icon_url=author.display_avatar.url,
            )
            embed.set_footer(
                text=f"Quoted by {user.display_name} • #{channel_name}",
                icon_url=user.display_avatar.url,
            )

        # Stateless interactive view with [ 🗑️ Remove my Quote ]
        view = QuoteCardView(quoter_id=user.id)

        # Post the quote to destination channel
        # Suppress all unintended mass pings from quoted content
        allowed_mentions = discord.AllowedMentions(
            everyone=False, roles=False, users=False
        )

        try:
            if quote_file:
                posted_msg = await dest_channel.send(
                    embed=embed,
                    file=quote_file,
                    view=view,
                    allowed_mentions=allowed_mentions,
                )
            else:
                posted_msg = await dest_channel.send(
                    embed=embed,
                    view=view,
                    allowed_mentions=allowed_mentions,
                )
        except discord.Forbidden:
            await respond_func(
                f"❌ Permission denied: Unable to send messages or attach files in {dest_channel.mention}."
            )
            return
        except Exception as exc:
            logger.error("Failed to post quote message: %s", exc)
            await respond_func(f"❌ Failed to post quote: {exc}")
            return

        # 10. Increment lightweight server quote counter
        await self.storage.increment_quote_count(guild.id)

        # 11. Send feedback to quoter
        posted_link = f"https://discord.com/channels/{guild.id}/{dest_channel.id}/{posted_msg.id}"
        confirm_msg = f"✨ **Quote published successfully!** [View Quote]({posted_link})"

        if is_interaction:
            await respond_func(confirm_msg, ephemeral=True)
        else:
            if dest_channel.id != source_channel.id:
                try:
                    await respond_func(confirm_msg)
                except Exception:
                    pass

        # 12. Optional moderation audit logging
        if settings.log_channel_id and settings.log_channel_id != dest_channel.id:
            log_chan = guild.get_channel(settings.log_channel_id)
            if log_chan and log_chan.permissions_for(guild.me).send_messages:
                log_embed = discord.Embed(
                    title="📝 Quote Created",
                    color=SUCCESS_COLOR,
                    timestamp=datetime.now(timezone.utc),
                )
                log_embed.add_field(name="Quoted By", value=f"{user.mention} (`{user.id}`)", inline=True)
                log_embed.add_field(name="Author", value=f"{author.mention} (`{author.id}`)", inline=True)
                log_embed.add_field(name="Source Channel", value=f"{source_channel.mention}", inline=True)
                log_embed.add_field(
                    name="Links",
                    value=f"[Original Message]({jump_url}) • [Quote Card]({posted_link})",
                    inline=False,
                )
                try:
                    await log_chan.send(embed=log_embed)
                except Exception:
                    pass

    # ── Slash and Prefix Command Group ─────────────────────────────────────────

    @commands.hybrid_group(
        name="quote",
        aliases=["q"],
        fallback="send",
        help="Quote a message by link or by replying to it.",
    )
    @app_commands.describe(
        message_link="The Discord message link to quote (e.g. https://discord.com/channels/...)"
    )
    async def quote_group(
        self,
        ctx: commands.Context,
        *,
        message_link: Optional[str] = None,
    ):
        """
        Quote a message by link or by replying to it.
        Example: /quote message_link: https://discord.com/channels/...
        """
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)

        respond = ctx.interaction.followup.send if ctx.interaction else ctx.send

        # Check for reply if prefix command
        source_message = None
        if not message_link and ctx.message and ctx.message.reference:
            ref = ctx.message.reference
            if ref.message_id and ref.channel_id:
                channel = ctx.guild.get_channel(ref.channel_id)
                if channel:
                    try:
                        source_message = await channel.fetch_message(ref.message_id)
                    except discord.NotFound:
                        await respond("❌ The replied-to message could not be found.")
                        return
                    except discord.Forbidden:
                        await respond("❌ I lack permissions to read message history in that channel.")
                        return
                    except Exception as e:
                        await respond(f"❌ Failed to fetch message: {e}")
                        return

        # If link is provided
        if not source_message and message_link:
            parsed = parse_message_link(message_link)
            if not parsed:
                await respond(
                    "❌ Invalid Discord message link. Please ensure it follows the format:\n"
                    "`https://discord.com/channels/<guild_id>/<channel_id>/<message_id>`"
                )
                return

            link_guild_id, link_channel_id, link_message_id = parsed
            if link_guild_id != ctx.guild.id:
                await respond("❌ You cannot quote messages from a different server.")
                return

            channel = ctx.guild.get_channel(link_channel_id)
            if not channel:
                try:
                    channel = await self.bot.fetch_channel(link_channel_id)
                except Exception:
                    channel = None

            if not channel:
                await respond("❌ The channel for that message could not be accessed.")
                return

            try:
                source_message = await channel.fetch_message(link_message_id)
            except discord.NotFound:
                await respond("❌ The referenced message could not be found. It may have been deleted.")
                return
            except discord.Forbidden:
                await respond("❌ I do not have permission to read message history in that channel.")
                return
            except Exception as e:
                await respond(f"❌ Failed to fetch message: {e}")
                return

        # If neither link nor reply was detected, display helpful instructions
        if not source_message:
            help_embed = discord.Embed(
                title="💬 How to Quote a Message",
                description=(
                    "You can quote any message easily using three different methods:\n\n"
                    "1️⃣ **Message Context Menu (Fastest & Easiest):**\n"
                    "• Right-click or long-press any message ➔ **Apps** ➔ **Quote Message**\n\n"
                    "2️⃣ **By Message Link:**\n"
                    "• Copy message link (Right-click ➔ Copy Message Link)\n"
                    "• Run `/quote message_link: <paste-link>`\n\n"
                    "3️⃣ **By Replying (Prefix):**\n"
                    "• Reply to any message with `n!quote`\n"
                ),
                color=BRAND_COLOR,
            )
            help_embed.set_footer(text="NEXORA Quote System • Beautiful Discord Quote Cards")
            await respond(embed=help_embed)
            return

        # Execute quote
        await self._execute_quote(
            user=ctx.author,
            guild=ctx.guild,
            source_message=source_message,
            respond_func=respond,
            is_interaction=bool(ctx.interaction),
        )

    # ── Subcommand: /quote channel ─────────────────────────────────────────────

    @quote_group.command(
        name="channel",
        help="Set or clear the destination channel where quotes are posted.",
    )
    @app_commands.describe(
        target="The channel where quote cards should be sent (leave blank to reset to default)"
    )
    @commands.has_permissions(manage_guild=True)
    async def set_channel(
        self, ctx: commands.Context, target: Optional[discord.TextChannel] = None
    ):
        """Set or reset the server's quote destination channel."""
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)

        respond = ctx.interaction.followup.send if ctx.interaction else ctx.send
        settings = await self.storage.get_settings(ctx.guild.id)

        if target is None:
            settings.destination_channel_id = None
            await self.storage.save_settings(ctx.guild.id, settings)
            await respond(
                "✅ Quote destination channel reset. Quotes will now post directly in the channel where the quote command is run."
            )
            return

        # Check permissions in target channel
        perms = target.permissions_for(ctx.guild.me)
        if not perms.send_messages or not perms.embed_links:
            await respond(
                f"⚠️ I need **Send Messages** and **Embed Links** permissions in {target.mention} to post quotes properly."
            )

        settings.destination_channel_id = target.id
        await self.storage.save_settings(ctx.guild.id, settings)

        embed = discord.Embed(
            title="🎯 Quote Channel Configured",
            description=f"All server quotes will now be posted to {target.mention}.",
            color=SUCCESS_COLOR,
        )
        embed.set_footer(text="Administrators can change this anytime with /quote channel")
        await respond(embed=embed)

    # ── Subcommand: /quote settings ───────────────────────────────────────────

    @quote_group.command(
        name="settings",
        help="View and configure the server's quote settings and diagnostics.",
    )
    @commands.has_permissions(manage_guild=True)
    async def view_settings(self, ctx: commands.Context):
        """Interactive control panel for quote system settings."""
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)

        respond = ctx.interaction.followup.send if ctx.interaction else ctx.send
        settings = await self.storage.get_settings(ctx.guild.id)
        embed = await self.build_settings_embed(ctx.guild, settings)
        view = QuoteSettingsView(self, ctx.guild.id, ctx.author.id)

        await respond(embed=embed, view=view)

    # ── Subcommand: /quote toggle ─────────────────────────────────────────────

    @quote_group.command(
        name="toggle",
        help="Quickly enable or disable the quote system in this server.",
    )
    @app_commands.describe(enabled="True to enable, False to disable (optional)")
    @commands.has_permissions(manage_guild=True)
    async def toggle_system(
        self, ctx: commands.Context, enabled: Optional[bool] = None
    ):
        """Enable or disable quotes."""
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)

        respond = ctx.interaction.followup.send if ctx.interaction else ctx.send
        settings = await self.storage.get_settings(ctx.guild.id)

        if enabled is None:
            settings.enabled = not settings.enabled
        else:
            settings.enabled = enabled

        await self.storage.save_settings(ctx.guild.id, settings)

        status_str = "🟢 **enabled**" if settings.enabled else "🔴 **disabled**"
        await respond(f"✅ Quote system has been {status_str} for **{ctx.guild.name}**.")

    # ── Subcommand: /quote exclude ────────────────────────────────────────────

    @quote_group.command(
        name="exclude",
        help="Toggle a channel on the quoting exclusion list.",
    )
    @app_commands.describe(channel="The channel to exclude or re-include from quoting")
    @commands.has_permissions(manage_guild=True)
    async def exclude_channel(
        self, ctx: commands.Context, channel: discord.TextChannel
    ):
        """Add or remove a channel from quoting exclusions."""
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)

        respond = ctx.interaction.followup.send if ctx.interaction else ctx.send
        settings = await self.storage.get_settings(ctx.guild.id)

        if channel.id in settings.excluded_channels:
            settings.excluded_channels.remove(channel.id)
            msg = f"✅ Removed {channel.mention} from the excluded list. Messages can now be quoted from this channel."
        else:
            settings.excluded_channels.append(channel.id)
            msg = f"🛡️ Added {channel.mention} to the excluded list. Members can no longer quote messages from this channel."

        await self.storage.save_settings(ctx.guild.id, settings)
        await respond(msg)

    # ── Subcommand: /quote logchannel ─────────────────────────────────────────

    @quote_group.command(
        name="logchannel",
        help="Set or remove a moderation logging channel for quotes.",
    )
    @app_commands.describe(channel="The channel to send quote creation & removal audit logs")
    @commands.has_permissions(manage_guild=True)
    async def set_log_channel(
        self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None
    ):
        """Set or disable quote audit logging."""
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)

        respond = ctx.interaction.followup.send if ctx.interaction else ctx.send
        settings = await self.storage.get_settings(ctx.guild.id)

        if channel is None:
            settings.log_channel_id = None
            await self.storage.save_settings(ctx.guild.id, settings)
            await respond("✅ Quote moderation logging has been disabled.")
            return

        settings.log_channel_id = channel.id
        await self.storage.save_settings(ctx.guild.id, settings)
        await respond(f"✅ Quote moderation audit logs will now be sent to {channel.mention}.")

    # ── Subcommand: /quote help ───────────────────────────────────────────────

    @quote_group.command(
        name="help",
        help="Display comprehensive instructions for using the quote system.",
    )
    async def quote_help(self, ctx: commands.Context):
        """Show full quote documentation and command reference."""
        if ctx.interaction:
            await ctx.interaction.response.defer(ephemeral=True)

        respond = ctx.interaction.followup.send if ctx.interaction else ctx.send

        embed = discord.Embed(
            title="📖 NEXORA Quote System Guide",
            description=(
                "NEXORA's Quote System lets members immortalize iconic server moments "
                "into high-definition atmospheric quote cards with real message jump links!\n"
            ),
            color=BRAND_COLOR,
        )

        embed.add_field(
            name="✨ Quoting Methods",
            value=(
                "• **Apps Context Menu:** Right-click or long-press any message ➔ **Apps** ➔ **Quote Message**\n"
                "• **Slash Command:** `/quote message_link: <link>`\n"
                "• **Reply (Prefix):** Reply to any message and type `n!quote`\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="🗑️ Quote Controls",
            value=(
                "• Every quote card features a **[ 🗑️ Remove my Quote ]** button.\n"
                "• Only the member who quoted it or server moderators with `Manage Messages` can remove it.\n"
                "• Unrelated members receive a denial message.\n"
            ),
            inline=False,
        )

        embed.add_field(
            name="🛡️ Administrator Commands",
            value=(
                "• `/quote channel #channel` — Set destination channel (e.g. `#quotes`)\n"
                "• `/quote settings` — View panel & test permissions\n"
                "• `/quote toggle` — Turn quoting ON or OFF\n"
                "• `/quote exclude #channel` — Prohibit quoting from specific channels\n"
                "• `/quote logchannel #channel` — Audit logging for quote creations & deletions\n"
            ),
            inline=False,
        )

        embed.set_footer(text="NEXORA Quotes • Safe, Beautiful, and Persistent")
        await respond(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Quote(bot))

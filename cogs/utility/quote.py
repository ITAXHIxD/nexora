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
  • Interactive [ 🗑️ Remove my Quote ] persistent button with strict
    ownership validation and moderator override.
  • Full administrator configuration panel (/quote settings, /quote channel,
    /quote toggle, /quote exclude, /quote logchannel).
  • Permission validation & channel privacy protection: users cannot quote
    from channels they lack permission to view.
  • Mass-mention suppression (disallows @everyone, @here, and role pings).
  • Dual persistence: MongoDB Atlas + local JSON fallback.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import io
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Tuple, Union

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from utils.quote_card import generate_quote_card
from utils.quote_storage import GuildQuoteSettings, QuoteRecord, QuoteStorage
from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    CYAN_COLOR,
    ts_format,
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


class PersistentQuoteView(discord.ui.View):
    """
    Persistent view for quote removal across bot restarts.
    Handles both fixed custom_id 'quote:remove_my_quote' and dynamic IDs.
    """

    def __init__(self, cog: Optional["Quote"] = None):
        super().__init__(timeout=None)
        self.cog = cog

    @discord.ui.button(
        label="Remove my Quote",
        emoji="🗑️",
        style=discord.ButtonStyle.secondary,
        custom_id="quote:remove_my_quote",
    )
    async def remove_quote_button(
        self, interaction: discord.Interaction, button: discord.ui.Button
    ):
        if self.cog is not None:
            await self.cog.handle_quote_removal(interaction)
        else:
            # Fallback if cog not directly attached
            bot = interaction.client
            cog = bot.get_cog("Quote")
            if cog:
                await cog.handle_quote_removal(interaction)
            else:
                await interaction.response.send_message(
                    "❌ Quote service is currently reloading. Please try again in a moment.",
                    ephemeral=True,
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
        quotes_count = await self.cog.storage.get_guild_quotes_count(self.guild_id)
        diag_lines.append(f"**Total Quotes Stored:** `{quotes_count}`")

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
        self.persistent_view = PersistentQuoteView(self)
        self.bot.add_view(self.persistent_view)

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

    async def handle_quote_removal(self, interaction: discord.Interaction):
        """Processes the [ 🗑️ Remove my Quote ] button click."""
        if not interaction.guild:
            await interaction.response.send_message(
                "❌ Quotes can only be managed within a server.", ephemeral=True
            )
            return

        msg_id = interaction.message.id if interaction.message else None
        if not msg_id:
            await interaction.response.send_message(
                "❌ Could not identify the quote message.", ephemeral=True
            )
            return

        quote = await self.storage.get_quote_by_message(interaction.guild.id, msg_id)

        user = interaction.user
        is_owner = False
        is_mod = (
            user.guild_permissions.manage_messages
            or user.guild_permissions.administrator
            or user.id == self.bot.owner_id
        )

        if quote:
            is_owner = user.id == quote.quoter_id
        else:
            # Check embed footer for legacy fallback
            if interaction.message.embeds:
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

        # Remove from storage if record exists
        if quote:
            await self.storage.delete_quote(quote.quote_id)

            # Audit / Moderation logging
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
                    log_embed.add_field(
                        name="Original Quoter",
                        value=f"<@{quote.quoter_id}> (`{quote.quoter_id}`)",
                        inline=True,
                    )
                    if quote.content_preview:
                        log_embed.add_field(
                            name="Quote Preview",
                            value=f"_{quote.content_preview[:150]}_",
                            inline=False,
                        )
                    log_embed.set_footer(text=f"Quote ID: {quote.quote_id}")
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

        quotes_count = await self.storage.get_guild_quotes_count(guild.id)

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
        embed.add_field(name="Saved Quotes", value=f"`{quotes_count}` quotes", inline=True)

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
        """Validates permissions, renders the quote card/embed, posts it, and persists metadata."""
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

        # Check for image attachments
        image_bytes: Optional[bytes] = None
        has_image = False
        attachment_links = []
        for att in source_message.attachments:
            if att.content_type and att.content_type.startswith("image/"):
                has_image = True
                if not image_bytes:
                    try:
                        image_bytes = await att.read()
                    except Exception as e:
                        logger.debug("Failed to read attachment bytes: %s", e)
            else:
                attachment_links.append(f"📎 [{att.filename}]({att.url})")

        # Download author avatar for PIL card
        avatar_bytes: Optional[bytes] = None
        try:
            avatar_bytes = await author.display_avatar.read()
        except Exception as e:
            logger.debug("Failed to read author avatar bytes: %s", e)

        # Real Discord message jump link
        jump_url = f"https://discord.com/channels/{guild.id}/{source_channel.id}/{source_message.id}"

        # 8. Render Quote Card / Embed
        quote_id = QuoteRecord().quote_id
        timestamp_str = source_message.created_at.strftime("%b %d, %Y")
        channel_name = getattr(source_channel, "name", "channel")

        quote_file: Optional[discord.File] = None
        if settings.render_style == "card":
            try:
                card_buf = await asyncio.to_thread(
                    generate_quote_card,
                    author_name=author_display_name,
                    author_handle=author_handle,
                    text=content,
                    avatar_bytes=avatar_bytes,
                    image_bytes=image_bytes,
                    channel_name=channel_name,
                    timestamp_str=timestamp_str,
                )
                if card_buf:
                    quote_file = discord.File(card_buf, filename=f"quote_{quote_id}.png")
            except Exception as e:
                logger.error("PIL card generation failed, falling back to embed: %s", e)
                quote_file = None

        # Build Discord Embed
        # Prominent jump link at the top
        embed_desc_lines = [f"[Jump to original message]({jump_url})"]
        if attachment_links:
            embed_desc_lines.append("\n" + "\n".join(attachment_links))

        # If card failed to generate or style is embed, format blockquote text
        if not quote_file:
            if content:
                # Format with blockquote styling
                quoted_lines = [f"> {line}" for line in content.split("\n")]
                embed_desc_lines.append("\n" + "\n".join(quoted_lines))
            elif has_image:
                embed_desc_lines.append("\n> _[Shared an image]_")

        embed = discord.Embed(
            description="\n".join(embed_desc_lines),
            color=BRAND_COLOR,
            timestamp=source_message.created_at,
        )

        if quote_file:
            embed.set_image(url=f"attachment://quote_{quote_id}.png")
        elif has_image and source_message.attachments:
            # Set the image to the first attachment url
            embed.set_image(url=source_message.attachments[0].url)

        # Author and Footer
        if not quote_file:
            embed.set_author(
                name=f"{author_display_name} (@{author_handle})",
                icon_url=author.display_avatar.url,
            )

        embed.set_footer(
            text=f"Quoted by {user.display_name} • #{channel_name}",
            icon_url=user.display_avatar.url,
        )

        # 9. Interactive view with [ 🗑️ Remove my Quote ]
        view = PersistentQuoteView(self)

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

        # 10. Save quote metadata
        record = QuoteRecord(
            quote_id=quote_id,
            guild_id=guild.id,
            source_channel_id=source_channel.id,
            source_message_id=source_message.id,
            quote_channel_id=dest_channel.id,
            quote_message_id=posted_msg.id,
            quoter_id=user.id,
            author_id=author.id,
            created_at=datetime.now(timezone.utc).isoformat(),
            jump_url=jump_url,
            content_preview=content[:200],
            has_image=has_image,
        )
        await self.storage.add_quote(record)

        # 11. Send feedback to quoter
        posted_link = f"https://discord.com/channels/{guild.id}/{dest_channel.id}/{posted_msg.id}"
        confirm_msg = f"✨ **Quote published successfully!** [View Quote]({posted_link})"

        if is_interaction:
            await respond_func(confirm_msg, ephemeral=True)
        else:
            # If in the same channel, don't spam duplicate confirmation
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
                log_embed.set_footer(text=f"Quote ID: {quote_id}")
                try:
                    await log_chan.send(embed=log_embed)
                except Exception:
                    pass

    # ── Slash and Prefix Command Group ─────────────────────────────────────────

    @commands.hybrid_group(
        name="quote",
        invoke_without_command=True,
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

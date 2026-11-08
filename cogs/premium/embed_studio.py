"""
cogs/premium/embed_studio.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Universal Embed & Announcement Studio for Nexora.

Allows server staff (Administrators, Server Managers, Message Moderators)
to craft, visually compose, import raw JSON (Discohook format),
live-preview, and dispatch state-of-the-art embeds to any channel.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Union, List, Tuple

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    PREMIUM_COLOR,
    SUCCESS_COLOR,
    ERROR_COLOR,
    CYAN_COLOR,
)

logger = logging.getLogger(__name__)


def parse_discohook_json(raw_input: str) -> Tuple[Optional[str], List[discord.Embed]]:
    """
    Parses Discohook export JSON or raw Discord embed JSON.
    Supports:
      • Standard Discohook wrapper: {"content": "...", "embeds": [...]}
      • Single embed dict: {"title": "...", "description": "...", ...}
      • Array of embed dicts: [{...}, {...}]
      • Codeblock markdown wrapping (```json ... ```)
      • Decimal or Hex color codes ("#5865F2", "0x5865F2", 5793266)
    """
    text = raw_input.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    text = text.strip()
    # Strip optional leading "json " or "discohook " keyword (e.g. `n!embed_studio json {...}`)
    text = re.sub(r"^(?:json|discohook)\s+", "", text, flags=re.IGNORECASE).strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON syntax: {e.msg} (line {e.lineno}, col {e.colno})")

    content: Optional[str] = None
    raw_embeds: list = []

    if isinstance(data, dict):
        content = data.get("content")
        if "embeds" in data and isinstance(data["embeds"], list):
            raw_embeds = data["embeds"]
        elif any(k in data for k in ("title", "description", "fields", "color", "author", "footer", "image", "thumbnail")):
            raw_embeds = [data]
        elif content:
            raw_embeds = []
        else:
            raise ValueError("Provided JSON does not contain any valid 'content' or 'embeds' fields.")
    elif isinstance(data, list):
        raw_embeds = data
    else:
        raise ValueError("JSON payload must be a JSON object or array of embed objects.")

    if not content and not raw_embeds:
        raise ValueError("The provided JSON does not contain any message content or embeds.")

    if content and len(content) > 2000:
        raise ValueError(f"Message content exceeds Discord's 2,000 character limit ({len(content)} chars).")

    embeds: List[discord.Embed] = []
    for idx, e in enumerate(raw_embeds[:10]):  # Discord allows up to 10 embeds per message
        if not isinstance(e, dict):
            continue
        cleaned = dict(e)

        # Normalize color
        if "color" in cleaned and cleaned["color"] is not None:
            c_val = cleaned["color"]
            if isinstance(c_val, str):
                c_clean = c_val.lstrip("#").replace("0x", "").strip()
                if re.fullmatch(r"[0-9a-fA-F]{1,6}", c_clean):
                    cleaned["color"] = int(c_clean, 16)
                else:
                    cleaned.pop("color", None)
            elif not isinstance(c_val, int):
                cleaned.pop("color", None)

        try:
            emb = discord.Embed.from_dict(cleaned)
            embeds.append(emb)
        except Exception as err:
            raise ValueError(f"Embed #{idx + 1} could not be parsed: {err}")

    # Discord total character limit across embeds is 6,000
    total_embed_chars = sum(len(e) for e in embeds)
    if total_embed_chars > 6000:
        raise ValueError(f"Total embed characters exceed Discord's 6,000 limit ({total_embed_chars} chars).")

    return content, embeds


# ── Modals ────────────────────────────────────────────────────────────────────

class EmbedEditorModal(discord.ui.Modal, title="🎨 Embed Visual Composer"):
    embed_title = discord.ui.TextInput(
        label="Embed Title",
        placeholder="e.g. 📢 Server Announcement / Official Guidelines",
        max_length=256,
        required=True,
    )
    embed_desc = discord.ui.TextInput(
        label="Description / Body (Markdown supported)",
        placeholder="Write your announcement body here...",
        style=discord.TextStyle.paragraph,
        max_length=3500,
        required=True,
    )
    embed_color = discord.ui.TextInput(
        label="Hex Color Code",
        placeholder="e.g. #5865F2, #FFB800, #00D2FF (or leave blank)",
        max_length=16,
        required=False,
    )
    embed_image = discord.ui.TextInput(
        label="Banner Image URL (Optional)",
        placeholder="https://example.com/banner.png",
        max_length=512,
        required=False,
    )
    embed_footer = discord.ui.TextInput(
        label="Footer Text (Optional)",
        placeholder="e.g. Nexora Community · Stay Awesome",
        max_length=256,
        required=False,
    )

    def __init__(self, original_embed: Optional[discord.Embed] = None, target_channel: Optional[discord.TextChannel] = None):
        super().__init__()
        self.target_channel = target_channel
        if original_embed:
            if original_embed.title:
                self.embed_title.default = original_embed.title
            if original_embed.description:
                self.embed_desc.default = original_embed.description
            if original_embed.color:
                self.embed_color.default = f"#{original_embed.color.value:06X}"
            if original_embed.image and original_embed.image.url:
                self.embed_image.default = original_embed.image.url
            if original_embed.footer and original_embed.footer.text:
                self.embed_footer.default = original_embed.footer.text

    async def on_submit(self, interaction: discord.Interaction):
        color_val = BRAND_COLOR
        if self.embed_color.value:
            clean = self.embed_color.value.lstrip("#").replace("0x", "").strip()
            if re.fullmatch(r"[0-9a-fA-F]{1,6}", clean):
                color_val = int(clean, 16)

        new_embed = discord.Embed(
            title=self.embed_title.value.strip(),
            description=self.embed_desc.value.strip(),
            color=color_val,
            timestamp=datetime.now(timezone.utc),
        )

        if self.embed_image.value and self.embed_image.value.strip().startswith("http"):
            new_embed.set_image(url=self.embed_image.value.strip())

        if self.embed_footer.value:
            new_embed.set_footer(text=self.embed_footer.value.strip())

        preview_view = EmbedPreviewView(
            requester=interaction.user,
            embeds=[new_embed],
            content=None,
            target_channel=self.target_channel,
        )

        await interaction.response.send_message(
            content="👀 **Embed Preview** (Visible only to you). Use the action buttons below to edit, import JSON, or dispatch:",
            embed=new_embed,
            view=preview_view,
            ephemeral=True,
        )


class EmbedJsonImportModal(discord.ui.Modal, title="📋 Import Discohook / Embed JSON"):
    json_data = discord.ui.TextInput(
        label="Discohook / Discord Embed JSON",
        placeholder='Paste raw JSON here, e.g. {"content": "Hello", "embeds": [{"title": "Rules"}]}',
        style=discord.TextStyle.paragraph,
        max_length=4000,
        required=True,
    )

    def __init__(self, requester: discord.abc.User, target_channel: Optional[discord.TextChannel] = None):
        super().__init__()
        self.requester = requester
        self.target_channel = target_channel

    async def on_submit(self, interaction: discord.Interaction):
        raw_text = self.json_data.value.strip()
        try:
            content, embeds = parse_discohook_json(raw_text)
        except ValueError as err:
            return await interaction.response.send_message(
                f"❌ **JSON Import Failed**:\n`{err}`\n\nPlease check your Discohook JSON syntax and try again.",
                ephemeral=True,
            )

        preview_view = EmbedPreviewView(
            requester=self.requester,
            embeds=embeds,
            content=content,
            target_channel=self.target_channel,
        )

        preview_text = "👀 **Discohook Import Preview** (Visible only to you). Review your announcement below and choose a channel:"
        if content:
            preview_text += f"\n\n**Message Content:**\n{content}"

        await interaction.response.send_message(
            content=preview_text,
            embeds=embeds if embeds else discord.utils.MISSING,
            view=preview_view,
            ephemeral=True,
        )


# ── Server-Scoped Channel Selector (Fixes cross-server channel bug) ───────────

class GuildChannelSelect(discord.ui.Select):
    """
    Explicitly populates options strictly from the interaction guild's text & news channels.
    Unlike native discord.ui.ChannelSelect (which relies on Discord client autocomplete and
    leaks channels across different servers), this is 100% server-scoped and guaranteed
    to ONLY show channels in the current guild.
    """

    def __init__(self, guild: discord.Guild, on_select_callback):
        self.on_select_callback = on_select_callback

        # Filter strictly to text & announcement channels in this guild
        accessible_channels = []
        for ch in guild.channels:
            if isinstance(ch, (discord.TextChannel, discord.VoiceChannel, discord.StageChannel)):
                # Must be a text-capable channel
                if isinstance(ch, discord.TextChannel):
                    perms = ch.permissions_for(guild.me)
                    if perms.send_messages and perms.embed_links:
                        accessible_channels.append(ch)

        # Sort announcement / news channels and high-priority channels first
        def channel_priority(c: discord.TextChannel):
            is_news = getattr(c, "is_news", lambda: False)()
            name = c.name.lower()
            is_priority = any(k in name for k in ("announc", "news", "update", "rule", "info", "general"))
            return (0 if is_news else 1, 0 if is_priority else 1, c.position)

        accessible_channels.sort(key=channel_priority)

        options: list[discord.SelectOption] = []
        for ch in accessible_channels[:25]:  # Discord select menu limit
            cat_name = f" [{ch.category.name}]" if ch.category else ""
            is_news = getattr(ch, "is_news", lambda: False)()
            emoji = "📢" if is_news else "💬"
            options.append(
                discord.SelectOption(
                    label=f"#{ch.name}"[:100],
                    value=str(ch.id),
                    description=f"ID: {ch.id}{cat_name}"[:100],
                    emoji=emoji,
                )
            )

        if not options:
            options.append(
                discord.SelectOption(
                    label="No accessible text channels found",
                    value="none",
                    description="Nexora needs Send Messages and Embed Links permissions.",
                )
            )

        super().__init__(
            placeholder="Select target channel in this server...",
            min_values=1,
            max_values=1,
            options=options,
        )

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0]
        if val == "none":
            return await interaction.response.send_message(
                "❌ No valid text channel could be selected. Please check Nexora's channel permissions.",
                ephemeral=True,
            )
        await self.on_select_callback(interaction, int(val))


class ChannelPickerView(discord.ui.View):
    def __init__(
        self,
        requester: discord.abc.User,
        guild: discord.Guild,
        content: Optional[str],
        embeds: List[discord.Embed],
    ):
        super().__init__(timeout=180)
        self.requester = requester
        self.guild = guild
        self.content = content
        self.embeds = embeds
        self.selected_channel: Optional[discord.TextChannel] = None

        self.select_menu = GuildChannelSelect(guild, self._on_channel_chosen)
        self.add_item(self.select_menu)

    async def _on_channel_chosen(self, interaction: discord.Interaction, channel_id: int):
        target = self.guild.get_channel(channel_id)
        if not target or not isinstance(target, discord.TextChannel):
            return await interaction.response.send_message("❌ Selected channel is invalid or unavailable.", ephemeral=True)

        perms = target.permissions_for(self.guild.me)
        if not perms.send_messages or not perms.embed_links:
            return await interaction.response.send_message(
                f"❌ I lack permission to send messages and embeds in {target.mention}!",
                ephemeral=True,
            )

        self.selected_channel = target

        # Dispatch announcement
        try:
            msg = await target.send(
                content=self.content,
                embeds=self.embeds if self.embeds else discord.utils.MISSING,
            )
            await interaction.response.send_message(
                f"🚀 **Embed successfully dispatched to {target.mention}!** [Jump to Message]({msg.jump_url})",
                ephemeral=True,
            )
        except Exception as e:
            logger.error("Failed to dispatch embed: %s", e)
            await interaction.response.send_message(f"❌ Failed to dispatch announcement: `{e}`", ephemeral=True)


# ── Embed Preview View ────────────────────────────────────────────────────────

class EmbedPreviewView(discord.ui.View):
    def __init__(
        self,
        requester: discord.abc.User,
        embeds: List[discord.Embed],
        content: Optional[str] = None,
        target_channel: Optional[discord.TextChannel] = None,
    ):
        super().__init__(timeout=300)
        self.requester = requester
        self.embeds = embeds
        self.content = content
        self.target_channel = target_channel

        if target_channel:
            self.btn_send.label = f"Send to #{target_channel.name}"[:80]

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            perms = interaction.user.guild_permissions
            if not (perms.administrator or perms.manage_guild or perms.manage_messages):
                await interaction.response.send_message("❌ This Embed Studio session belongs to someone else.", ephemeral=True)
                return False
        return True

    @discord.ui.button(label="Send to Channel", emoji="🚀", style=discord.ButtonStyle.success, row=0)
    async def btn_send(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.target_channel:
            # Send directly to the pre-specified channel
            perms = self.target_channel.permissions_for(interaction.guild.me)
            if not perms.send_messages or not perms.embed_links:
                return await interaction.response.send_message(
                    f"❌ I lack permission to send messages and embeds in {self.target_channel.mention}!",
                    ephemeral=True,
                )
            try:
                msg = await self.target_channel.send(
                    content=self.content,
                    embeds=self.embeds if self.embeds else discord.utils.MISSING,
                )
                return await interaction.response.send_message(
                    f"🚀 **Embed successfully dispatched to {self.target_channel.mention}!** [Jump to Message]({msg.jump_url})",
                    ephemeral=True,
                )
            except Exception as e:
                return await interaction.response.send_message(f"❌ Failed to dispatch: `{e}`", ephemeral=True)

        # Otherwise show the server-scoped channel picker
        channel_view = ChannelPickerView(
            requester=self.requester,
            guild=interaction.guild,
            content=self.content,
            embeds=self.embeds,
        )
        await interaction.response.send_message(
            "Select the channel in this server where you'd like to publish this announcement:",
            view=channel_view,
            ephemeral=True,
        )

    @discord.ui.button(label="Edit Visual", emoji="✏️", style=discord.ButtonStyle.primary, row=0)
    async def btn_edit(self, interaction: discord.Interaction, button: discord.ui.Button):
        first_embed = self.embeds[0] if self.embeds else None
        await interaction.response.send_modal(
            EmbedEditorModal(original_embed=first_embed, target_channel=self.target_channel)
        )

    @discord.ui.button(label="Import JSON", emoji="📋", style=discord.ButtonStyle.secondary, row=0)
    async def btn_import_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(
            EmbedJsonImportModal(requester=self.requester, target_channel=self.target_channel)
        )

    @discord.ui.button(label="Export JSON", emoji="📤", style=discord.ButtonStyle.secondary, row=0)
    async def btn_export_json(self, interaction: discord.Interaction, button: discord.ui.Button):
        payload = {
            "content": self.content,
            "embeds": [e.to_dict() for e in self.embeds],
        }
        raw_json = json.dumps(payload, indent=2, ensure_ascii=False)
        if len(raw_json) > 1900:
            raw_json = json.dumps(payload, ensure_ascii=False)[:1900]
        await interaction.response.send_message(
            f"📤 **Discohook-Compatible JSON Export:**\n```json\n{raw_json}\n```",
            ephemeral=True,
        )

    @discord.ui.button(label="Discard", emoji="🗑️", style=discord.ButtonStyle.danger, row=0)
    async def btn_discard(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()


# ── Embed Studio Cog ──────────────────────────────────────────────────────────

class EmbedStudio(commands.Cog):
    """Enterprise announcement and custom embed composer with Discohook JSON import."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="embed_studio",
        description="Craft, preview, import Discohook JSON, and publish embeds to any channel",
        aliases=["embed_builder", "discohook"],
    )
    @commands.check_any(
        commands.has_permissions(administrator=True),
        commands.has_permissions(manage_guild=True),
        commands.has_permissions(manage_messages=True),
    )
    @app_commands.default_permissions(manage_messages=True)
    @commands.guild_only()
    @app_commands.describe(
        channel="Optional target channel to send the embed to",
        json_code="Optional raw Discohook or Discord embed JSON string to import directly",
    )
    async def embed_studio(
        self,
        ctx: commands.Context,
        channel: Optional[discord.TextChannel] = None,
        *,
        json_code: Optional[str] = None,
    ):
        # 1. Check for file attachment (.json) if using prefix command
        if not json_code and ctx.message and ctx.message.attachments:
            att = ctx.message.attachments[0]
            if att.filename.endswith(".json") or att.content_type in ("application/json", "text/plain"):
                try:
                    raw_bytes = await att.read()
                    json_code = raw_bytes.decode("utf-8", errors="replace")
                except Exception as e:
                    return await ctx.send(f"❌ Failed to read JSON attachment: `{e}`", ephemeral=True)

        # 2. If JSON was provided, parse and launch preview immediately
        if json_code:
            try:
                content, embeds = parse_discohook_json(json_code)
            except ValueError as err:
                return await ctx.send(
                    f"❌ **Invalid Discohook JSON**:\n`{err}`\n\nPlease check your JSON syntax or use the interactive composer.",
                    ephemeral=True,
                )

            preview_view = EmbedPreviewView(
                requester=ctx.author,
                embeds=embeds,
                content=content,
                target_channel=channel,
            )

            preview_text = "👀 **Discohook Import Preview** (Visible only to you). Use the action buttons below to edit or dispatch:"
            if content:
                preview_text += f"\n\n**Message Content:**\n{content}"

            return await ctx.send(
                content=preview_text,
                embeds=embeds if embeds else discord.utils.MISSING,
                view=preview_view,
                ephemeral=True,
            )

        # 3. Display the Studio Launcher View (for both /embed_studio and n!embed_studio)
        launcher_view = discord.ui.View(timeout=300)
        selected_channel_box = {"channel": channel}

        btn_visual = discord.ui.Button(label="Visual Composer", emoji="🎨", style=discord.ButtonStyle.primary, row=0)
        btn_json = discord.ui.Button(label="Import Discohook JSON", emoji="📋", style=discord.ButtonStyle.success, row=0)

        async def visual_click(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                perms = interaction.user.guild_permissions
                if not (perms.administrator or perms.manage_guild or perms.manage_messages):
                    return await interaction.response.send_message("❌ This composer belongs to someone else.", ephemeral=True)
            await interaction.response.send_modal(EmbedEditorModal(target_channel=selected_channel_box["channel"]))

        async def json_click(interaction: discord.Interaction):
            if interaction.user.id != ctx.author.id:
                perms = interaction.user.guild_permissions
                if not (perms.administrator or perms.manage_guild or perms.manage_messages):
                    return await interaction.response.send_message("❌ This composer belongs to someone else.", ephemeral=True)
            await interaction.response.send_modal(
                EmbedJsonImportModal(requester=interaction.user, target_channel=selected_channel_box["channel"])
            )

        btn_visual.callback = visual_click
        btn_json.callback = json_click

        launcher_view.add_item(btn_visual)
        launcher_view.add_item(btn_json)

        target_str = f"\n📍 **Target Channel:** {channel.mention}" if channel else "\n📍 **Target Channel:** *Select after previewing (or pass `channel:`)*"
        studio_embed = discord.Embed(
            title="🛠️ Nexora Embed & Announcement Studio",
            description=(
                "Create, preview, and publish custom Discord announcements and multi-embed layouts.\n"
                f"{target_str}\n\n"
                "**Choose a workflow below:**\n"
                "🎨 **Visual Composer** — Interactive form for Title, Description, Hex Color, Banner Image, and Footer.\n"
                "📋 **Import Discohook JSON** — Paste raw JSON (multi-line or single-line) from Discohook or any embed generator."
            ),
            color=BRAND_COLOR,
        )
        studio_embed.set_footer(text="Nexora Studio • Live Ephemeral Preview & Server-Scoped Channel Picker")

        await ctx.send(
            embed=studio_embed,
            view=launcher_view,
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(EmbedStudio(bot))
    logger.debug("Loaded EmbedStudio Cog")

"""
utils/ui.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nexora Unified Components V2 Design System
Built for discord.py >= 2.7.1 Components V2 (LayoutView, Container,
Section, TextDisplay, Separator, Thumbnail, ActionRow).

Provides a premium, consistent visual language across all Nexora commands:
  • NexoraView: Reusable Components V2 view with author check & timeout handling
  • NexoraCardView: Universal LayoutView renderer with rich formatting
  • send_view(): Universal dispatcher for Context & Interaction
  • UI Utilities: progress bars, latency badges, status indicators, timestamps
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Union, Sequence

import discord
from discord.ext import commands

logger = logging.getLogger(__name__)

# ── Color Palette ─────────────────────────────────────────────────────────────
BRAND_COLOR   = 0x5865F2  # Nexora Blurple
CYAN_COLOR    = 0x00D2FF  # Diagnostic / Info Cyan
SUCCESS_COLOR = 0x57F287  # Green
WARNING_COLOR = 0xFEE75C  # Amber
ERROR_COLOR   = 0xED4245  # Crimson
PREMIUM_COLOR = 0xFFB800  # Gold
PURPLE_COLOR  = 0x9B59B6  # Royal Violet
DARK_COLOR    = 0x2B2D31  # Charcoal

SEPARATOR_LINE = "━━━━━━━━━━━━━━━━━━━━━━━━"


def cfg_color(bot, key: str, fallback: int = BRAND_COLOR) -> int:
    """Retrieve color from bot config or return fallback."""
    try:
        raw = bot.bot_config["ui_settings"][key]
        return int(raw, 16) if isinstance(raw, str) else int(raw)
    except Exception:
        return fallback


# ── Visual Helpers ────────────────────────────────────────────────────────────

def progress_bar(
    val: Union[int, float],
    max_val: Union[int, float] = 100.0,
    length: int = 10,
    filled: str = "▰",
    empty: str = "▱",
) -> str:
    """Render a sleek unicode progress bar."""
    if max_val <= 0:
        pct = 0.0
    else:
        pct = max(0.0, min(1.0, float(val) / float(max_val)))
    fill_count = int(round(pct * length))
    empty_count = length - fill_count
    return f"{filled * fill_count}{empty * empty_count}"


def latency_badge(ms: float) -> str:
    """Return a styled latency indicator with status color."""
    if ms < 90:
        return f"🟢 **{ms:.1f}ms** · Excellent"
    elif ms < 180:
        return f"🟡 **{ms:.1f}ms** · Good"
    elif ms < 300:
        return f"🟠 **{ms:.1f}ms** · Moderate"
    else:
        return f"🔴 **{ms:.1f}ms** · High Latency"


def status_badge(status: discord.Status) -> str:
    """Map Discord status to emoji and title."""
    mapping = {
        discord.Status.online: "🟢 Online",
        discord.Status.idle: "🟡 Idle",
        discord.Status.dnd: "🔴 Do Not Disturb",
        discord.Status.do_not_disturb: "🔴 Do Not Disturb",
        discord.Status.offline: "⚪ Offline",
        discord.Status.invisible: "⚪ Invisible",
    }
    return mapping.get(status, "⚪ Unknown")


def ts_format(dt: Optional[datetime], fmt: str = "R") -> str:
    """Format datetime into Discord dynamic timestamp."""
    if not dt:
        return "Unknown"
    ts = int(dt.timestamp())
    return f"<t:{ts}:{fmt}>"


def limit_text(text: str, limit: int = 3900) -> str:
    """Safely clamp text length for Discord UI displays."""
    text = text or ""
    return text if len(text) <= limit else text[:limit - 1] + "…"


# ── Base LayoutView ───────────────────────────────────────────────────────────

class NexoraView(discord.ui.LayoutView):
    """
    Standard Components V2 LayoutView shell for Nexora.
    Manages an accent-colored container, permission restrictions,
    and automatic button deactivation upon timeout.
    """

    def __init__(
        self,
        *,
        bot: Optional[commands.Bot] = None,
        user_id: Optional[int] = None,
        color: int = BRAND_COLOR,
        timeout: Optional[float] = 180,
    ):
        super().__init__(timeout=timeout)
        self.bot = bot
        self.user_id = user_id
        self._color = color
        self.message: Optional[Union[discord.Message, discord.WebhookMessage]] = None

        self.container = discord.ui.Container(accent_colour=color)
        self.add_item(self.container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if self.user_id is not None and interaction.user.id != self.user_id:
            await interaction.response.send_message(
                "❌ This panel belongs to someone else. Run the command to open your own.",
                ephemeral=True,
            )
            return False
        return True

    def clear_container(self):
        self.container.clear_items()

    def add_text(self, text: str):
        """Append a TextDisplay to the container."""
        self.container.add_item(discord.ui.TextDisplay(limit_text(text)))

    def add_section(self, text: str, thumbnail_url: Optional[str] = None):
        """Append a section with optional thumbnail accessory."""
        display = discord.ui.TextDisplay(limit_text(text))
        if thumbnail_url:
            self.container.add_item(
                discord.ui.Section(display, accessory=discord.ui.Thumbnail(thumbnail_url))
            )
        else:
            self.container.add_item(display)

    def add_separator(self, spacing: discord.SeparatorSpacing = discord.SeparatorSpacing.small):
        """Append a hairline divider."""
        self.container.add_item(discord.ui.Separator(spacing=spacing))

    def add_row(self, *items):
        """Wrap interactive items (buttons, selects) in an ActionRow and append."""
        row = discord.ui.ActionRow()
        for item in items:
            row.add_item(item)
        self.container.add_item(row)
        return row

    def add_footer(self, text: str):
        """Append a clean subtext footer."""
        self.add_separator(discord.SeparatorSpacing.small)
        self.container.add_item(discord.ui.TextDisplay(f"-# {text}"))

    async def on_timeout(self):
        """Disable all interactive components when the view times out."""
        for item in self.container.children:
            if isinstance(item, discord.ui.ActionRow):
                for child in item.children:
                    if hasattr(child, "disabled"):
                        child.disabled = True
        try:
            if self.message:
                await self.message.edit(view=self)
        except Exception:
            pass


# ── Universal Card View (Drop-in for Embeds) ──────────────────────────────────

class NexoraCardView(NexoraView):
    """
    Renders any structured content or legacy discord.Embed as a sleek Components V2 Card.
    """

    def __init__(
        self,
        *,
        title: Optional[str] = None,
        description: Optional[str] = None,
        color: int = BRAND_COLOR,
        thumbnail_url: Optional[str] = None,
        fields: Optional[Sequence[tuple[str, str, bool]]] = None,
        footer_text: Optional[str] = None,
        bot: Optional[commands.Bot] = None,
        user_id: Optional[int] = None,
        timeout: float = 180,
    ):
        super().__init__(bot=bot, user_id=user_id, color=color, timeout=timeout)
        self._build_card(
            title=title,
            description=description,
            thumbnail_url=thumbnail_url,
            fields=fields or [],
            footer_text=footer_text,
        )

    def _build_card(self, title, description, thumbnail_url, fields, footer_text):
        self.clear_container()

        header_lines = []
        if title:
            header_lines.append(f"# {title}")
        if description:
            header_lines.append(f"{description}")

        header_content = "\n\n".join(header_lines) or "\u200b"
        self.add_section(header_content, thumbnail_url=thumbnail_url)

        if fields:
            self.add_separator(discord.SeparatorSpacing.small)
            field_texts = []
            for name, val, _ in fields:
                field_texts.append(f"### {name}\n{val}")
            self.add_text("\n\n".join(field_texts))

        if footer_text:
            self.add_footer(footer_text)

    @classmethod
    def from_embed(
        cls,
        embed: discord.Embed,
        *,
        bot: Optional[commands.Bot] = None,
        user_id: Optional[int] = None,
        timeout: float = 180,
    ) -> "NexoraCardView":
        """Convert a discord.Embed into a Components V2 NexoraCardView."""
        color = getattr(embed, "color", None)
        color_val = color.value if color and hasattr(color, "value") and color.value else BRAND_COLOR
        thumb = getattr(getattr(embed, "thumbnail", None), "url", None)
        fields = [(f.name, f.value, f.inline) for f in (embed.fields or [])]
        footer = getattr(getattr(embed, "footer", None), "text", None)

        return cls(
            title=embed.title,
            description=embed.description,
            color=color_val,
            thumbnail_url=thumb,
            fields=fields,
            footer_text=footer,
            bot=bot,
            user_id=user_id,
            timeout=timeout,
        )


# ── Universal Dispatcher ──────────────────────────────────────────────────────

async def send_view(
    target: Union[commands.Context, discord.Interaction, discord.TextChannel],
    view: discord.ui.LayoutView,
    *,
    ephemeral: bool = False,
) -> Optional[Union[discord.Message, discord.WebhookMessage]]:
    """
    Universally sends a Components V2 LayoutView whether invoked from:
      • commands.Context (hybrid slash or prefix)
      • discord.Interaction (deferred, immediate, followup)
      • discord.abc.Messageable
    Automatically binds view.message to the resulting message object.
    """
    msg = None
    try:
        if isinstance(target, discord.Interaction):
            if target.response.is_done():
                msg = await target.followup.send(view=view, ephemeral=ephemeral)
            else:
                await target.response.send_message(view=view, ephemeral=ephemeral)
                try:
                    msg = await target.original_response()
                except Exception:
                    msg = None
        elif isinstance(target, commands.Context):
            if target.interaction:
                if target.interaction.response.is_done():
                    msg = await target.interaction.followup.send(view=view, ephemeral=ephemeral)
                else:
                    await target.interaction.response.send_message(view=view, ephemeral=ephemeral)
                    try:
                        msg = await target.interaction.original_response()
                    except Exception:
                        msg = None
            else:
                msg = await target.send(view=view)
        else:
            msg = await target.send(view=view)
    except Exception as exc:
        logger.error("Error sending Components V2 view: %s", exc)
        raise exc

    if msg and hasattr(view, "message"):
        view.message = msg
    return msg


# ── Common Interactive Components ─────────────────────────────────────────────

class DismissButton(discord.ui.Button):
    """Clean secondary button that deletes/dismisses the view if invoked by author."""

    def __init__(self, user_id: Optional[int] = None, label: str = "Dismiss"):
        super().__init__(
            label=label,
            emoji="🗑️",
            style=discord.ButtonStyle.secondary,
        )
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if self.user_id and interaction.user.id != self.user_id:
            await interaction.response.send_message("❌ Only the command invoker can dismiss this.", ephemeral=True)
            return
        try:
            await interaction.message.delete()
        except Exception:
            try:
                await interaction.response.edit_message(view=None)
            except Exception:
                pass

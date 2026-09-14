"""
cogs/moderation/mod_utils.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nexora Components V2 Moderation Engine & Utilities
  • Duration parsing & formatting
  • Expiry timestamps
  • ModCardView: Components V2 action card
  • ModConfirmLayoutView: Components V2 confirmation dialog
  • Role hierarchy & safety checks
  • DM dispatchers
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Optional, Union

import discord
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    NexoraView,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)

# ── Duration parser ────────────────────────────────────────────────────────────

_DUR_RE = re.compile(
    r"(?:(\d+)\s*d(?:ays?)?)?"
    r"(?:(\d+)\s*h(?:ours?)?)?"
    r"(?:(\d+)\s*m(?:in(?:utes?)?)?)?"
    r"(?:(\d+)\s*s(?:ec(?:onds?)?)?)?",
    re.IGNORECASE,
)


def parse_duration(text: str) -> Optional[timedelta]:
    """Parse a human duration string into a timedelta (e.g., 30m, 2h, 1d, 7d)."""
    m = _DUR_RE.fullmatch(text.strip())
    if not m or not any(m.groups()):
        return None
    td = timedelta(
        days=int(m.group(1) or 0),
        hours=int(m.group(2) or 0),
        minutes=int(m.group(3) or 0),
        seconds=int(m.group(4) or 0),
    )
    return td if td.total_seconds() > 0 else None


def fmt_duration(td: timedelta) -> str:
    """Convert timedelta into readable '2d 4h 30m' string."""
    total = int(td.total_seconds())
    days, r = divmod(total, 86400)
    hours, r = divmod(r, 3600)
    minutes, seconds = divmod(r, 60)
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds and not days:
        parts.append(f"{seconds}s")
    return " ".join(parts) or "0s"


def expiry_ts(td: timedelta) -> str:
    """Return relative + absolute dynamic Discord timestamps."""
    ts = int((datetime.now(timezone.utc) + td).timestamp())
    return f"<t:{ts}:R> (<t:{ts}:f>)"


# ── DM helper ──────────────────────────────────────────────────────────────────

async def try_dm(member: discord.Member, embed_or_view: Union[discord.Embed, discord.ui.LayoutView]) -> bool:
    """Send embed or Components V2 view to target via DM. Returns False if blocked."""
    try:
        if isinstance(embed_or_view, discord.ui.LayoutView):
            await member.send(view=embed_or_view)
        else:
            await member.send(embed=embed_or_view)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


# ── Hierarchy safety check ─────────────────────────────────────────────────────

def can_action(ctx_member: discord.Member, target: Union[discord.Member, discord.User]) -> Optional[str]:
    """Check hierarchy rules. Returns error message or None if safe."""
    if target.id == ctx_member.id:
        return "❌ You cannot perform moderation actions on yourself."
    if target.id == ctx_member.guild.owner_id:
        return "❌ You cannot perform moderation actions on the server owner."
    if target.id == ctx_member.guild.me.id:
        return "❌ I cannot moderate myself."

    # If target is a member in the guild, enforce role hierarchy
    if isinstance(target, discord.Member):
        if target.bot and ctx_member.guild.owner_id != ctx_member.id and target.top_role >= ctx_member.top_role:
            return "❌ You cannot moderate a bot with equal or higher role than you."
        if target.top_role >= ctx_member.top_role and ctx_member.guild.owner_id != ctx_member.id:
            return "❌ That member has an equal or higher role than you."
        guild_me = ctx_member.guild.me
        if target.top_role >= guild_me.top_role:
            return "❌ I cannot moderate that member — their role is higher than mine."
    return None


# ── Mod Card Colors & Emojis ──────────────────────────────────────────────────

ACTION_CONFIG = {
    "ban":      {"color": 0xED4245, "emoji": "🔨", "title": "Member Banned"},
    "unban":    {"color": 0x57F287, "emoji": "🔓", "title": "User Unbanned"},
    "softban":  {"color": 0xE74C3C, "emoji": "🧹", "title": "Member Softbanned"},
    "tempban":  {"color": 0xE67E22, "emoji": "⏱️", "title": "Member Temp-Banned"},
    "kick":     {"color": 0xFF9F1C, "emoji": "👢", "title": "Member Kicked"},
    "mute":     {"color": 0x5865F2, "emoji": "🔇", "title": "Member Timed Out"},
    "unmute":   {"color": 0x57F287, "emoji": "🔊", "title": "Timeout Removed"},
    "warn":     {"color": 0xFEE75C, "emoji": "⚠️", "title": "Member Warned"},
    "delwarn":  {"color": 0x57F287, "emoji": "🗑️", "title": "Warning Deleted"},
    "lock":     {"color": 0xED4245, "emoji": "🔒", "title": "Channel Locked"},
    "unlock":   {"color": 0x57F287, "emoji": "🔓", "title": "Channel Unlocked"},
    "slowmode": {"color": 0x5865F2, "emoji": "🐢", "title": "Slowmode Configured"},
    "purge":    {"color": 0x00D2FF, "emoji": "🧹", "title": "Messages Purged"},
}


# ── Components V2 Mod Action View ─────────────────────────────────────────────

class ModActionView(NexoraView):
    """Modern Components V2 card confirming a completed moderation action."""

    def __init__(
        self,
        action: str,
        target: Union[discord.Member, discord.User],
        moderator: discord.abc.User,
        reason: str,
        *,
        duration: Optional[timedelta] = None,
        extra: Optional[str] = None,
        timeout: float = 180,
    ):
        cfg = ACTION_CONFIG.get(action.lower(), {"color": BRAND_COLOR, "emoji": "⚙️", "title": action.title()})
        super().__init__(user_id=moderator.id, color=cfg["color"], timeout=timeout)
        self.action = action
        self.target = target
        self.moderator = moderator
        self.reason = reason
        self.duration = duration
        self.extra = extra
        self._build()

    def _build(self):
        self.clear_container()
        cfg = ACTION_CONFIG.get(self.action.lower(), {"emoji": "⚙️", "title": self.action.title()})

        header = (
            f"# {cfg['emoji']} {cfg['title']}\n"
            f"> Target: **@{self.target.name}** ({self.target.mention}) · ID: `{self.target.id}`\n"
            f"🛡️ **Moderator:** {self.moderator.mention}"
        )
        avatar_url = str(self.target.display_avatar.url)
        self.add_section(header, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        details = [f"• **Reason:**\n  > {self.reason or 'No reason provided.'}"]
        if self.duration:
            details.append(f"• **Duration:** `{fmt_duration(self.duration)}`")
            details.append(f"• **Expires:** {expiry_ts(self.duration)}")
        if self.extra:
            details.append(f"• **Note:** {self.extra}")

        self.add_text("### 📋 Action Audit\n" + "\n".join(details))
        self.add_footer("Nexora Moderation Engine · Audit record logged")


# ── Components V2 Confirmation View ───────────────────────────────────────────

class ModConfirmLayoutView(NexoraView):
    """
    Components V2 prompt asking the moderator to confirm an action.
    """

    def __init__(
        self,
        action: str,
        target: Union[discord.Member, discord.User],
        moderator: discord.abc.User,
        reason: str,
        *,
        details: Optional[str] = None,
        timeout: float = 30.0,
    ):
        cfg = ACTION_CONFIG.get(action.lower(), {"color": WARNING_COLOR, "emoji": "⚠️"})
        super().__init__(user_id=moderator.id, color=cfg["color"], timeout=timeout)
        self.action = action
        self.target = target
        self.moderator = moderator
        self.reason = reason
        self.details = details
        self.confirmed: Optional[bool] = None
        self._build()

    def _build(self):
        self.clear_container()
        cfg = ACTION_CONFIG.get(self.action.lower(), {"emoji": "⚠️"})

        header = (
            f"# {cfg['emoji']} Confirm {self.action.title()}\n"
            f"> Are you sure you want to **{self.action}** {self.target.mention}?\n"
            f"Target: `{self.target}` ({self.target.id})"
        )
        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        body_lines = [f"• **Reason:** {self.reason}"]
        if self.details:
            body_lines.append(f"• **Details:** {self.details}")
        body_lines.append("• **Timeout:** This prompt automatically cancels in 30 seconds.")

        self.add_text("### ⚠️ Caution Required\n" + "\n".join(body_lines))

        btn_confirm = discord.ui.Button(
            label=f"Confirm {self.action.title()}",
            emoji="✅",
            style=discord.ButtonStyle.danger,
            custom_id="mod-confirm",
        )
        btn_cancel = discord.ui.Button(
            label="Cancel",
            emoji="✖",
            style=discord.ButtonStyle.secondary,
            custom_id="mod-cancel",
        )

        btn_confirm.callback = self._on_confirm
        btn_cancel.callback = self._on_cancel

        self.add_row(btn_confirm, btn_cancel)

    async def _on_confirm(self, interaction: discord.Interaction):
        self.confirmed = True
        self.stop()

    async def _on_cancel(self, interaction: discord.Interaction):
        self.confirmed = False
        self.clear_container()
        self.add_text(
            f"# ✖ Action Cancelled\n"
            f"> The **{self.action}** action for {self.target.mention} was cancelled by {self.moderator.mention}."
        )
        self.add_footer("Nexora Moderation · No punishment applied")
        await interaction.response.edit_message(view=self)
        self.stop()

    async def on_timeout(self):
        if self.confirmed is None:
            self.confirmed = False
            self.clear_container()
            self.add_text(
                f"# ⏱️ Confirmation Timed Out\n"
                f"> The prompt to {self.action} {self.target.mention} expired."
            )
            self.add_footer("Nexora Moderation · Action aborted")
            try:
                if self.message:
                    await self.message.edit(view=self)
            except Exception:
                pass


# ── Backwards-Compatible Embed Helpers ────────────────────────────────────────

def mod_embed(
    action: str,
    target: discord.Member,
    moderator: discord.Member,
    reason: str,
    *,
    duration: Optional[timedelta] = None,
    extra: Optional[str] = None,
) -> discord.Embed:
    """Build legacy embed for backwards compatibility."""
    cfg = ACTION_CONFIG.get(action, {"color": BRAND_COLOR, "emoji": "⚙️", "title": action.title()})
    embed = discord.Embed(
        title=f"{cfg['emoji']} {cfg['title']}",
        color=discord.Color(cfg["color"]),
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="👤 User", value=f"{target.mention}\n`{target}` ({target.id})", inline=True)
    embed.add_field(name="🛡️ Moderator", value=f"{moderator.mention}", inline=True)
    if duration:
        embed.add_field(name="⏱️ Duration", value=fmt_duration(duration), inline=True)
        embed.add_field(name="🕐 Expires", value=expiry_ts(duration), inline=False)
    embed.add_field(name="📋 Reason", value=reason or "No reason provided.", inline=False)
    if extra:
        embed.add_field(name="ℹ️ Note", value=extra, inline=False)
    return embed


def dm_embed(
    action: str,
    guild: discord.Guild,
    moderator: discord.Member,
    reason: str,
    *,
    duration: Optional[timedelta] = None,
) -> discord.Embed:
    """DM embed sent to offender."""
    cfg = ACTION_CONFIG.get(action, {"color": BRAND_COLOR, "emoji": "⚙️", "title": action.title()})
    lines = [
        f"**Server:** {guild.name}",
        f"**Moderator:** {moderator}",
        f"**Reason:** {reason or 'No reason provided.'}",
    ]
    if duration:
        lines.append(f"**Duration:** {fmt_duration(duration)}")
        lines.append(f"**Expires:** {expiry_ts(duration)}")

    embed = discord.Embed(
        title=f"{cfg['emoji']} You have received a {action.title()}",
        description="\n".join(lines),
        color=discord.Color(cfg["color"]),
        timestamp=datetime.now(timezone.utc),
    )
    if guild.icon:
        embed.set_thumbnail(url=guild.icon.url)
    return embed


class ConfirmView(discord.ui.View):
    """Legacy confirm view."""

    def __init__(self, allowed_user_id: int, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.allowed_user_id = allowed_user_id
        self.confirmed: Optional[bool] = None

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.allowed_user_id:
            await interaction.response.send_message("❌ Not your action.", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="Confirm", style=discord.ButtonStyle.danger, emoji="✅")
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = True
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.secondary, emoji="✖")
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.confirmed = False
        for c in self.children:
            c.disabled = True
        await interaction.response.edit_message(view=self)
        self.stop()


# ── Server Audit Log Dispatcher ──────────────────────────────────────────────

async def log_mod_action(
    guild: discord.Guild,
    action: str,
    target: Union[discord.Member, discord.User, discord.abc.GuildChannel, str],
    moderator: discord.abc.User,
    reason: str,
    *,
    duration: Optional[timedelta] = None,
    extra: Optional[str] = None,
    bot: Optional[commands.Bot] = None,
):
    """
    Dispatches a moderation audit log embed to the guild's log channel if one exists.
    Checks explicit configuration and standard auto-detect names (#mod-logs, etc.).
    Fails silently if no channel exists or permissions are missing.
    """
    if not guild:
        return

    log_channel = None

    # 1. Try finding channel via ServerLogs cog
    if bot:
        server_logs_cog = bot.get_cog("ServerLogs")
        if server_logs_cog and hasattr(server_logs_cog, "get_log_channel"):
            try:
                log_channel = await server_logs_cog.get_log_channel(guild)
            except Exception as e:
                logger.debug("Error querying ServerLogs cog: %s", e)

    # 2. Fallback auto-detection by name if cog wasn't available
    if not log_channel:
        standard_names = {
            "mod-logs", "mod-log", "modlog", "modlogs",
            "server-logs", "server-log", "audit-logs", "audit-log",
            "bot-logs", "bot-log", "logs",
        }
        for ch in guild.text_channels:
            if ch.name.lower().replace("_", "-").strip() in standard_names:
                perms = ch.permissions_for(guild.me)
                if perms.send_messages and perms.embed_links:
                    log_channel = ch
                    break

    if not log_channel:
        return

    cfg = ACTION_CONFIG.get(action.lower(), {"color": BRAND_COLOR, "emoji": "🛡️", "title": action.title()})
    embed = discord.Embed(
        title=f"{cfg['emoji']} Moderation Audit: {cfg['title']}",
        color=discord.Color(cfg["color"]),
        timestamp=datetime.now(timezone.utc),
    )

    if isinstance(target, (discord.Member, discord.User)):
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.add_field(name="👤 Target", value=f"{target.mention}\n`{target}` ({target.id})", inline=True)
    elif isinstance(target, discord.abc.GuildChannel):
        embed.add_field(name="📍 Channel", value=f"{target.mention}\n`#{target.name}` ({target.id})", inline=True)
    else:
        embed.add_field(name="🎯 Subject", value=str(target), inline=True)

    embed.add_field(name="🛡️ Moderator", value=f"{moderator.mention}\n`{moderator}`", inline=True)

    if duration:
        embed.add_field(name="⏱️ Duration", value=fmt_duration(duration), inline=True)
        embed.add_field(name="🕐 Expires", value=expiry_ts(duration), inline=False)

    embed.add_field(name="📋 Reason", value=reason or "No reason provided.", inline=False)

    if extra:
        embed.add_field(name="ℹ️ Details", value=extra, inline=False)

    embed.set_footer(text=f"Nexora Moderation Audit · {guild.name}")

    try:
        await log_channel.send(embed=embed)
    except Exception as exc:
        logger.debug("Failed to dispatch mod log to #%s in guild %s: %s", log_channel.name, guild.id, exc)
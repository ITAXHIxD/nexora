"""
cogs/moderation/mod_utils.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Shared utilities used by all moderation cogs:
  • parse_duration()   — "1d2h30m" → timedelta
  • fmt_duration()     — timedelta → "2d 4h 30m"
  • expiry_ts()        — returns Discord <t:...> timestamp string
  • try_dm()           — sends a DM, silently ignores if blocked
  • ConfirmView        — two-button confirm/cancel with timeout
  • mod_embed()        — standardised action embed
  • can_action()       — role hierarchy safety check
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import re
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord.ext import commands

# ── Duration parser ────────────────────────────────────────────────────────────

_DUR_RE = re.compile(
    r"(?:(\d+)\s*d(?:ays?)?)?"
    r"(?:(\d+)\s*h(?:ours?)?)?"
    r"(?:(\d+)\s*m(?:in(?:utes?)?)?)?"
    r"(?:(\d+)\s*s(?:ec(?:onds?)?)?)?",
    re.IGNORECASE,
)

def parse_duration(text: str) -> Optional[timedelta]:
    """
    Parse a human duration string into a timedelta.
    Accepts: 30m  2h  1d  1h30m  7d  10s  2d12h  etc.
    Returns None if the string is zero-length or unrecognised.
    """
    m = _DUR_RE.fullmatch(text.strip())
    if not m or not any(m.groups()):
        return None
    td = timedelta(
        days    = int(m.group(1) or 0),
        hours   = int(m.group(2) or 0),
        minutes = int(m.group(3) or 0),
        seconds = int(m.group(4) or 0),
    )
    return td if td.total_seconds() > 0 else None


def fmt_duration(td: timedelta) -> str:
    """Convert a timedelta to a readable string like '2d 4h 30m'."""
    total   = int(td.total_seconds())
    days, r = divmod(total, 86400)
    hours, r = divmod(r, 3600)
    minutes, seconds = divmod(r, 60)
    parts = []
    if days:    parts.append(f"{days}d")
    if hours:   parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    if seconds and not days: parts.append(f"{seconds}s")
    return " ".join(parts) or "0s"


def expiry_ts(td: timedelta) -> str:
    """Return a Discord relative + absolute timestamp for now + td."""
    ts = int((datetime.now(timezone.utc) + td).timestamp())
    return f"<t:{ts}:R>  (<t:{ts}:f>)"


# ── DM helper ──────────────────────────────────────────────────────────────────

async def try_dm(member: discord.Member, embed: discord.Embed) -> bool:
    """Send embed to member via DM. Returns True on success, False if blocked."""
    try:
        await member.send(embed=embed)
        return True
    except (discord.Forbidden, discord.HTTPException):
        return False


# ── Hierarchy safety check ─────────────────────────────────────────────────────

def can_action(ctx_member: discord.Member, target: discord.Member) -> Optional[str]:
    """
    Return an error string if the action is unsafe, or None if it's fine.
    Checks: targeting self, targeting bot, role hierarchy.
    """
    if target == ctx_member:
        return "❌ You can't do that to yourself."
    if target.bot:
        return "❌ You can't moderate a bot."
    if target.top_role >= ctx_member.top_role and ctx_member.guild.owner_id != ctx_member.id:
        return "❌ That member has an equal or higher role than you."
    guild_me = ctx_member.guild.me
    if target.top_role >= guild_me.top_role:
        return "❌ I can't moderate that member — their role is higher than mine."
    return None


# ── Standard mod action embed ──────────────────────────────────────────────────

ACTION_COLORS = {
    "ban":     discord.Color.from_rgb(220, 50,  50),
    "tempban": discord.Color.from_rgb(220, 100, 50),
    "kick":    discord.Color.from_rgb(220, 160, 50),
    "mute":    discord.Color.from_rgb(100, 100, 220),
    "unmute":  discord.Color.from_rgb(50,  200, 100),
}

ACTION_EMOJIS = {
    "ban":     "🔨",
    "tempban": "⏱️",
    "kick":    "👢",
    "mute":    "🔇",
    "unmute":  "🔊",
}

def mod_embed(
    action: str,
    target: discord.Member,
    moderator: discord.Member,
    reason: str,
    *,
    duration: Optional[timedelta] = None,
    extra: Optional[str] = None,
) -> discord.Embed:
    """Build the standardised moderation action embed."""
    color = ACTION_COLORS.get(action, discord.Color.blurple())
    emoji = ACTION_EMOJIS.get(action, "⚙️")
    label = action.replace("temp", "Temp-").title()

    embed = discord.Embed(
        title=f"{emoji} {label}",
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=target.display_avatar.url)
    embed.add_field(name="👤 User",       value=f"{target.mention}\n`{target}` ({target.id})", inline=True)
    embed.add_field(name="🛡️ Moderator", value=f"{moderator.mention}",                         inline=True)

    if duration:
        embed.add_field(name="⏱️ Duration", value=fmt_duration(duration), inline=True)
        embed.add_field(name="🕐 Expires",  value=expiry_ts(duration),    inline=False)

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
    """Embed sent to the target via DM."""
    color = ACTION_COLORS.get(action, discord.Color.blurple())
    emoji = ACTION_EMOJIS.get(action, "⚙️")
    label = action.replace("temp", "Temp-").title()

    lines = [
        f"**Server:** {guild.name}",
        f"**Moderator:** {moderator}",
        f"**Reason:** {reason or 'No reason provided.'}",
    ]
    if duration:
        lines.append(f"**Duration:** {fmt_duration(duration)}")
        lines.append(f"**Expires:** {expiry_ts(duration)}")

    embed = discord.Embed(
        title=f"{emoji} You have been {label}ed",
        description="\n".join(lines),
        color=color,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=guild.icon.url if guild.icon else None)
    return embed


# ── Confirmation view ──────────────────────────────────────────────────────────

class ConfirmView(discord.ui.View):
    """
    Reusable confirm / cancel view.

    Usage:
        view = ConfirmView(moderator_id)
        msg  = await ctx.send(embed=confirm_embed, view=view)
        await view.wait()
        if not view.confirmed:
            return  # cancelled or timed out
    """

    def __init__(self, allowed_user_id: int, timeout: float = 30.0):
        super().__init__(timeout=timeout)
        self.allowed_user_id = allowed_user_id
        self.confirmed: Optional[bool] = None
        self.interaction: Optional[discord.Interaction] = None

    async def _check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.allowed_user_id:
            await interaction.response.send_message(
                "❌ Only the moderator who ran this command can confirm it.",
                ephemeral=True,
            )
            return False
        return True

    @discord.ui.button(label="✅  Confirm", style=discord.ButtonStyle.danger)
    async def confirm(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        self.confirmed   = True
        self.interaction = interaction
        self._disable_all()
        await interaction.response.edit_message(view=self)
        self.stop()

    @discord.ui.button(label="✖  Cancel", style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not await self._check(interaction):
            return
        self.confirmed   = False
        self.interaction = interaction
        self._disable_all()
        await interaction.response.edit_message(view=self)
        self.stop()

    def _disable_all(self):
        for item in self.children:
            item.disabled = True

    async def on_timeout(self):
        self.confirmed = False
        self._disable_all()
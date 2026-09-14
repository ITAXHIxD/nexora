"""
cogs/info/channelinfo.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Channel Inspector Card
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    NexoraView,
    DismissButton,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)


class ChannelInfoView(NexoraView):
    """Components V2 channel specification card."""

    def __init__(
        self,
        channel: discord.abc.GuildChannel,
        requester: discord.abc.User,
        timeout: float = 180,
    ):
        super().__init__(user_id=requester.id, color=BRAND_COLOR, timeout=timeout)
        self.channel = channel
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()
        c = self.channel
        guild = c.guild

        # Formatting type and category
        chan_type = str(c.type).replace("_", " ").title()
        category_name = c.category.name if getattr(c, "category", None) else "None"
        icon_url = str(guild.icon.url) if guild.icon else None

        # ── Header Section ────────────────────────────────────────────────────
        header_text = (
            f"# 📝 #{c.name}\n"
            f"> Category: **{category_name}** · Type: **{chan_type}**\n"
            f"Created {ts_format(c.created_at, 'D')} ({ts_format(c.created_at, 'R')})"
        )
        self.add_section(header_text, thumbnail_url=icon_url)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── Channel Specifics ─────────────────────────────────────────────────
        lines = []
        if isinstance(c, discord.TextChannel):
            if c.topic:
                lines.append(f"• **Topic:**\n  > {c.topic[:200]}")
            lines.append(f"• **Slowmode:** `{c.slowmode_delay}s` · **NSFW:** `{'Yes' if c.is_nsfw() else 'No'}`")
        elif isinstance(c, discord.VoiceChannel):
            limit_str = f"{c.user_limit} users" if c.user_limit else "Unlimited"
            lines.append(f"• **Bitrate:** `{c.bitrate // 1000} kbps` · **User Limit:** `{limit_str}`")
            lines.append(f"• **Active Members:** `{len(c.members)}` connected")
        elif isinstance(c, discord.StageChannel):
            lines.append(f"• **Bitrate:** `{c.bitrate // 1000} kbps` · **Speakers:** `{len(c.speakers)}`")

        lines.append(f"• **Position:** `{c.position + 1}` in server list · **ID:** `{c.id}`")

        self.add_text("### ⚙️ Channel Properties\n" + "\n".join(lines))

        # ── Footer ────────────────────────────────────────────────────────────
        self.add_footer(f"Requested by {self.requester.display_name}")

        # ── Action Buttons ────────────────────────────────────────────────────
        buttons = []
        if hasattr(c, "jump_url"):
            buttons.append(
                discord.ui.Button(
                    label="Jump to Channel",
                    emoji="🔗",
                    style=discord.ButtonStyle.link,
                    url=c.jump_url,
                )
            )

        buttons.append(DismissButton(user_id=self.requester.id))
        self.add_row(*buttons)


class ChannelInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="channelinfo",
        description="📝 Displays detailed specifications and properties of a channel",
        aliases=["ci"],
    )
    @app_commands.describe(channel="The channel to inspect (defaults to current channel)")
    async def channelinfo(
        self,
        ctx: commands.Context,
        channel: Optional[discord.abc.GuildChannel] = None,
    ):
        if not ctx.guild:
            await ctx.send("❌ This command must be used within a server.", ephemeral=True)
            return

        target = channel or ctx.channel
        if not isinstance(target, discord.abc.GuildChannel):
            await ctx.send("❌ Cannot retrieve information for this channel type.", ephemeral=True)
            return

        view = ChannelInfoView(target, ctx.author)
        await send_view(ctx, view)


async def setup(bot):
    await bot.add_cog(ChannelInfo(bot))
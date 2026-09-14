"""
cogs/info/roleinfo.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Role Inspector Card
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
    progress_bar,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)


class RoleInfoView(NexoraView):
    """Components V2 role specification card."""

    def __init__(
        self,
        role: discord.Role,
        requester: discord.abc.User,
        timeout: float = 180,
    ):
        color = role.color.value if role.color.value else BRAND_COLOR
        super().__init__(user_id=requester.id, color=color, timeout=timeout)
        self.role = role
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()
        r = self.role
        guild = r.guild
        member_count = len(r.members)
        total_guild_members = max(1, guild.member_count or 1)
        member_pct = (member_count / total_guild_members) * 100

        # Permissions
        key_perms = [
            perm.replace("_", " ").title()
            for perm, val in r.permissions
            if val and perm not in ["read_message_history", "view_channel"]
        ]
        perms_str = " · ".join(f"`{p}`" for p in key_perms[:8]) if key_perms else "`None`"
        if len(key_perms) > 8:
            perms_str += f" *(+{len(key_perms) - 8} more)*"

        color_hex = f"#{r.color.value:06x}" if r.color.value else "Default"
        icon_url = str(r.icon.url) if r.icon else (str(guild.icon.url) if guild.icon else None)

        # ── Header Section ────────────────────────────────────────────────────
        header_text = (
            f"# 🎭 {r.name}\n"
            f"> ID: `{r.id}` · Mention: {r.mention}\n"
            f"Created {ts_format(r.created_at, 'D')} ({ts_format(r.created_at, 'R')})"
        )
        self.add_section(header_text, thumbnail_url=icon_url)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── Membership & Attributes Block ─────────────────────────────────────
        bar = progress_bar(member_count, total_guild_members, length=8)
        meta_block = (
            "### 📊 Role Attributes\n"
            f"• **Assigned Members:** `{bar}` **{member_count:,}** ({member_pct:.1f}% of server)\n"
            f"• **Color:** `{color_hex}` · **Position:** `{r.position}`\n"
            f"• **Hoisted in Sidebar:** `{'Yes' if r.hoist else 'No'}` · **Mentionable:** `{'Yes' if r.mentionable else 'No'}`\n"
            f"• **Integration Role:** `{'Yes' if r.is_integration() or r.is_bot_managed() else 'No'}`"
        )
        self.add_text(meta_block)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── Key Permissions Block ─────────────────────────────────────────────
        self.add_text(f"### 🛡️ Key Permissions ({len(key_perms)})\n{perms_str}")

        # ── Footer ────────────────────────────────────────────────────────────
        self.add_footer(f"Requested by {self.requester.display_name}")

        # ── Action Buttons ────────────────────────────────────────────────────
        dismiss = DismissButton(user_id=self.requester.id)
        self.add_row(dismiss)


class RoleInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="roleinfo",
        description="🎭 Displays detailed specifications and permissions of a role",
        aliases=["ri"],
    )
    @app_commands.describe(role="The role you want to inspect")
    async def roleinfo(self, ctx: commands.Context, role: discord.Role):
        if not ctx.guild:
            await ctx.send("❌ This command must be used in a server.", ephemeral=True)
            return

        view = RoleInfoView(role, ctx.author)
        await send_view(ctx, view)


async def setup(bot):
    await bot.add_cog(RoleInfo(bot))
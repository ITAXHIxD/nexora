"""
cogs/info/userinfo.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Member Profile Dossier
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    NexoraView,
    DismissButton,
    status_badge,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)


class UserInfoView(NexoraView):
    """Components V2 member dossier card with roles and permissions."""

    def __init__(
        self,
        target: Union[discord.Member, discord.User],
        requester: discord.abc.User,
        bot: Optional[commands.Bot] = None,
        timeout: float = 180,
    ):
        self.bot = bot
        color = BRAND_COLOR
        if bot and hasattr(bot, "get_user_custom_color"):
            custom_c = bot.get_user_custom_color(target.id)
            if custom_c:
                color = custom_c
        if color == BRAND_COLOR and isinstance(target, discord.Member) and target.color and target.color.value:
            color = target.color.value
        super().__init__(user_id=requester.id, color=color, timeout=timeout)
        self.target = target
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()
        u = self.target
        is_member = isinstance(u, discord.Member)

        # Badges & Flags
        badges = []
        if is_member and u.guild and u.id == u.guild.owner_id:
            badges.append("👑 **Owner**")
        if is_member and getattr(u.guild_permissions, "administrator", False):
            badges.append("🛡️ **Admin**")
        if is_member and getattr(u, "premium_since", None):
            badges.append("💎 **Booster**")

        # VIP Badge Check
        if self.bot:
            vip_checker = getattr(self.bot, "is_premium_user", None)
            is_vip = False
            if callable(vip_checker):
                res = vip_checker(u.id)
                is_vip = bool(res)
            elif u.id in getattr(self.bot, "premium_user_ids", set()):
                is_vip = True

            if is_vip:
                badge_getter = getattr(self.bot, "get_user_vip_badge", None)
                b_info = badge_getter(u.id) if callable(badge_getter) else None
                if b_info:
                    badges.append(f"{b_info['emoji']} **{b_info['label']}**")
                else:
                    badges.append("👑 **Nexora VIP**")

        if u.bot:
            badges.append("🤖 **Bot**")
        
        if not badges:
            badge_line = "👤 **Member**" if is_member else "🌐 **Discord User**"
        else:
            badge_line = " · ".join(badges)

        status_text = status_badge(u.status) if is_member and hasattr(u, "status") else "🌐 `External/Offline`"

        # ── Header Section ────────────────────────────────────────────────────
        header_text = (
            f"# {u.display_name}\n"
            f"> `@{u.name}` · ID: `{u.id}`\n"
            f"{badge_line} · {status_text}"
        )
        avatar_url = str(u.display_avatar.url)
        self.add_section(header_text, thumbnail_url=avatar_url)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── Dates & Timestamps Block ──────────────────────────────────────────
        created_str = f"{ts_format(u.created_at, 'D')} ({ts_format(u.created_at, 'R')})"
        if is_member and getattr(u, "joined_at", None):
            dates_block = (
                "### 📅 Timeline\n"
                f"• **Account Created:** {created_str}\n"
                f"• **Joined Server:** {ts_format(u.joined_at, 'D')} ({ts_format(u.joined_at, 'R')})"
            )
        else:
            dates_block = (
                "### 📅 Timeline\n"
                f"• **Account Created:** {created_str}\n"
                f"• **Context:** Global Discord Profile (DM / User App)"
            )
        self.add_text(dates_block)
        self.add_separator(discord.SeparatorSpacing.small)

        # ── Roles & Key Permissions Block ─────────────────────────────────────
        if is_member:
            guild_roles = [r for r in u.roles if r.name != "@everyone"]
            guild_roles.reverse()  # Highest first
            roles_mentions = [r.mention for r in guild_roles[:12]]
            roles_str = ", ".join(roles_mentions) if roles_mentions else "None"
            if len(guild_roles) > 12:
                roles_str += f" *(+{len(guild_roles) - 12} more)*"

            key_perms = []
            p = u.guild_permissions
            if p.administrator:
                key_perms.append("Administrator")
            if p.manage_guild:
                key_perms.append("Manage Server")
            if p.manage_roles:
                key_perms.append("Manage Roles")
            if p.manage_channels:
                key_perms.append("Manage Channels")
            if p.ban_members:
                key_perms.append("Ban Members")
            if p.kick_members:
                key_perms.append("Kick Members")
            if p.manage_messages:
                key_perms.append("Manage Messages")
            perms_str = " · ".join(f"`{k}`" for k in key_perms[:6]) if key_perms else "`Standard Member`"

            top_role = u.top_role.mention if u.top_role.name != "@everyone" else "None"
            roles_block = (
                "### 🎭 Roles & Permissions\n"
                f"• **Top Role:** {top_role} · **Total:** `{len(guild_roles)}`\n"
                f"• **Key Perms:** {perms_str}\n"
                f"• **Assigned Roles:**\n  {roles_str}"
            )
        else:
            accent_hex = f"`#{u.accent_color.value:06X}`" if getattr(u, "accent_color", None) else "`Default`"
            has_banner = "✅ Custom Banner" if getattr(u, "banner", None) else "None"
            roles_block = (
                "### 🌐 Global Discord Identity\n"
                f"• **Display Name:** `{u.display_name}`\n"
                f"• **Accent Theme:** {accent_hex} · **Banner:** {has_banner}"
            )
        self.add_text(roles_block)

        # ── Footer ────────────────────────────────────────────────────────────
        self.add_footer(f"Requested by {self.requester.display_name}")

        # ── Interactive Buttons ───────────────────────────────────────────────
        buttons = [
            discord.ui.Button(
                label="Avatar",
                emoji="🖼️",
                style=discord.ButtonStyle.link,
                url=u.display_avatar.url,
            )
        ]
        if hasattr(u, "banner") and u.banner:
            buttons.append(
                discord.ui.Button(
                    label="Banner",
                    emoji="🌆",
                    style=discord.ButtonStyle.link,
                    url=u.banner.url,
                )
            )

        buttons.append(DismissButton(user_id=self.requester.id))
        self.add_row(*buttons)


class UserInfo(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.hybrid_command(
        name="userinfo",
        description="👤 View detailed user dossier, roles, and permissions",
        aliases=["ui", "whois"],
    )
    @app_commands.describe(user="User or member to inspect (defaults to yourself)")
    async def userinfo(self, ctx: commands.Context, user: Optional[Union[discord.Member, discord.User]] = None):
        target = user or ctx.author
        if not isinstance(target, discord.Member) and ctx.guild:
            target = ctx.guild.get_member(target.id) or target

        view = UserInfoView(target, ctx.author, bot=ctx.bot)
        await send_view(ctx, view)


async def setup(bot):
    await bot.add_cog(UserInfo(bot))

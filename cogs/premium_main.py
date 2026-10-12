"""
cogs/premium_main.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Nexora Dual-Tier Premium Suite & Vanity Status Engine.

Combines Server Premium (communities) and User VIP (individuals)
into an enterprise-grade monetization and perk ecosystem.

MongoDB Collections:
  1. "premium"       — Server subscriptions (guild_id as int _id)
  2. "user_premium"  — User VIP subscriptions (user_id as int _id)

Exported Bot Helpers (patched dynamically in cog_load):
  • bot.is_premium_guild(guild_id)  → bool
  • bot.get_premium_tier(guild_id)  → str
  • bot.is_premium_user(user_id)    → bool
  • bot.get_user_vip_tier(user_id)  → str
  • bot.get_user_custom_color(user_id) → int | None
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import re
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Set, Tuple

import discord
from discord import app_commands
from discord.ext import commands, tasks

from utils.premium_storage import load_premium_data, save_premium_data

from utils.ui import (
    BRAND_COLOR,
    PREMIUM_COLOR,
    SUCCESS_COLOR,
    ERROR_COLOR,
    CYAN_COLOR,
    progress_bar,
)

logger = logging.getLogger(__name__)

UNSAFE_VANITY_WEBHOOK_FIELDS = (
    "log_webhook",
    "webhook",
    "webhook_url",
    "discord_webhook",
    "discord_webhook_url",
)

OWNER_ID = 1013851779886231685
YEARLY_DISCOUNT = 20  # 20% annual discount

# ══════════════════════════════════════════════════════════════════
# SERVER PREMIUM CONFIGURATION
# ══════════════════════════════════════════════════════════════════

SERVER_TIERS = {
    "FREE": {
        "display_name": "🆓 Free Tier",
        "emoji":        "🆓",
        "price":        0.00,
        "color":        0x95A5A6,
        "features": {
            "vanity_roles":       0,
            "custom_responses":   0,
            "booster_roles":      False,
            "embed_studio":       False,
            "server_analytics":   False,
            "priority_support":   False,
            "message_history":    10,
        },
        "limits": {
            "api_calls_per_day":      100,
            "response_priority":      3,
        },
    },
    "BASIC": {
        "display_name": "💎 Basic Server",
        "emoji":        "💎",
        "price":        4.99,
        "color":        0x5DADE2,
        "features": {
            "vanity_roles":       5,
            "custom_responses":   10,
            "booster_roles":      True,
            "embed_studio":       True,
            "server_analytics":   True,
            "priority_support":   True,
            "message_history":    25,
        },
        "limits": {
            "api_calls_per_day":      500,
            "response_priority":      2,
        },
    },
    "PRO": {
        "display_name": "🚀 Pro Server",
        "emoji":        "🚀",
        "price":        12.99,
        "color":        0x57F287,
        "features": {
            "vanity_roles":       20,
            "custom_responses":   30,
            "booster_roles":      True,
            "embed_studio":       True,
            "server_analytics":   True,
            "priority_support":   True,
            "message_history":    50,
        },
        "limits": {
            "api_calls_per_day":      1500,
            "response_priority":      1,
        },
    },
    "ENTERPRISE": {
        "display_name": "🏢 Enterprise Server",
        "emoji":        "🏢",
        "price":        29.99,
        "color":        0xFFD700,
        "features": {
            "vanity_roles":       -1,
            "custom_responses":   -1,
            "booster_roles":      True,
            "embed_studio":       True,
            "server_analytics":   True,
            "priority_support":   True,
            "message_history":    100,
        },
        "limits": {
            "api_calls_per_day":      -1,
            "response_priority":      0,
        },
    },
    "CUSTOM": {
        "display_name": "🛃 Custom SLA",
        "emoji":        "🛃",
        "price":        None,
        "color":        0xFF64C8,
        "features": {
            "vanity_roles":       -1,
            "custom_responses":   -1,
            "booster_roles":      True,
            "embed_studio":       True,
            "server_analytics":   True,
            "priority_support":   True,
            "message_history":    100,
        },
        "limits": {
            "api_calls_per_day":      -1,
            "response_priority":      0,
        },
    },
    "GRANDFATHERED": {
        "display_name": "🏆 Grandfathered",
        "emoji":        "🏆",
        "price":        0.00,
        "color":        0xFF8C00,
        "features": {
            "vanity_roles":       -1,
            "custom_responses":   -1,
            "booster_roles":      True,
            "embed_studio":       True,
            "server_analytics":   True,
            "priority_support":   True,
            "message_history":    100,
        },
        "limits": {
            "api_calls_per_day":      -1,
            "response_priority":      0,
        },
    },
}

PAID_SERVER_TIERS = {"BASIC", "PRO", "ENTERPRISE", "CUSTOM", "GRANDFATHERED"}

# ══════════════════════════════════════════════════════════════════
# USER VIP CONFIGURATION
# ══════════════════════════════════════════════════════════════════

USER_TIERS = {
    "FREE": {
        "display_name": "Standard User",
        "emoji":        "👤",
        "price":        0.00,
        "color":        0x95A5A6,
        "features": {
            "max_reminders":    5,
            "custom_color":     False,
            "vip_badge":        False,
            "server_passes":    0,
            "cooldown_bypass":  False,
        },
    },
    "VIP": {
        "display_name": "👑 Nexora VIP",
        "emoji":        "👑",
        "price":        2.99,
        "color":        0xF1C40F,
        "features": {
            "max_reminders":    25,
            "custom_color":     True,
            "vip_badge":        True,
            "server_passes":    0,
            "cooldown_bypass":  True,
        },
    },
    "VIP_PLUS": {
        "display_name": "⭐ Nexora VIP Plus",
        "emoji":        "⭐",
        "price":        7.99,
        "color":        0x9B59B6,
        "features": {
            "max_reminders":    50,
            "custom_color":     True,
            "vip_badge":        True,
            "server_passes":    1,  # Grants 1 free Server Premium pass!
            "cooldown_bypass":  True,
        },
    },
}

PAID_USER_TIERS = {"VIP", "VIP_PLUS"}


# ══════════════════════════════════════════════════════════════════
# UTILITIES
# ══════════════════════════════════════════════════════════════════

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_dt(value) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        return _aware(value)
    if isinstance(value, str):
        try:
            return _aware(datetime.fromisoformat(value))
        except ValueError:
            return None
    return None


def _is_expired(doc: dict) -> bool:
    exp = _parse_dt(doc.get("expires_at"))
    if exp is None:
        return False
    return exp < utcnow()


def _fmt_expiry(doc: dict) -> str:
    exp = _parse_dt(doc.get("expires_at"))
    if exp is None:
        return "♾️  **Permanent Lifetime**"
    if exp < utcnow():
        return "❌  **Expired**"
    ts = int(exp.timestamp())
    return f"<t:{ts}:R> · <t:{ts}:D>"


def _quota_meter(used: int, limit: int, width: int = 10) -> str:
    if limit == -1:
        return f"`[██████████]` `{used}` / `Unlimited`"
    pct = min(1.0, float(used) / float(limit)) if limit > 0 else 0.0
    bar = progress_bar(used, limit, length=width, filled="█", empty="░")
    return f"`[{bar}]` `{used} / {limit}` ({int(pct * 100)}%)"


# ══════════════════════════════════════════════════════════════════
# INTERACTIVE UI: DUAL-TIER CATALOG & PRICING
# ══════════════════════════════════════════════════════════════════

class DualPricingView(discord.ui.View):
    """Dynamic pricing catalog supporting both Server and User tiers with yearly calculator."""

    def __init__(self, requester: discord.abc.User, default_mode: str = "server", timeout: float = 180):
        super().__init__(timeout=timeout)
        self.requester = requester
        self.mode = default_mode  # "server" or "user"
        self.selected_server = "PRO"
        self.selected_user = "VIP_PLUS"
        self.yearly = False
        self._update_button_states()

    def _update_button_states(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == "mode_server":
                    child.style = discord.ButtonStyle.primary if self.mode == "server" else discord.ButtonStyle.secondary
                elif child.custom_id == "mode_user":
                    child.style = discord.ButtonStyle.primary if self.mode == "user" else discord.ButtonStyle.secondary
                elif child.custom_id == "toggle_cycle":
                    if self.yearly:
                        child.label = "Billing: Annual (20% OFF)"
                        child.style = discord.ButtonStyle.success
                        child.emoji = "🎉"
                    else:
                        child.label = "Billing: Monthly"
                        child.style = discord.ButtonStyle.secondary
                        child.emoji = "📅"

    def render_embed(self) -> discord.Embed:
        if self.mode == "server":
            return self._render_server_embed()
        return self._render_user_embed()

    def _render_server_embed(self) -> discord.Embed:
        cfg = SERVER_TIERS[self.selected_server]
        base_price = cfg["price"]

        embed = discord.Embed(
            title=f"🏢 Nexora Server Subscriptions · {cfg['display_name']}",
            color=cfg["color"],
            timestamp=utcnow(),
        )

        if base_price is None:
            price_str = "🤝 **Custom Negotiated Pricing**"
            sub_text = "Tailored for large community networks, brands, and esports servers."
        elif base_price == 0:
            price_str = "🆓 **$0.00 / Free Forever**"
            sub_text = "Standard features for every server."
        else:
            if self.yearly:
                yr_price = round(base_price * 12 * (1.0 - YEARLY_DISCOUNT / 100.0), 2)
                save = round(base_price * 12 - yr_price, 2)
                price_str = f"### 🎉 **${yr_price:.2f} / year** (~${(yr_price/12):.2f}/mo)\n> 🎁 *Save **${save:.2f}** per year with 20% annual discount!*"
            else:
                price_str = f"### 📅 **${base_price:.2f} / month**\n> *Switch to Annual Billing to save 20%!*"
            sub_text = "Unlock community-wide perks for all members in the server!"

        embed.description = f"{price_str}\n\n{sub_text}"

        feats = cfg["features"]
        v_str = "Unlimited" if feats.get("vanity_roles", 0) == -1 else str(feats.get("vanity_roles", 0))
        r_str = "Unlimited" if feats.get("custom_responses", 0) == -1 else str(feats.get("custom_responses", 0))

        feat_list = [
            f"• 🎭 **Vanity Status Roles:** **{v_str}** triggers & auto-sync",
            f"• 🤖 **Auto-Responders:** **{r_str}** smart keyword responders",
            f"• 🚀 **Custom Booster Roles:** {'✅ Included' if feats.get('booster_roles') else '❌ Not included'}",
            f"• 🎨 **Embed Studio:** {'✅ Included' if feats.get('embed_studio') else '❌ Not included'}",
            f"• 📊 **Server Analytics & Growth:** {'✅ Included' if feats.get('server_analytics') else '❌ Not included'}",
            f"• 💬 **Context Memory:** **{feats.get('message_history', 10)}** messages",
            f"• ⚡ **Dedicated Quota:** **{cfg['limits'].get('api_calls_per_day', 100)}** calls/day",
            f"• 🛡️ **Priority SLA & Support:** {'✅ 24/7 Dedicated' if feats.get('priority_support') else '⚪ Community Discord'}",
        ]
        embed.add_field(name="📦 Community Perks Included", value="\n".join(feat_list), inline=False)
        embed.add_field(
            name="💡 Looking for Personal User Perks?",
            value="Click **'👑 User VIP Plans'** below to see individual cross-server superpowers!",
            inline=False,
        )
        embed.set_footer(text=f"Requested by {self.requester.display_name} · Instant UPI / Card Activation", icon_url=self.requester.display_avatar.url)
        return embed

    def _render_user_embed(self) -> discord.Embed:
        cfg = USER_TIERS[self.selected_user]
        base_price = cfg["price"]

        embed = discord.Embed(
            title=f"👑 Nexora Personal VIP · {cfg['display_name']}",
            color=cfg["color"],
            timestamp=utcnow(),
        )

        if self.yearly:
            yr_price = round(base_price * 12 * (1.0 - YEARLY_DISCOUNT / 100.0), 2)
            save = round(base_price * 12 - yr_price, 2)
            price_str = f"### 🎉 **${yr_price:.2f} / year** (~${(yr_price/12):.2f}/mo)\n> 🎁 *Save **${save:.2f}** per year with 20% annual discount!*"
        else:
            price_str = f"### 📅 **${base_price:.2f} / month**\n> *Switch to Annual Billing to save 20%!*"

        embed.description = f"{price_str}\n\nPerks that follow you across **every single server** where Nexora is present!"

        feats = cfg["features"]
        perks = [
            f"• 🎨 **Custom Embed Accent Color:** Bot commands adopt your custom chosen color!",
            f"• 👑 **VIP Profile Badge & Glow:** Displayed on `/userinfo`, `/myprofile`, and `/avatar`",
            f"• ⏰ **Supercharged Reminders:** Up to **{feats.get('max_reminders', 5)}** concurrent persistent reminders",
            f"• ⚡ **Cooldown Bypass:** Zero command cooldown delays across the bot",
        ]
        if feats.get("server_passes", 0) > 0:
            perks.append(f"• 🎟️ **Free Server Activation Pass:** Gift **Server Premium** to any 1 server of your choice!")

        embed.add_field(name="🌟 Personal VIP Perks", value="\n".join(perks), inline=False)
        embed.add_field(
            name="💳 Instant Activation",
            value=f"Click **'How to Pay (UPI)'** below or DM <@{OWNER_ID}> to activate immediately.",
            inline=False,
        )
        embed.set_footer(text=f"Requested by {self.requester.display_name} · Personal VIP Ecosystem", icon_url=self.requester.display_avatar.url)
        return embed

    @discord.ui.button(label="Server Plans", emoji="🏢", style=discord.ButtonStyle.primary, custom_id="mode_server", row=0)
    async def btn_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.mode = "server"
        self._update_button_states()
        await interaction.response.edit_message(embed=self.render_embed(), view=self)

    @discord.ui.button(label="User VIP Plans", emoji="👑", style=discord.ButtonStyle.secondary, custom_id="mode_user", row=0)
    async def btn_user(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.mode = "user"
        self._update_button_states()
        await interaction.response.edit_message(embed=self.render_embed(), view=self)

    @discord.ui.button(label="Billing: Monthly", emoji="📅", style=discord.ButtonStyle.secondary, custom_id="toggle_cycle", row=0)
    async def btn_cycle(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.yearly = not self.yearly
        self._update_button_states()
        await interaction.response.edit_message(embed=self.render_embed(), view=self)

    @discord.ui.button(label="How to Pay (UPI)", emoji="💳", style=discord.ButtonStyle.success, row=1)
    async def btn_pay(self, interaction: discord.Interaction, button: discord.ui.Button):
        pay_embed = discord.Embed(
            title="💳 Nexora Premium Payment Gateway",
            description=(
                f"### **Payment & Instant Activation**\n"
                f"• **Accepted Methods:** **UPI** (GPay, PhonePe, Paytm), PayPal, Crypto\n"
                f"• **Direct Contact:** <@{OWNER_ID}>\n\n"
                f"**To Activate:**\n"
                f"1. Select whether you want **Server Premium** or **User VIP**.\n"
                f"2. Contact <@{OWNER_ID}> on Discord.\n"
                f"3. Send the payment and provide your Server ID or User ID for instant activation!"
            ),
            color=SUCCESS_COLOR,
        )
        await interaction.response.send_message(embed=pay_embed, ephemeral=True)

    @discord.ui.button(label="Dismiss", emoji="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def btn_dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message("❌ This pricing menu belongs to someone else.", ephemeral=True)
            return False
        return True


# ══════════════════════════════════════════════════════════════════
# INTERACTIVE UI: SERVER CONTROL HUB (/premium server)
# ══════════════════════════════════════════════════════════════════

class ServerControlHubView(discord.ui.View):
    """Executive dashboard for server premium status, quotas, and health."""

    def __init__(self, cog: "Premium", guild: discord.Guild, doc: dict, requester: discord.abc.User, timeout: float = 180):
        super().__init__(timeout=timeout)
        self.cog = cog
        self.guild = guild
        self.doc = doc
        self.requester = requester
        self.tab = "overview"

        tier = (doc.get("tier", "FREE") or "FREE").upper()
        if tier != "GRANDFATHERED" and _is_expired(doc):
            tier = "FREE"
        self.tier = tier
        self.cfg = SERVER_TIERS.get(tier, SERVER_TIERS["FREE"])
        self._update_button_states()

    def _update_button_states(self):
        for child in self.children:
            if isinstance(child, discord.ui.Button):
                if child.custom_id == f"hub_{self.tab}":
                    child.style = discord.ButtonStyle.primary
                elif child.custom_id and child.custom_id.startswith("hub_"):
                    child.style = discord.ButtonStyle.secondary

    def get_overview_embed(self) -> discord.Embed:
        g = self.guild
        cfg = self.cfg
        is_active = self.tier in PAID_SERVER_TIERS and (self.tier == "GRANDFATHERED" or not _is_expired(self.doc))

        embed = discord.Embed(
            title=f"{cfg['emoji']} {g.name} · Server Premium Status",
            color=cfg["color"],
            timestamp=utcnow(),
        )
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        if g.banner:
            embed.set_image(url=g.banner.url)

        status_text = "🟢 **Active Server Subscription**" if is_active else "⚪ **Free Tier**"
        embed.description = f"### Plan: `{cfg['display_name']}`\n> Status: {status_text} · Guild ID: `{g.id}`"

        vanity_roles = self.doc.get("vanity_roles", {})
        custom_replies = self.doc.get("custom_replies", [])
        booster_roles = self.doc.get("booster_roles", {})

        v_limit = cfg["features"].get("vanity_roles", 0)
        r_limit = cfg["features"].get("custom_responses", 0)

        embed.add_field(name="🎭 Vanity Triggers", value=_quota_meter(len(vanity_roles), v_limit), inline=False)
        embed.add_field(name="🤖 Auto-Responders", value=_quota_meter(len(custom_replies), r_limit), inline=False)
        embed.add_field(
            name="🚀 Custom Booster Roles",
            value=f"`{len(booster_roles)}` active roles · Anchor: `{'Configured' if self.doc.get('booster_anchor') else 'Not Set'}`",
            inline=False,
        )

        purchased_by = self.doc.get("purchased_by")
        buyer_str = f"<@{purchased_by}>" if purchased_by else "*System / Free Tier*"
        purchased_at = _parse_dt(self.doc.get("purchased_at"))
        purchased_at_str = f"<t:{int(purchased_at.timestamp())}:D>" if purchased_at else "*N/A*"

        embed.add_field(name="👤 Owner / Buyer", value=buyer_str, inline=True)
        embed.add_field(name="📅 Activated On", value=purchased_at_str, inline=True)
        embed.add_field(name="⏳ Expiration", value=_fmt_expiry(self.doc), inline=False)
        storage_state = "MongoDB connected" if self.cog.col_server is not None else "Local entitlement only; feature settings require MongoDB"
        embed.add_field(name="Premium Storage", value=storage_state, inline=False)

        embed.set_footer(text=f"Requested by {self.requester.display_name} · Nexora Dual-Tier Ecosystem", icon_url=self.requester.display_avatar.url)
        return embed

    def get_perks_embed(self) -> discord.Embed:
        cfg = self.cfg
        embed = discord.Embed(
            title=f"🔓 Server Perks Matrix · {cfg['display_name']}",
            description="Feature allocations unlocked for this community.",
            color=cfg["color"],
            timestamp=utcnow(),
        )
        feats = cfg["features"]
        perk_lines = []
        labels = {
            "vanity_roles":     "Vanity Status Roles",
            "custom_responses": "Auto-Responders",
            "booster_roles":    "Custom Booster Roles",
            "embed_studio":     "Embed & Announcement Studio",
            "server_analytics": "Server Analytics & Growth Diagnostics",
            "priority_support": "Priority Bot Infrastructure",
            "message_history":  "Context Message History",
        }
        for k, lbl in labels.items():
            val = feats.get(k, False)
            if isinstance(val, bool):
                icon = "✅" if val else "❌"
                perk_lines.append(f"{icon} **{lbl}:** {'Unlocked' if val else 'Locked'}")
            elif val == -1:
                perk_lines.append(f"✅ **{lbl}:** `Unlimited`")
            elif val == 0:
                perk_lines.append(f"❌ **{lbl}:** `None` (Upgrade required)")
            else:
                perk_lines.append(f"✅ **{lbl}:** Up to `{val}` slots")

        embed.add_field(name="Feature Status", value="\n".join(perk_lines), inline=False)
        return embed

    def get_diagnostics_embed(self) -> discord.Embed:
        g = self.guild
        me = g.me
        can_roles = me.guild_permissions.manage_roles
        can_channels = me.guild_permissions.manage_channels
        top_role = me.top_role

        embed = discord.Embed(
            title="🛡️ Server Permission Health & Audit",
            description=f"Automated health diagnostics for **{g.name}**.",
            color=CYAN_COLOR,
            timestamp=utcnow(),
        )
        embed.add_field(
            name="🎭 Manage Roles Permission",
            value="✅ **Granted** (Required for Vanity & Booster roles)" if can_roles else "❌ **Missing!** Grant `Manage Roles`.",
            inline=False,
        )
        embed.add_field(
            name="📢 Manage Channels Permission",
            value="✅ **Granted** (Required for Celebration logs)" if can_channels else "⚠️ **Missing** (Optional for celebration logs)",
            inline=False,
        )
        embed.add_field(
            name="👑 Bot Role Hierarchy",
            value=f"Top Role: {top_role.mention} (Position `{top_role.position}`)\n*Vanity & Booster roles must be placed below this role.*",
            inline=False,
        )
        return embed

    @discord.ui.button(label="Overview", emoji="📊", style=discord.ButtonStyle.primary, custom_id="hub_overview", row=0)
    async def btn_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.tab = "overview"
        self._update_button_states()
        await interaction.response.edit_message(embed=self.get_overview_embed(), view=self)

    @discord.ui.button(label="Perks", emoji="⚡", style=discord.ButtonStyle.secondary, custom_id="hub_perks", row=0)
    async def btn_perks(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.tab = "perks"
        self._update_button_states()
        await interaction.response.edit_message(embed=self.get_perks_embed(), view=self)

    @discord.ui.button(label="Diagnostics", emoji="🛡️", style=discord.ButtonStyle.secondary, custom_id="hub_diagnostics", row=0)
    async def btn_diagnostics(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.tab = "diagnostics"
        self._update_button_states()
        await interaction.response.edit_message(embed=self.get_diagnostics_embed(), view=self)

    @discord.ui.button(label="Compare Plans", emoji="🏷️", style=discord.ButtonStyle.success, row=1)
    async def btn_plans(self, interaction: discord.Interaction, button: discord.ui.Button):
        catalog_view = DualPricingView(self.requester, default_mode="server")
        await interaction.response.send_message(embed=catalog_view.render_embed(), view=catalog_view, ephemeral=True)

    @discord.ui.button(label="Dismiss", emoji="🗑️", style=discord.ButtonStyle.danger, row=1)
    async def btn_dismiss(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.requester.id:
            await interaction.response.send_message("❌ This panel belongs to someone else.", ephemeral=True)
            return False
        return True


# ══════════════════════════════════════════════════════════════════
# MAIN COG IMPLEMENTATION
# ══════════════════════════════════════════════════════════════════

class Premium(commands.Cog):
    """Unified Server Premium, User VIP, and Vanity status management engine."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.col_server = None
        self.col_user = None

    async def cog_load(self):
        db = getattr(self.bot, "mongo_db", None)
        if db is not None:
            self.col_server = db["premium"]
            self.col_user = db["user_premium"]
            logger.info("Premium: MongoDB collections connected")

            await self._scrub_unsafe_webhook_fields()

            # Cache server premium
            try:
                async for doc in self.col_server.find({"tier": {"$in": list(PAID_SERVER_TIERS)}}):
                    if not _is_expired(doc):
                        self.bot.premium_guild_ids.add(doc["_id"])
                        self.bot.premium_guild_tiers[doc["_id"]] = doc.get("tier", "FREE")
            except Exception as e:
                logger.warning("Premium server cache warning: %s", e)

            # Cache user VIP
            self.bot.premium_user_ids = set()
            self.bot.premium_user_tiers = {}
            self.bot.premium_user_colors = {}
            try:
                async for doc in self.col_user.find({"tier": {"$in": list(PAID_USER_TIERS)}}):
                    if not _is_expired(doc):
                        uid = doc["_id"]
                        self.bot.premium_user_ids.add(uid)
                        self.bot.premium_user_tiers[uid] = doc.get("tier", "FREE")
                        if doc.get("custom_color"):
                            self.bot.premium_user_colors[uid] = doc["custom_color"]
            except Exception as e:
                logger.warning("Premium user cache warning: %s", e)
        else:
            logger.warning("Premium: mongo_db unavailable")

        if not self.vanity_scan_task.is_running():
            self.vanity_scan_task.start()

        # Patch shared helpers used by premium-gated features.
        cog = self

        def _get_tier_config(tier: str) -> dict:
            key = str(tier or "FREE").strip().upper()
            return SERVER_TIERS.get(key, SERVER_TIERS["FREE"])

        async def _is_premium_guild(guild_id: int) -> bool:
            return await cog.is_premium_guild(guild_id)

        async def _get_premium_tier(guild_id: int) -> str:
            return await cog.get_premium_tier(guild_id)

        async def _is_premium_user(user_id: int) -> bool:
            return await cog.is_premium_user(user_id)

        async def _get_user_vip_tier(user_id: int) -> str:
            return await cog.get_user_vip_tier(user_id)

        def _get_user_custom_color(user_id: int) -> Optional[int]:
            return getattr(cog.bot, "premium_user_colors", {}).get(user_id)

        self.bot.is_premium_guild     = _is_premium_guild
        self.bot.get_premium_tier     = _get_premium_tier
        self.bot.get_tier_config      = _get_tier_config
        self.bot.is_premium_user      = _is_premium_user
        self.bot.get_user_vip_tier    = _get_user_vip_tier
        self.bot.get_user_custom_color = _get_user_custom_color

    def cog_unload(self):
        if self.vanity_scan_task.is_running():
            self.vanity_scan_task.cancel()

    async def _scrub_unsafe_webhook_fields(self):
        if self.col_server is None:
            return
        unset_fields = {f"vanity_settings.{field}": "" for field in UNSAFE_VANITY_WEBHOOK_FIELDS}
        filter_q = {"$or": [{f"vanity_settings.{field}": {"$exists": True}} for field in UNSAFE_VANITY_WEBHOOK_FIELDS]}
        try:
            res = await self.col_server.update_many(filter_q, {"$unset": unset_fields})
            if res.modified_count:
                logger.info("Premium: scrubbed webhooks from %d documents", res.modified_count)
        except Exception as e:
            logger.error("Scrub error: %s", e)

    # ── Database Lookups ──────────────────────────────────────────────────────

    def _get_local_server_doc(self, guild_id: int) -> dict:
        """Read a server subscription and vanity settings from the local fallback."""
        data = load_premium_data()
        subscriptions = data.get("subscriptions", {})
        subscription = subscriptions.get(str(guild_id), {}) if isinstance(subscriptions, dict) else {}
        if not isinstance(subscription, dict) or not subscription:
            return {}

        doc = dict(subscription)
        doc["_id"] = int(guild_id)
        vanity = data.get("vanity", {})
        if isinstance(vanity, dict):
            roles_map = vanity.get("roles", {})
            settings_map = vanity.get("settings", {})
            if isinstance(roles_map, dict):
                doc.setdefault("vanity_roles", roles_map.get(str(guild_id), {}))
            if isinstance(settings_map, dict):
                doc.setdefault("vanity_settings", settings_map.get(str(guild_id), {}))
        return doc

    def _save_local_server_subscription(self, guild_id: int, tier: str, expires_at, **metadata) -> None:
        data = load_premium_data()
        subscriptions = data.setdefault("subscriptions", {})
        key = str(guild_id)
        current = subscriptions.get(key)
        if not isinstance(current, dict):
            current = {}
        current.update({
            "tier": str(tier).upper(),
            "expires_at": expires_at.isoformat() if isinstance(expires_at, datetime) else expires_at,
            **metadata,
        })
        subscriptions[key] = current
        save_premium_data(data)

    async def get_server_doc(self, guild_id: int) -> dict:
        gid = int(guild_id)
        local_doc = self._get_local_server_doc(gid)

        if self.col_server is not None:
            try:
                doc = await self.col_server.find_one({"_id": gid})
                if not doc:
                    doc = await self.col_server.find_one({"_id": str(gid)})
                if doc:
                    # Feature setup may have created a partial DB record, and older
                    # grants may exist only in the local subscription file. Preserve
                    # the newest entitlement while keeping Mongo's feature settings.
                    if local_doc.get("tier"):
                        local_times = [
                            _parse_dt(local_doc.get(key))
                            for key in ("purchased_at", "revoked_at", "updated_at", "activated_at")
                        ]
                        db_times = [
                            _parse_dt(doc.get(key))
                            for key in ("purchased_at", "revoked_at", "updated_at", "activated_at")
                        ]
                        local_times = [value for value in local_times if value is not None]
                        db_times = [value for value in db_times if value is not None]
                        local_updated = max(local_times) if local_times else None
                        db_updated = max(db_times) if db_times else None
                        local_is_newer = local_updated is not None and (
                            db_updated is None or local_updated > db_updated
                        )

                        if not doc.get("tier") or local_is_newer:
                            merged = {**local_doc, **doc}
                            for key in (
                                "tier", "expires_at", "purchased_by", "purchased_at",
                                "payment_method", "notes", "revoked_at", "updated_at",
                            ):
                                if key in local_doc:
                                    merged[key] = local_doc[key]
                            return merged
                    return doc
            except Exception as exc:
                logger.warning("Premium lookup failed; trying local JSON fallback: %s", exc)
        return local_doc

    async def get_user_doc(self, user_id: int) -> dict:
        if self.col_user is None:
            return {}
        doc = await self.col_user.find_one({"_id": user_id})
        return doc or {}

    async def is_premium_guild(self, guild_id: int) -> bool:
        gid = int(guild_id)
        doc = await self.get_server_doc(gid)
        tier = str(doc.get("tier", "FREE") or "FREE").upper() if doc else "FREE"

        if tier == "GRANDFATHERED":
            self.bot.premium_guild_ids.add(gid)
            self.bot.premium_guild_tiers[gid] = tier
            return True

        active = bool(doc) and tier in PAID_SERVER_TIERS and not _is_expired(doc)
        if active:
            self.bot.premium_guild_ids.add(gid)
            self.bot.premium_guild_tiers[gid] = tier
        else:
            self.bot.premium_guild_ids.discard(gid)
            self.bot.premium_guild_tiers.pop(gid, None)
        return active

    async def get_premium_tier(self, guild_id: int) -> str:
        gid = int(guild_id)
        doc = await self.get_server_doc(gid)
        if not doc:
            self.bot.premium_guild_ids.discard(gid)
            self.bot.premium_guild_tiers.pop(gid, None)
            return "FREE"

        tier = str(doc.get("tier", "FREE") or "FREE").upper()
        if tier == "GRANDFATHERED":
            self.bot.premium_guild_ids.add(gid)
            self.bot.premium_guild_tiers[gid] = tier
            return tier
        if tier not in PAID_SERVER_TIERS or _is_expired(doc):
            self.bot.premium_guild_ids.discard(gid)
            self.bot.premium_guild_tiers.pop(gid, None)
            return "FREE"

        self.bot.premium_guild_ids.add(gid)
        self.bot.premium_guild_tiers[gid] = tier
        return tier

    async def is_premium_user(self, user_id: int) -> bool:
        doc = await self.get_user_doc(user_id)
        if not doc:
            self.bot.premium_user_ids.discard(user_id)
            self.bot.premium_user_tiers.pop(user_id, None)
            return False
        tier = doc.get("tier", "FREE").upper()
        if tier not in PAID_USER_TIERS:
            self.bot.premium_user_ids.discard(user_id)
            self.bot.premium_user_tiers.pop(user_id, None)
            return False
        active = not _is_expired(doc)
        if active:
            self.bot.premium_user_ids.add(user_id)
            self.bot.premium_user_tiers[user_id] = tier
        else:
            self.bot.premium_user_ids.discard(user_id)
            self.bot.premium_user_tiers.pop(user_id, None)
        return active

    async def get_user_vip_tier(self, user_id: int) -> str:
        doc = await self.get_user_doc(user_id)
        if not doc:
            return "FREE"
        tier = doc.get("tier", "FREE").upper()
        if _is_expired(doc):
            return "FREE"
        return tier

    # ── Vanity Engine ─────────────────────────────────────────────────────────

    def evaluate_vanity_matches(self, status: str, roles_map: dict, settings: dict) -> Set[int]:
        if not roles_map or not status:
            return set()
        match_mode = settings.get("match_mode", "substring")
        priority_mode = settings.get("priority_mode", "longest_first")
        case_sensitive = settings.get("case_sensitive", False)
        test_status = status if case_sensitive else status.lower()

        candidates = []
        for trigger, rid in roles_map.items():
            if str(rid).isdigit():
                candidates.append((trigger, int(rid)))

        if priority_mode == "longest_first":
            candidates.sort(key=lambda item: len(item[0]), reverse=True)

        matched_ids = set()
        for trigger, role_id in candidates:
            trigger_check = trigger if case_sensitive else trigger.lower()
            if match_mode == "exact":
                matched = (test_status.strip() == trigger_check.strip())
            elif match_mode == "word_boundary":
                pattern = r"\b" + re.escape(trigger_check) + r"\b"
                matched = bool(re.search(pattern, test_status))
            else:
                matched = (trigger_check in test_status)

            if matched:
                matched_ids.add(role_id)
                if priority_mode == "first_match":
                    break
        return matched_ids

    async def _sync_member_roles(self, member: discord.Member, custom_status: str, roles_map: dict, settings: dict) -> Tuple[int, int]:
        guild = member.guild
        if not guild.me.guild_permissions.manage_roles:
            return (0, 0)

        current_role_ids = {r.id for r in member.roles}
        vanity_role_ids = {int(rid) for rid in roles_map.values() if str(rid).isdigit()}
        should_have_ids = self.evaluate_vanity_matches(custom_status, roles_map, settings)

        added = 0
        removed = 0
        to_add = should_have_ids - current_role_ids
        for rid in to_add:
            role = guild.get_role(rid)
            if role and role < guild.me.top_role and not role.managed:
                try:
                    await member.add_roles(role, reason="Nexora Vanity Status Match")
                    added += 1
                except Exception:
                    pass

        to_remove = (current_role_ids & vanity_role_ids) - should_have_ids
        for rid in to_remove:
            role = guild.get_role(rid)
            if role and role < guild.me.top_role and not role.managed:
                try:
                    await member.remove_roles(role, reason="Nexora Vanity Removed")
                    removed += 1
                except Exception:
                    pass

        return (added, removed)

    async def run_vanity_sweep(self, guild: discord.Guild) -> dict:
        start = time.perf_counter()
        doc = await self.get_server_doc(guild.id)
        roles_map = doc.get("vanity_roles", {})
        settings = doc.get("vanity_settings", {})

        total_scanned = 0
        total_added = 0
        total_removed = 0
        supporters_count = 0
        all_vanity_ids = {int(rid) for rid in roles_map.values() if str(rid).isdigit()}

        for member in [m for m in guild.members if not m.bot and m.status != discord.Status.offline]:
            total_scanned += 1
            status = " ".join([a.name for a in member.activities if isinstance(a, discord.CustomActivity) and a.name])
            added, removed = await self._sync_member_roles(member, status, roles_map, settings)
            total_added += added
            total_removed += removed
            if any(r.id in all_vanity_ids for r in member.roles):
                supporters_count += 1
            await asyncio.sleep(0.02)

        dur_ms = (time.perf_counter() - start) * 1000.0
        return {
            "scanned": total_scanned,
            "added": total_added,
            "removed": total_removed,
            "supporters": supporters_count,
            "duration_ms": dur_ms,
        }

    @commands.Cog.listener()
    async def on_presence_update(self, before: discord.Member, after: discord.Member):
        if after.bot or not after.guild:
            return
        if not await self.is_premium_guild(after.guild.id):
            return

        b_status = " ".join([a.name for a in before.activities if isinstance(a, discord.CustomActivity) and a.name])
        a_status = " ".join([a.name for a in after.activities if isinstance(a, discord.CustomActivity) and a.name])
        if b_status == a_status:
            return

        doc = await self.get_server_doc(after.guild.id)
        roles_map = doc.get("vanity_roles", {})
        if not roles_map:
            return
        settings = doc.get("vanity_settings", {})
        await self._sync_member_roles(after, a_status, roles_map, settings)

    @tasks.loop(minutes=5)
    async def vanity_scan_task(self):
        try:
            for guild in self.bot.guilds:
                if not await self.is_premium_guild(guild.id):
                    continue
                doc = await self.get_server_doc(guild.id)
                roles_map = doc.get("vanity_roles", {})
                if not roles_map:
                    continue
                settings = doc.get("vanity_settings", {})
                for member in [m for m in guild.members if not m.bot and m.status != discord.Status.offline]:
                    status = " ".join([a.name for a in member.activities if isinstance(a, discord.CustomActivity) and a.name])
                    await self._sync_member_roles(member, status, roles_map, settings)
                    await asyncio.sleep(0.05)
        except Exception as e:
            logger.error("vanity_scan_task exception: %s", e)

    @vanity_scan_task.before_loop
    async def before_vanity_scan(self):
        await self.bot.wait_until_ready()

    # ══════════════════════════════════════════════════════════════
    # COMMANDS
    # ══════════════════════════════════════════════════════════════

    @commands.group(name="premium", invoke_without_command=True, description="View Server Premium or personal User VIP")
    async def premium_cmd(self, ctx: commands.Context):
        """View server premium status by default."""
        if not ctx.guild:
            return await self.premium_user(ctx)
        await self.premium_server(ctx)

    @premium_cmd.command(name="server", description="View this server's premium status, quotas, and diagnostics")
    @commands.guild_only()
    async def premium_server(self, ctx: commands.Context):
        doc = await self.get_server_doc(ctx.guild.id)
        view = ServerControlHubView(self, ctx.guild, doc, ctx.author)
        embed = view.get_overview_embed()
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    @premium_cmd.command(name="user", description="View your personal VIP perks, badges, and custom styling")
    async def premium_user(self, ctx: commands.Context):
        doc = await self.get_user_doc(ctx.author.id)
        tier = doc.get("tier", "FREE").upper()
        if _is_expired(doc):
            tier = "FREE"
        cfg = USER_TIERS.get(tier, USER_TIERS["FREE"])

        embed = discord.Embed(
            title=f"👑 Personal VIP Dashboard · {ctx.author.display_name}",
            color=cfg["color"],
            timestamp=utcnow(),
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        is_vip = tier in PAID_USER_TIERS and not _is_expired(doc)
        status_line = f"🟢 **{cfg['display_name']} Active**" if is_vip else "⚪ **Standard Free User**"
        embed.description = f"### Status: {status_line}\n> Personal cross-server superpowers active anywhere Nexora is present!"

        feats = cfg["features"]
        custom_color = doc.get("custom_color")
        color_str = f"`#{custom_color:06X}`" if custom_color else "*Default (Blurple)*"
        passes = doc.get("server_passes", feats.get("server_passes", 0))

        embed.add_field(name="🎨 Custom Embed Color", value=color_str, inline=True)
        embed.add_field(name="⏰ Max Reminders", value=f"`{feats.get('max_reminders', 5)}` slots", inline=True)
        embed.add_field(name="🎟️ Server Passes", value=f"`{passes}` available", inline=True)
        embed.add_field(name="⏳ Subscription Expiry", value=_fmt_expiry(doc), inline=False)

        embed.add_field(
            name="🛠️ VIP Actions",
            value=(
                "• `/vip color <hex>` — Set custom embed color\n"
                "• `/vip badge` — Equip VIP profile badge\n"
                "• `/vip pass <guild_id>` — Activate Server Premium for any guild!"
            ),
            inline=False,
        )
        embed.set_footer(text="Nexora VIP Network · Powering your Discord experience")
        await ctx.send(embed=embed)


    @app_commands.command(name="premium", description="View Server Premium status or personal User VIP")
    @app_commands.choices(view=[
        app_commands.Choice(name="Server Premium", value="server"),
        app_commands.Choice(name="Personal User VIP", value="user"),
    ])
    @app_commands.describe(view="Choose a dashboard; Server Premium is the default")
    async def premium_slash(self, interaction: discord.Interaction, view: str = "server"):
        """Standalone /premium command; prefix commands remain n!premium server/user."""
        if view == "user":
            doc = await self.get_user_doc(interaction.user.id)
            tier = str(doc.get("tier", "FREE") or "FREE").upper()
            if _is_expired(doc):
                tier = "FREE"
            cfg = USER_TIERS.get(tier, USER_TIERS["FREE"])
            embed = discord.Embed(
                title=f"Personal VIP Dashboard - {interaction.user.display_name}",
                color=cfg["color"],
                timestamp=utcnow(),
            )
            embed.set_thumbnail(url=interaction.user.display_avatar.url)
            is_vip = tier in PAID_USER_TIERS and not _is_expired(doc)
            embed.description = (
                f"Status: {'Active ' + cfg['display_name'] if is_vip else 'Standard Free User'}\n"
                "Personal VIP perks apply anywhere Nexora is present."
            )
            feats = cfg["features"]
            custom_color = doc.get("custom_color")
            color_str = f"#{custom_color:06X}" if custom_color else "Default"
            passes = doc.get("server_passes", feats.get("server_passes", 0))
            embed.add_field(name="Custom Embed Color", value=color_str, inline=True)
            embed.add_field(name="Max Reminders", value=str(feats.get("max_reminders", 5)), inline=True)
            embed.add_field(name="Server Passes", value=str(passes), inline=True)
            embed.add_field(name="Subscription Expiry", value=_fmt_expiry(doc), inline=False)
            embed.add_field(
                name="VIP Actions",
                value="/vip color <hex>\n/vip badge\n/vip pass <guild_id>",
                inline=False,
            )
            embed.set_footer(text="Nexora VIP Network")
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        if interaction.guild is None:
            return await interaction.response.send_message(
                "Use the user dashboard option in /premium to view personal VIP, or /premium_price for plans.",
                ephemeral=True,
            )

        doc = await self.get_server_doc(interaction.guild.id)
        panel = ServerControlHubView(self, interaction.guild, doc, interaction.user)
        await interaction.response.send_message(embed=panel.get_overview_embed(), view=panel)

    @commands.hybrid_command(name="premium_price", description="View Server Premium and User VIP plans and pricing calculator", aliases=["plans", "upgrade"])
    async def premium_price(self, ctx: commands.Context):
        view = DualPricingView(ctx.author, default_mode="server")
        embed = view.render_embed()
        if ctx.interaction:
            await ctx.interaction.response.send_message(embed=embed, view=view)
        else:
            await ctx.send(embed=embed, view=view)

    # ── Vanity Command Suite ──────────────────────────────────────────────────

    @commands.hybrid_command(name="vanity", description="Manage vanity status roles, leaderboards, and settings")
    @commands.guild_only()
    async def vanity(self, ctx: commands.Context):
        if not await self.is_premium_guild(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**: Vanity roles require an active server subscription. Use `/premium_price` to view tiers!", ephemeral=True)

        doc = await self.get_server_doc(ctx.guild.id)
        roles = doc.get("vanity_roles", {})
        tier = await self.get_premium_tier(ctx.guild.id)
        cfg = SERVER_TIERS.get(tier, SERVER_TIERS["FREE"])
        max_slots = cfg["features"].get("vanity_roles", 0)

        embed = discord.Embed(
            title=f"🎭 Vanity Roles Dashboard · {ctx.guild.name}",
            description=f"Plan: **{cfg['display_name']}** · Quota: {_quota_meter(len(roles), max_slots)}",
            color=PREMIUM_COLOR,
            timestamp=utcnow(),
        )
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        if roles:
            lines = []
            for kw, rid in roles.items():
                r = ctx.guild.get_role(int(rid)) if str(rid).isdigit() else None
                lines.append(f"• `{kw}` ➔ {r.mention if r else f'`{rid}`'} (`{len(r.members) if r else 0}` supporters)")
            embed.add_field(name="Active Mappings", value="\n".join(lines), inline=False)
        else:
            embed.add_field(name="Active Mappings", value="*No triggers mapped yet. Use `n!vanity_add <trigger> @role` to create one!*", inline=False)

        embed.add_field(
            name="⚡ Management Commands",
            value=(
                "• `n!vanity_add <trigger> @role` — Add a vanity trigger\n"
                "• `n!vanity_del <trigger>` — Remove a trigger\n"
                "• `/vanity_sync` — Run immediate live sweep across server\n"
                "• `n!vanity_channel #channel` — Set celebration announcement channel"
            ),
            inline=False,
        )
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="vanity_sync", description="Run an immediate live sweep to award/revoke vanity status roles")
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def vanity_sync(self, ctx: commands.Context):
        if not await self.is_premium_guild(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.", ephemeral=True)

        if ctx.interaction:
            await ctx.interaction.response.defer()
            audit = await self.run_vanity_sweep(ctx.guild)
            report = discord.Embed(
                title="🔄 Real-Time Vanity Audit Complete",
                description=(
                    f"• **Members Scanned:** `{audit['scanned']}`\n"
                    f"• **Roles Awarded:** `{audit['added']}`\n"
                    f"• **Roles Revoked:** `{audit['removed']}`\n"
                    f"• **Active Supporters:** `{audit['supporters']}`\n"
                    f"• **Execution Duration:** `{audit['duration_ms']:.1f}ms`"
                ),
                color=SUCCESS_COLOR,
                timestamp=utcnow(),
            )
            await ctx.interaction.followup.send(embed=report)
        else:
            msg = await ctx.send("🔄 Scanning member presences across the server...")
            audit = await self.run_vanity_sweep(ctx.guild)
            report = discord.Embed(
                title="🔄 Real-Time Vanity Audit Complete",
                description=(
                    f"• **Members Scanned:** `{audit['scanned']}`\n"
                    f"• **Roles Awarded:** `{audit['added']}`\n"
                    f"• **Roles Revoked:** `{audit['removed']}`\n"
                    f"• **Active Supporters:** `{audit['supporters']}`\n"
                    f"• **Execution Duration:** `{audit['duration_ms']:.1f}ms`"
                ),
                color=SUCCESS_COLOR,
                timestamp=utcnow(),
            )
            await msg.edit(content=None, embed=report)

    @commands.command(name="vanity_add")
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def vanity_add(self, ctx: commands.Context, trigger: str, *, role: discord.Role):
        """Map a custom status keyword to a vanity role."""
        if not await self.is_premium_guild(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**: Use `/premium_price` to view upgrade tiers.")

        tier = await self.get_premium_tier(ctx.guild.id)
        cfg = SERVER_TIERS.get(tier, SERVER_TIERS["FREE"])
        max_slots = cfg["features"].get("vanity_roles", 0)

        doc = await self.get_server_doc(ctx.guild.id)
        current_roles = doc.get("vanity_roles", {})

        if max_slots != -1 and len(current_roles) >= max_slots:
            return await ctx.send(f"❌ **Slot Limit Reached**: Your **{tier}** plan allows up to `{max_slots}` vanity roles.")

        if role == ctx.guild.default_role or role.managed:
            return await ctx.send("❌ Cannot assign `@everyone` or managed/bot integration roles.")
        if role >= ctx.guild.me.top_role:
            return await ctx.send(f"❌ The role {role.mention} is higher than or equal to my highest role! Move my role above it in Server Settings.")

        trigger_clean = trigger.strip()
        await self.col_server.update_one(
            {"_id": ctx.guild.id},
            {"$set": {f"vanity_roles.{trigger_clean}": str(role.id)}},
            upsert=True,
        )
        await ctx.send(f"✅ Mapped status keyword `{trigger_clean}` ➔ {role.mention}!")

    @commands.command(name="vanity_del", aliases=["vanity_remove", "vanity_delete"])
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def vanity_del(self, ctx: commands.Context, trigger: str):
        """Remove a vanity keyword mapping."""
        if not await self.is_premium_guild(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.")
        trigger_clean = trigger.strip()
        await self.col_server.update_one({"_id": ctx.guild.id}, {"$unset": {f"vanity_roles.{trigger_clean}": ""}})
        await ctx.send(f"✅ Removed vanity mapping for `{trigger_clean}`.")

    @commands.command(name="vanity_channel")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def vanity_channel(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        """Set or disable the celebration channel for vanity status announcements."""
        if not await self.is_premium_guild(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.")

        if channel is None:
            await self.col_server.update_one({"_id": ctx.guild.id}, {"$unset": {"vanity_settings.channel_id": ""}})
            return await ctx.send("✅ Disabled vanity status celebration announcements.")

        await self.col_server.update_one({"_id": ctx.guild.id}, {"$set": {"vanity_settings.channel_id": channel.id}}, upsert=True)
        await ctx.send(f"✅ Vanity celebration announcements will now be sent to {channel.mention}!")

    # ── Owner Commands ────────────────────────────────────────────────────────

    @commands.command(name="set_premium")
    @commands.is_owner()
    async def set_premium(self, ctx: commands.Context, guild_id: Optional[str] = None, tier: str = "PRO", days: int = 30):
        """[Owner] Grant or update server premium subscription."""
        if guild_id:
            try:
                gid = int(guild_id)
            except ValueError:
                return await ctx.send("Guild ID must be a numeric Discord server ID.")
        elif ctx.guild:
            gid = ctx.guild.id
        else:
            return await ctx.send("Provide a guild ID when running this command in DMs.")

        tier = str(tier or "PRO").strip().upper()
        if tier not in SERVER_TIERS:
            return await ctx.send(f"Unknown tier. Valid: {' | '.join(SERVER_TIERS)}")
        if days != -1 and days < 1:
            return await ctx.send("Duration must be at least 1 day, or -1 for permanent.")

        expires = None if days == -1 or tier == "GRANDFATHERED" else utcnow() + timedelta(days=days)
        metadata = {
            "purchased_by": ctx.author.id,
            "purchased_at": utcnow().isoformat(),
            "payment_method": "Manual",
            "notes": f"Set by {ctx.author}",
        }

        if self.col_server is not None:
            try:
                await self.col_server.update_one(
                    {"_id": gid},
                    {"$set": {**metadata, "tier": tier, "expires_at": expires}},
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Premium grant failed in MongoDB: %s", exc)
                return await ctx.send("MongoDB could not save the premium grant. No grant was reported as successful.")

        try:
            # Mirror entitlement state locally so it survives a later short database outage.
            self._save_local_server_subscription(gid, tier, expires, **metadata)
        except Exception as exc:
            if self.col_server is None:
                logger.error("Could not save premium grant locally: %s", exc)
                return await ctx.send("Could not save premium to the local fallback.")
            logger.warning("Could not mirror premium grant into local JSON: %s", exc)

        active = tier in PAID_SERVER_TIERS and (tier == "GRANDFATHERED" or not _is_expired({"expires_at": expires}))
        if active:
            self.bot.premium_guild_ids.add(gid)
            self.bot.premium_guild_tiers[gid] = tier
        else:
            self.bot.premium_guild_ids.discard(gid)
            self.bot.premium_guild_tiers.pop(gid, None)
        await ctx.send(f"Set server premium for {gid} to {tier} ({'Permanent' if days == -1 or tier == 'GRANDFATHERED' else f'{days} days'}).")

    @app_commands.command(name="premium_grant", description="Grant Server Premium to a Discord server (bot owner only)")
    @app_commands.describe(
        guild_id="Numeric Discord server ID",
        tier="Premium tier to grant",
        days="Duration in days; use -1 for permanent",
    )
    @app_commands.choices(tier=[
        app_commands.Choice(name="Basic", value="BASIC"),
        app_commands.Choice(name="Pro", value="PRO"),
        app_commands.Choice(name="Enterprise", value="ENTERPRISE"),
        app_commands.Choice(name="Custom", value="CUSTOM"),
        app_commands.Choice(name="Grandfathered (Lifetime)", value="GRANDFATHERED"),
    ])
    @app_commands.checks.is_owner()
    async def premium_grant_slash(
        self,
        interaction: discord.Interaction,
        guild_id: str,
        tier: str = "PRO",
        days: int = 30,
    ):
        try:
            gid = int(guild_id.strip())
        except (ValueError, AttributeError):
            return await interaction.response.send_message("Guild ID must be a numeric Discord server ID.", ephemeral=True)

        tier = str(tier or "PRO").strip().upper()
        if tier not in SERVER_TIERS or tier == "FREE":
            return await interaction.response.send_message("Choose Basic, Pro, Enterprise, Custom, or Grandfathered.", ephemeral=True)
        if days != -1 and days < 1:
            return await interaction.response.send_message("Duration must be at least 1 day, or -1 for permanent.", ephemeral=True)

        expires = None if days == -1 or tier == "GRANDFATHERED" else utcnow() + timedelta(days=days)
        metadata = {
            "purchased_by": interaction.user.id,
            "purchased_at": utcnow().isoformat(),
            "payment_method": "Manual",
            "notes": f"Set by {interaction.user}",
        }

        if self.col_server is not None:
            try:
                await self.col_server.update_one(
                    {"_id": gid},
                    {"$set": {**metadata, "tier": tier, "expires_at": expires}},
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Slash premium grant failed in MongoDB: %s", exc)
                return await interaction.response.send_message(
                    "MongoDB could not save the premium grant. No grant was reported as successful.",
                    ephemeral=True,
                )

        try:
            self._save_local_server_subscription(gid, tier, expires, **metadata)
        except Exception as exc:
            if self.col_server is None:
                logger.error("Could not save slash premium grant locally: %s", exc)
                return await interaction.response.send_message("Could not save premium to local storage.", ephemeral=True)
            logger.warning("Could not mirror slash premium grant locally: %s", exc)

        self.bot.premium_guild_ids.add(gid)
        self.bot.premium_guild_tiers[gid] = tier
        duration = "Permanent" if days == -1 or tier == "GRANDFATHERED" else f"{days} days"
        warning = ""
        if self.col_server is None:
            warning = "\n\nWarning: MongoDB is not connected. The entitlement is saved locally, but database-backed perks such as vanity roles, booster roles, and auto-responder settings need MongoDB to be available."
        await interaction.response.send_message(
            f"Granted {tier} Server Premium to guild {gid} for {duration}.{warning}",
            ephemeral=True,
        )

    @commands.command(name="set_user_vip")
    @commands.is_owner()
    async def set_user_vip(self, ctx: commands.Context, user: discord.User, tier: str = "VIP_PLUS", days: int = 30):
        """[Owner] Grant or update personal User VIP subscription."""
        if self.col_user is None:
            return await ctx.send("❌ MongoDB not connected.")
        tier = tier.upper()
        if tier not in USER_TIERS:
            return await ctx.send(f"❌ Unknown tier. Valid: `{' | '.join(USER_TIERS)}`")

        expires = None if days == -1 else utcnow() + timedelta(days=days)
        await self.col_user.update_one(
            {"_id": user.id},
            {"$set": {
                "tier":         tier,
                "expires_at":   expires,
                "activated_at": utcnow(),
                "server_passes": USER_TIERS[tier]["features"].get("server_passes", 0),
            }},
            upsert=True,
        )
        self.bot.premium_user_ids.add(user.id)
        self.bot.premium_user_tiers[user.id] = tier
        await ctx.send(f"✅ Set User VIP for {user.mention} (`{user.id}`) to **{tier}** ({'Permanent' if days == -1 else f'{days}d'}).")

    @commands.command(name="revoke_premium")
    @commands.is_owner()
    async def revoke_premium(self, ctx: commands.Context, guild_id: Optional[str] = None):
        """[Owner] Revoke server premium."""
        if guild_id:
            try:
                gid = int(guild_id)
            except ValueError:
                return await ctx.send("Guild ID must be a numeric Discord server ID.")
        elif ctx.guild:
            gid = ctx.guild.id
        else:
            return await ctx.send("Provide a guild ID when running this command in DMs.")

        now = utcnow()
        if self.col_server is not None:
            try:
                await self.col_server.update_one(
                    {"_id": gid},
                    {"$set": {"tier": "FREE", "expires_at": now}},
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Could not revoke premium in MongoDB: %s", exc)
                return await ctx.send("Database could not save the revocation; the grant remains unchanged.")

        try:
            self._save_local_server_subscription(gid, "FREE", now, revoked_at=now.isoformat())
        except Exception as exc:
            if self.col_server is None:
                logger.error("Could not revoke premium in local storage: %s", exc)
                return await ctx.send("Could not save the revocation.")
            logger.warning("Could not mirror premium revocation into local JSON: %s", exc)

        self.bot.premium_guild_ids.discard(gid)
        self.bot.premium_guild_tiers.pop(gid, None)
        await ctx.send(f"Revoked server premium from {gid}.")

    @commands.command(name="revoke_user_vip")
    @commands.is_owner()
    async def revoke_user_vip(self, ctx: commands.Context, user: discord.User):
        """[Owner] Revoke user VIP."""
        await self.col_user.update_one({"_id": user.id}, {"$set": {"tier": "FREE", "expires_at": utcnow()}}, upsert=True)
        self.bot.premium_user_ids.discard(user.id)
        self.bot.premium_user_tiers.pop(user.id, None)
        await ctx.send(f"✅ Revoked VIP from {user.mention}.")


async def setup(bot: commands.Bot):
    await bot.add_cog(Premium(bot))
    logger.debug("Loaded Premium Cog")

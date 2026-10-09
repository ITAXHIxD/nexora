"""
cogs/premium/user_vip.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Personal User VIP Management Suite for Nexora.

Allows VIP subscribers to:
  • Set custom bot embed accent color (`/vip color <hex>`)
  • Equip and display exclusive VIP badges (`/vip badge <badge>`)
  • Activate Server Passes to gift Server Premium to any server (`/vip pass <guild_id>`)
  • View their personal VIP dashboard (`/vip`)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional

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

VIP_BADGES = {
    "crown":     {"emoji": "👑", "label": "Golden Crown VIP"},
    "star":      {"emoji": "⭐", "label": "Starlight VIP"},
    "diamond":   {"emoji": "💎", "label": "Crystal Diamond VIP"},
    "fire":      {"emoji": "🔥", "label": "Inferno VIP"},
    "galaxy":    {"emoji": "🌌", "label": "Celestial VIP"},
}


class UserVIP(commands.Cog):
    """Personal cross-server VIP perks, styling, and server pass activation."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_user_col(self):
        db = getattr(self.bot, "mongo_db", None)
        return db["user_premium"] if db is not None else None

    def _get_server_col(self):
        db = getattr(self.bot, "mongo_db", None)
        return db["premium"] if db is not None else None

    async def _is_vip(self, user_id: int) -> bool:
        checker = getattr(self.bot, "is_premium_user", None)
        if checker:
            return await checker(user_id)
        return False

    # ── Hybrid VIP Group ──────────────────────────────────────────────────────

    @commands.hybrid_group(name="vip", description="View and manage your personal VIP perks, badges, and colors", fallback="dashboard")
    async def vip(self, ctx: commands.Context):
        """View your personal VIP dashboard."""
        col = self._get_user_col()
        doc = await col.find_one({"_id": ctx.author.id}) if col is not None else None

        is_vip = await self._is_vip(ctx.author.id)
        tier = doc.get("tier", "FREE") if doc else "FREE"

        embed = discord.Embed(
            title=f"👑 Nexora Personal VIP · {ctx.author.display_name}",
            color=doc.get("custom_color") or PREMIUM_COLOR if is_vip else 0x95A5A6,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)

        if is_vip:
            embed.description = f"### Status: 🟢 **{tier} Active**\n> Your personal superpowers are active across all servers!"
            custom_color = doc.get("custom_color")
            color_str = f"`#{custom_color:06X}`" if custom_color else "*Default (Blurple)*"
            badge_key = doc.get("badge", "crown")
            badge_info = VIP_BADGES.get(badge_key, VIP_BADGES["crown"])
            passes = doc.get("server_passes", 0)

            embed.add_field(name="🎨 Custom Embed Color", value=color_str, inline=True)
            embed.add_field(name="🏷️ Equipped Badge", value=f"{badge_info['emoji']} {badge_info['label']}", inline=True)
            embed.add_field(name="🎟️ Server Passes", value=f"`{passes}` available to activate", inline=True)

            embed.add_field(
                name="🛠️ VIP Actions",
                value=(
                    "• `/vip color <hex_or_preset>` — Choose custom embed color\n"
                    "• `/vip badge <badge>` — Change profile badge\n"
                    "• `/vip pass <guild_id>` — Grant Server Premium to any server!"
                ),
                inline=False,
            )
        else:
            embed.description = (
                "### Status: ⚪ **Standard Free User**\n\n"
                "Unlock cross-server superpowers with **Nexora VIP**:\n"
                "• 🎨 Custom bot embed colors on all commands\n"
                "• 👑 VIP golden badges on profile & avatar\n"
                "• ⏰ Up to **50** concurrent reminders with priority alerts\n"
                "• 🎟️ Free Server Premium Activation Pass (VIP Plus)\n\n"
                "Use `/premium_price` to view VIP tiers starting at just $2.99/mo!"
            )

        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        await ctx.send(embed=embed)

    @vip.command(name="color", description="Set your personal custom embed color for bot replies")
    @app_commands.describe(color="Hex color (e.g. #00D2FF) or 'reset'")
    async def vip_color(self, ctx: commands.Context, color: str):
        if not await self._is_vip(ctx.author.id):
            return await ctx.send("❌ **VIP Required**: Custom embed styling requires an active VIP subscription. Use `/premium_price` to upgrade!", ephemeral=True)

        col = self._get_user_col()
        if col is None:
            return await ctx.send("❌ Database unavailable.", ephemeral=True)

        if color.lower().strip() in ("reset", "default", "none"):
            await col.update_one({"_id": ctx.author.id}, {"$unset": {"custom_color": ""}})
            self.bot.premium_user_colors.pop(ctx.author.id, None)
            return await ctx.send("✅ Reset your custom embed color to default!")

        clean = color.lstrip("#").replace("0x", "").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{6}", clean):
            return await ctx.send("❌ Invalid color format. Please enter a valid 6-digit hex code like `#FF3366` or `#00D2FF`.", ephemeral=True)

        val = int(clean, 16)
        await col.update_one({"_id": ctx.author.id}, {"$set": {"custom_color": val}}, upsert=True)
        self.bot.premium_user_colors[ctx.author.id] = val

        embed = discord.Embed(
            title="🎨 Custom Accent Color Updated",
            description=f"Your personal bot embed color has been updated to `#{val:06X}`!",
            color=val,
        )
        await ctx.send(embed=embed)

    @vip.command(name="badge", description="Equip an exclusive VIP profile badge")
    @app_commands.describe(badge="Choose a badge style")
    @app_commands.choices(badge=[
        app_commands.Choice(name="👑 Golden Crown", value="crown"),
        app_commands.Choice(name="⭐ Starlight", value="star"),
        app_commands.Choice(name="💎 Crystal Diamond", value="diamond"),
        app_commands.Choice(name="🔥 Inferno", value="fire"),
        app_commands.Choice(name="🌌 Celestial Galaxy", value="galaxy"),
    ])
    async def vip_badge(self, ctx: commands.Context, badge: app_commands.Choice[str]):
        if not await self._is_vip(ctx.author.id):
            return await ctx.send("❌ **VIP Required**.", ephemeral=True)

        col = self._get_user_col()
        if col is None:
            return await ctx.send("❌ Database unavailable.", ephemeral=True)

        await col.update_one({"_id": ctx.author.id}, {"$set": {"badge": badge.value}}, upsert=True)
        b_info = VIP_BADGES.get(badge.value, VIP_BADGES["crown"])
        await ctx.send(f"✅ Equipped **{b_info['emoji']} {b_info['label']}** badge to your profile!")

    @vip.command(name="pass", description="Redeem a Server Pass to activate Server Premium for any server")
    @app_commands.describe(guild_id="The ID of the server to grant Server Premium to")
    async def vip_pass(self, ctx: commands.Context, guild_id: str):
        if not await self._is_vip(ctx.author.id):
            return await ctx.send("❌ **VIP Required**.", ephemeral=True)

        col_user = self._get_user_col()
        col_server = self._get_server_col()
        if not col_user or not col_server:
            return await ctx.send("❌ Database unavailable.", ephemeral=True)

        doc = await col_user.find_one({"_id": ctx.author.id})
        passes = doc.get("server_passes", 0) if doc else 0
        if passes <= 0:
            return await ctx.send("❌ You don't have any Server Passes remaining. Upgrade to **VIP Plus** or contact the bot owner!", ephemeral=True)

        if not guild_id.isdigit():
            return await ctx.send("❌ Please provide a valid numeric Server ID.", ephemeral=True)

        gid = int(guild_id)
        g = self.bot.get_guild(gid)
        g_name = g.name if g else f"Guild ID {gid}"

        # Deduct 1 pass and activate Pro on server for 30 days
        await col_user.update_one({"_id": ctx.author.id}, {"$inc": {"server_passes": -1}})
        expires = datetime.now(timezone.utc) + timedelta(days=30)

        await col_server.update_one(
            {"_id": gid},
            {"$set": {
                "tier": "PRO",
                "expires_at": expires,
                "purchased_by": ctx.author.id,
                "purchased_at": datetime.now(timezone.utc),
                "payment_method": "User VIP Pass",
                "notes": f"Activated via VIP Pass by {ctx.author} ({ctx.author.id})",
            }},
            upsert=True,
        )
        self.bot.premium_guild_ids.add(gid)
        self.bot.premium_guild_tiers[gid] = "PRO"

        embed = discord.Embed(
            title="🎟️ Server Pass Redeemed!",
            description=f"Congratulations! You have activated **30 Days of PRO Server Premium** on **{g_name}** (`{gid}`).",
            color=SUCCESS_COLOR,
        )
        embed.add_field(name="Server", value=g_name, inline=True)
        embed.add_field(name="Passes Left", value=f"`{passes - 1}`", inline=True)
        embed.set_footer(text="Thank you for supporting Nexora!")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(UserVIP(bot))
    logger.debug("Loaded UserVIP Cog")

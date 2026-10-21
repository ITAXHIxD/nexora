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
from datetime import datetime, timezone, timedelta
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.premium_storage import load_premium_data, save_premium_data
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


async def _is_vip_admin(ctx: commands.Context) -> bool:
    dev_ids = getattr(ctx.bot, "developer_ids", set())
    if ctx.author.id in dev_ids:
        return True
    return await ctx.bot.is_owner(ctx.author)


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

    def _get_local_user_doc(self, user_id: int) -> dict:
        try:
            data = load_premium_data()
            sub = data.get("user_subscriptions", {}).get(str(user_id), {})
            if isinstance(sub, dict) and sub:
                doc = dict(sub)
                doc["_id"] = user_id
                return doc
        except Exception as exc:
            logger.debug("Failed reading local user VIP doc: %s", exc)
        return {}

    def _save_local_user_doc(self, user_id: int, updates: dict) -> None:
        try:
            data = load_premium_data()
            user_subs = data.setdefault("user_subscriptions", {})
            key = str(user_id)
            current = user_subs.get(key, {})
            if not isinstance(current, dict):
                current = {}
            for k, v in updates.items():
                if v is None:
                    current.pop(k, None)
                else:
                    current[k] = v
            user_subs[key] = current
            save_premium_data(data)
        except Exception as exc:
            logger.error("Failed saving local user VIP doc: %s", exc)

    async def _get_user_doc(self, user_id: int) -> dict:
        col = self._get_user_col()
        if col is not None:
            try:
                doc = await col.find_one({"_id": user_id})
                if doc:
                    return doc
            except Exception as exc:
                logger.warning("User VIP Mongo read failed, using local: %s", exc)
        return self._get_local_user_doc(user_id)

    async def _is_vip(self, user_id: int) -> bool:
        checker = getattr(self.bot, "is_premium_user", None)
        if callable(checker):
            res = checker(user_id)
            if hasattr(res, "__await__"):
                res = await res
            return bool(res)
        return False

    # ── Hybrid VIP Group ──────────────────────────────────────────────────────

    @commands.hybrid_group(name="vip", description="View and manage your personal VIP perks, badges, and colors", fallback="dashboard")
    async def vip(self, ctx: commands.Context):
        """View your personal VIP dashboard."""
        doc = await self._get_user_doc(ctx.author.id)
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
        if color.lower().strip() in ("reset", "default", "none"):
            if col is not None:
                try:
                    await col.update_one({"_id": ctx.author.id}, {"$unset": {"custom_color": ""}})
                except Exception as exc:
                    logger.debug("Mongo unset custom_color error: %s", exc)
            self._save_local_user_doc(ctx.author.id, {"custom_color": None})
            self.bot.premium_user_colors.pop(ctx.author.id, None)
            return await ctx.send("✅ Reset your custom embed color to default!")

        clean = color.lstrip("#").replace("0x", "").strip()
        if not re.fullmatch(r"[0-9a-fA-F]{6}", clean):
            return await ctx.send("❌ Invalid color format. Please enter a valid 6-digit hex code like `#FF3366` or `#00D2FF`.", ephemeral=True)

        val = int(clean, 16)
        if col is not None:
            try:
                await col.update_one({"_id": ctx.author.id}, {"$set": {"custom_color": val}}, upsert=True)
            except Exception as exc:
                logger.debug("Mongo set custom_color error: %s", exc)
        self._save_local_user_doc(ctx.author.id, {"custom_color": val})
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
        if col is not None:
            try:
                await col.update_one({"_id": ctx.author.id}, {"$set": {"badge": badge.value}}, upsert=True)
            except Exception as exc:
                logger.debug("Mongo set badge error: %s", exc)
        self._save_local_user_doc(ctx.author.id, {"badge": badge.value})
        b_info = VIP_BADGES.get(badge.value, VIP_BADGES["crown"])
        await ctx.send(f"✅ Equipped **{b_info['emoji']} {b_info['label']}** badge to your profile!")

    @vip.command(name="pass", description="Redeem a Server Pass to activate Server Premium for any server")
    @app_commands.describe(guild_id="The ID of the server to grant Server Premium to")
    async def vip_pass(self, ctx: commands.Context, guild_id: str):
        if not await self._is_vip(ctx.author.id):
            return await ctx.send("❌ **VIP Required**.", ephemeral=True)

        user_doc = await self._get_user_doc(ctx.author.id)
        passes = user_doc.get("server_passes", 0) if user_doc else 0
        if passes <= 0:
            return await ctx.send("❌ You don't have any Server Passes remaining. Upgrade to **VIP Plus** or contact the bot owner!", ephemeral=True)

        clean_gid = guild_id.strip()
        if not clean_gid.isdigit():
            return await ctx.send("❌ Please provide a valid numeric Server ID.", ephemeral=True)

        gid = int(clean_gid)
        g = self.bot.get_guild(gid)
        g_name = g.name if g else f"Guild ID {gid}"

        col_user = self._get_user_col()
        col_server = self._get_server_col()
        expires = datetime.now(timezone.utc) + timedelta(days=30)
        now_iso = datetime.now(timezone.utc).isoformat()

        if col_user is not None:
            try:
                await col_user.update_one({"_id": ctx.author.id}, {"$inc": {"server_passes": -1}})
            except Exception as exc:
                logger.error("Failed to deduct server pass in Mongo: %s", exc)

        self._save_local_user_doc(ctx.author.id, {"server_passes": max(0, passes - 1)})

        server_metadata = {
            "tier": "PRO",
            "expires_at": expires.isoformat(),
            "purchased_by": ctx.author.id,
            "purchased_at": now_iso,
            "payment_method": "User VIP Pass",
            "notes": f"Activated via VIP Pass by {ctx.author} ({ctx.author.id})",
        }

        if col_server is not None:
            try:
                await col_server.update_one(
                    {"_id": gid},
                    {"$set": {**server_metadata, "expires_at": expires, "purchased_at": datetime.now(timezone.utc)}},
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Failed to set server premium in Mongo via pass: %s", exc)

        # Mirror server subscription to local storage
        try:
            prem_data = load_premium_data()
            prem_data.setdefault("subscriptions", {})[str(gid)] = server_metadata
            save_premium_data(prem_data)
        except Exception as exc:
            logger.error("Failed to mirror server pass grant to local storage: %s", exc)

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

    @vip.command(name="grant", description="[Owner] Grant personal User VIP entitlement")
    @app_commands.describe(
        user="Discord user to grant VIP to",
        tier="VIP tier (VIP, VIP_PLUS, VIP_LIFETIME)",
        days="Duration in days (-1 for lifetime)",
        passes="Number of Server Passes to grant",
    )
    @app_commands.choices(tier=[
        app_commands.Choice(name="👑 VIP ($2.99/mo)", value="VIP"),
        app_commands.Choice(name="🌟 VIP Plus ($4.99/mo)", value="VIP_PLUS"),
        app_commands.Choice(name="💎 VIP Lifetime ($49.99)", value="VIP_LIFETIME"),
    ])
    async def vip_grant(
        self,
        ctx: commands.Context,
        user: discord.User,
        tier: Optional[app_commands.Choice[str]] = None,
        days: int = 30,
        passes: Optional[int] = None,
    ):
        if not await _is_vip_admin(ctx):
            return await ctx.send("❌ This command is restricted to the bot owner.", ephemeral=True)

        tier_val = tier.value if isinstance(tier, app_commands.Choice) else (str(tier).upper() if tier else "VIP")
        if tier_val not in ("VIP", "VIP_PLUS", "VIP_LIFETIME"):
            tier_val = "VIP"

        if tier_val == "VIP_LIFETIME":
            days = -1

        now = datetime.now(timezone.utc)
        if days == -1:
            expires = datetime(2099, 1, 1, tzinfo=timezone.utc)
        else:
            expires = now + timedelta(days=days)

        server_passes = passes if passes is not None else (1 if tier_val in ("VIP_PLUS", "VIP_LIFETIME") else 0)

        col_user = self._get_user_col()
        if col_user is not None:
            try:
                await col_user.update_one(
                    {"_id": user.id},
                    {
                        "$set": {
                            "tier": tier_val,
                            "expires_at": expires,
                            "activated_at": now.isoformat(),
                            "server_passes": server_passes,
                        }
                    },
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Mongo vip_grant failed: %s", exc)

        self._save_local_user_doc(
            user.id,
            {
                "tier": tier_val,
                "expires_at": expires.isoformat(),
                "activated_at": now.isoformat(),
                "server_passes": server_passes,
            },
        )

        self.bot.premium_user_ids.add(user.id)
        self.bot.premium_user_tiers[user.id] = tier_val

        dur_text = "Permanent / Lifetime" if days == -1 else f"{days} days"
        await ctx.send(f"✅ Granted **{tier_val}** ({dur_text}) with `{server_passes}` server pass(es) to {user.mention} (`{user.id}`).")

    @vip.command(name="revoke", description="[Owner] Revoke personal User VIP entitlement")
    @app_commands.describe(user="Discord user to revoke VIP from")
    async def vip_revoke(self, ctx: commands.Context, user: discord.User):
        if not await _is_vip_admin(ctx):
            return await ctx.send("❌ This command is restricted to the bot owner.", ephemeral=True)

        now = datetime.now(timezone.utc)
        col_user = self._get_user_col()
        if col_user is not None:
            try:
                await col_user.update_one(
                    {"_id": user.id},
                    {"$set": {"tier": "FREE", "expires_at": now, "revoked_at": now.isoformat()}},
                    upsert=True,
                )
            except Exception as exc:
                logger.error("Mongo vip_revoke failed: %s", exc)

        self._save_local_user_doc(
            user.id,
            {"tier": "FREE", "expires_at": now.isoformat(), "revoked_at": now.isoformat()},
        )

        self.bot.premium_user_ids.discard(user.id)
        self.bot.premium_user_tiers.pop(user.id, None)
        await ctx.send(f"✅ Revoked User VIP from {user.mention} (`{user.id}`).")


async def setup(bot: commands.Bot):
    await bot.add_cog(UserVIP(bot))
    logger.debug("Loaded UserVIP Cog")

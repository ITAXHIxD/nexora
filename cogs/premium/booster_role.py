"""
cogs/premium/booster_role.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Custom Nitro Booster Role Management Suite for Nexora Premium.

Permits server boosters in premium guilds to create, name, color,
and customize their own personal private role!

MongoDB: "premium" collection under `booster_roles` dict:
  {
    "_id": guild_id,
    "booster_roles": {
        "<user_id>": "<role_id>", ...
    },
    "booster_anchor": <role_id>  # Anchor role to place custom roles beneath
  }
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

COLOR_PRESETS = {
    "crimson":        0xE74C3C,
    "rose":           0xFF3366,
    "neon_pink":      0xFF1493,
    "sunset_orange":  0xFF6B35,
    "gold":           0xF1C40F,
    "lime":           0x2ECC71,
    "emerald":        0x00D68F,
    "cyan":           0x00D2FF,
    "electric_blue":  0x0070F3,
    "blurple":        0x5865F2,
    "royal_purple":   0x9B59B6,
    "amethyst":       0x8E44AD,
    "obsidian":       0x2B2D31,
    "silver":         0xBDC3C7,
    "pure_white":     0xFFFFFF,
}


def parse_color(color_input: str) -> Optional[discord.Color]:
    if not color_input:
        return None
    val = color_input.lower().strip()
    if val in COLOR_PRESETS:
        return discord.Color(COLOR_PRESETS[val])

    # Strip hash or 0x
    val = val.lstrip("#").replace("0x", "")
    if re.fullmatch(r"[0-9a-fA-F]{6}", val):
        try:
            return discord.Color(int(val, 16))
        except ValueError:
            return None
    return None


class BoosterRole(commands.Cog):
    """Custom personal booster role creation and customization."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _get_col(self):
        db = getattr(self.bot, "mongo_db", None)
        return db["premium"] if db is not None else None

    async def _is_premium(self, guild_id: int) -> bool:
        checker = getattr(self.bot, "is_premium_guild", None)
        if checker:
            return await checker(guild_id)
        return False

    async def _get_user_role_id(self, guild_id: int, user_id: int) -> Optional[int]:
        col = self._get_col()
        if col is None:
            return None
        doc = await col.find_one({"_id": guild_id})
        if not doc:
            return None
        roles_map = doc.get("booster_roles", {})
        rid = roles_map.get(str(user_id))
        return int(rid) if rid and str(rid).isdigit() else None

    async def _save_user_role(self, guild_id: int, user_id: int, role_id: Optional[int]):
        col = self._get_col()
        if col is None:
            return
        if role_id is None:
            await col.update_one({"_id": guild_id}, {"$unset": {f"booster_roles.{user_id}": ""}})
        else:
            await col.update_one({"_id": guild_id}, {"$set": {f"booster_roles.{user_id}": str(role_id)}}, upsert=True)

    async def _get_anchor(self, guild: discord.Guild) -> Optional[discord.Role]:
        col = self._get_col()
        if col is None:
            return None
        doc = await col.find_one({"_id": guild.id})
        if not doc:
            return None
        anchor_id = doc.get("booster_anchor")
        return guild.get_role(int(anchor_id)) if anchor_id else None

    # ── Hybrid Booster Role Command ───────────────────────────────────────────

    @commands.hybrid_group(name="booster_role", description="Create and manage your private personal booster role", fallback="info")
    @commands.guild_only()
    async def booster_role(self, ctx: commands.Context):
        """View your personal booster role information."""
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**: Custom Booster Roles require an active server subscription. Use `/premium_price` to learn more!", ephemeral=True)

        rid = await self._get_user_role_id(ctx.guild.id, ctx.author.id)
        if not rid:
            return await ctx.send("ℹ️ You don't have a personal booster role yet! Use `/booster_role create <name> [hex_color]` to create one.", ephemeral=True)

        role = ctx.guild.get_role(rid)
        if not role:
            await self._save_user_role(ctx.guild.id, ctx.author.id, None)
            return await ctx.send("⚠️ Your previous booster role was deleted. You can create a new one using `/booster_role create`.", ephemeral=True)

        hex_code = f"#{role.color.value:06X}"
        embed = discord.Embed(
            title="🚀 Your Custom Booster Role",
            color=role.color if role.color.value != 0 else PREMIUM_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.set_thumbnail(url=ctx.author.display_avatar.url)
        embed.add_field(name="Role Name", value=f"{role.mention} (`{role.name}`)", inline=True)
        embed.add_field(name="Color Code", value=f"`{hex_code}`", inline=True)
        embed.add_field(name="Hierarchy Position", value=f"`#{role.position}`", inline=True)
        embed.add_field(
            name="🛠️ Quick Actions",
            value=(
                "• `/booster_role color <hex>` — Change color\n"
                "• `/booster_role name <new_name>` — Rename role\n"
                "• `/booster_role delete` — Delete your custom role"
            ),
            inline=False,
        )
        embed.set_footer(text="Nexora Premium · Exclusive Server Booster Perk")
        await ctx.send(embed=embed)

    @booster_role.command(name="create", description="Create your personal server booster role")
    @commands.guild_only()
    @app_commands.describe(name="Name for your custom role", color="Hex color code (e.g. #FF3366) or preset name")
    async def booster_create(self, ctx: commands.Context, name: str, color: Optional[str] = None):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**: Custom Booster Roles require an active server subscription.", ephemeral=True)

        if not ctx.author.premium_since and not ctx.author.guild_permissions.administrator:
            return await ctx.send("❌ **Nitro Booster Required**: You must be actively boosting this server to create a custom booster role!", ephemeral=True)

        if not ctx.guild.me.guild_permissions.manage_roles:
            return await ctx.send("❌ I need the **Manage Roles** permission to create roles!", ephemeral=True)

        existing_rid = await self._get_user_role_id(ctx.guild.id, ctx.author.id)
        if existing_rid and ctx.guild.get_role(existing_rid):
            return await ctx.send(f"❌ You already have a custom role ({ctx.guild.get_role(existing_rid).mention})! Use `/booster_role color` or `/booster_role name` to customize it.", ephemeral=True)

        role_color = parse_color(color) if color else discord.Color.default()

        clean_name = name.strip()[:64]
        try:
            new_role = await ctx.guild.create_role(
                name=clean_name,
                color=role_color,
                reason=f"Nexora Booster Role for {ctx.author} ({ctx.author.id})",
            )
        except discord.Forbidden:
            return await ctx.send("❌ Missing permissions to create roles. Ensure my role is high enough.", ephemeral=True)

        # Position below anchor if exists
        anchor = await self._get_anchor(ctx.guild)
        if anchor and anchor.position > 1 and anchor < ctx.guild.me.top_role:
            try:
                positions = {new_role: max(1, anchor.position - 1)}
                await ctx.guild.edit_role_positions(positions)
            except Exception as e:
                logger.debug("Could not position booster role: %s", e)

        # Assign role to booster
        try:
            await ctx.author.add_roles(new_role, reason="Nexora Booster Role assignment")
        except Exception as e:
            logger.debug("Failed to assign new booster role: %s", e)

        await self._save_user_role(ctx.guild.id, ctx.author.id, new_role.id)

        embed = discord.Embed(
            title="🎉 Booster Role Created!",
            description=f"Congratulations {ctx.author.mention}! Your custom role {new_role.mention} is now active.",
            color=new_role.color if new_role.color.value != 0 else SUCCESS_COLOR,
        )
        embed.add_field(name="Role Name", value=f"`{new_role.name}`", inline=True)
        embed.add_field(name="Color Code", value=f"`#{new_role.color.value:06X}`", inline=True)
        await ctx.send(embed=embed)

    @booster_role.command(name="color", description="Change the color of your personal booster role")
    @commands.guild_only()
    @app_commands.describe(color="Hex code (e.g. #00D2FF) or preset (gold, crimson, cyan, neon_pink, etc.)")
    async def booster_color(self, ctx: commands.Context, color: str):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.", ephemeral=True)

        rid = await self._get_user_role_id(ctx.guild.id, ctx.author.id)
        if not rid:
            return await ctx.send("❌ You don't have a booster role. Create one with `/booster_role create`.", ephemeral=True)

        role = ctx.guild.get_role(rid)
        if not role:
            return await ctx.send("❌ Your custom role could not be found.", ephemeral=True)

        parsed = parse_color(color)
        if not parsed:
            presets_str = ", ".join(f"`{k}`" for k in list(COLOR_PRESETS.keys())[:8])
            return await ctx.send(f"❌ Invalid color. Use a 6-digit hex code (e.g. `#5865F2`) or preset ({presets_str}).", ephemeral=True)

        try:
            await role.edit(color=parsed, reason=f"Booster role color change by {ctx.author}")
        except discord.Forbidden:
            return await ctx.send("❌ Cannot edit role color due to role hierarchy. Please contact an admin.", ephemeral=True)

        hex_code = f"#{parsed.value:06X}"
        embed = discord.Embed(
            title="🎨 Role Color Updated",
            description=f"{role.mention} has been updated to `{hex_code}`!",
            color=parsed,
        )
        await ctx.send(embed=embed)

    @booster_role.command(name="name", description="Rename your personal booster role")
    @commands.guild_only()
    @app_commands.describe(name="New name for your role")
    async def booster_name(self, ctx: commands.Context, name: str):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.", ephemeral=True)

        rid = await self._get_user_role_id(ctx.guild.id, ctx.author.id)
        if not rid:
            return await ctx.send("❌ You don't have a booster role. Create one with `/booster_role create`.", ephemeral=True)

        role = ctx.guild.get_role(rid)
        if not role:
            return await ctx.send("❌ Your custom role could not be found.", ephemeral=True)

        clean_name = name.strip()[:64]
        try:
            await role.edit(name=clean_name, reason=f"Booster role rename by {ctx.author}")
        except discord.Forbidden:
            return await ctx.send("❌ Cannot edit role name due to role hierarchy.", ephemeral=True)

        await ctx.send(f"✅ Renamed your custom role to **{clean_name}**!")

    @booster_role.command(name="delete", description="Delete your personal booster role")
    @commands.guild_only()
    async def booster_delete(self, ctx: commands.Context):
        rid = await self._get_user_role_id(ctx.guild.id, ctx.author.id)
        if not rid:
            return await ctx.send("❌ You don't have a booster role.", ephemeral=True)

        role = ctx.guild.get_role(rid)
        if role:
            try:
                await role.delete(reason=f"Deleted by booster {ctx.author}")
            except Exception as e:
                logger.debug("Failed to delete booster role: %s", e)

        await self._save_user_role(ctx.guild.id, ctx.author.id, None)
        await ctx.send("✅ Your custom booster role has been deleted.")

    # ── Admin Anchor Setup ────────────────────────────────────────────────────

    @commands.command(name="booster_anchor")
    @commands.has_permissions(manage_roles=True)
    @commands.guild_only()
    async def booster_anchor(self, ctx: commands.Context, role: Optional[discord.Role] = None):
        """Set or clear the anchor role below which booster roles will be positioned."""
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**.")

        col = self._get_col()
        if col is None:
            return await ctx.send("❌ Database unavailable.")

        if role is None:
            await col.update_one({"_id": ctx.guild.id}, {"$unset": {"booster_anchor": ""}})
            return await ctx.send("✅ Cleared booster anchor role.")

        await col.update_one({"_id": ctx.guild.id}, {"$set": {"booster_anchor": role.id}}, upsert=True)
        await ctx.send(f"✅ Booster anchor set to {role.mention}. New booster roles will be positioned directly beneath it!")

    # ── Member Unboost / Leave Event ──────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_update(self, before: discord.Member, after: discord.Member):
        if before.premium_since and not after.premium_since:
            # Member lost booster status!
            rid = await self._get_user_role_id(after.guild.id, after.id)
            if rid:
                role = after.guild.get_role(rid)
                if role and role < after.guild.me.top_role:
                    try:
                        await role.delete(reason=f"Nexora Booster Role Cleanup: {after} is no longer boosting the server")
                        await self._save_user_role(after.guild.id, after.id, None)
                        logger.info("Cleaned up booster role %s for unboosted member %s", rid, after.id)
                    except Exception as e:
                        logger.debug("Booster cleanup error: %s", e)


async def setup(bot: commands.Bot):
    await bot.add_cog(BoosterRole(bot))
    logger.debug("Loaded BoosterRole Cog")

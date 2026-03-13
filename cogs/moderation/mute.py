"""
cogs/core/premium.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MongoDB-backed premium system for Nexora.

Collection: "premium"
Document schema:
  {
    _id:            guild_id (int),
    tier:           "FREE" | "BASIC" | "PRO" | "ULTRA" | "GRANDFATHERED",
    expires_at:     datetime | None  (None = permanent),
    purchased_by:   user_id (int),
    purchased_at:   datetime,
    payment_method: str,
    amount_paid:    float,
    notes:          str,
  }

Commands:
  n!premium / /premium           — check this server's premium status
  n!set_premium (owner only)     — grant / extend premium
  n!revoke_premium (owner only)  — remove premium
  n!premium_price                — show pricing info
  n!vanity                       — show vanity role config (premium only)

bot.is_premium_guild(guild_id) is patched onto the bot object in cog_load.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

# ── Tier config ────────────────────────────────────────────────────────────────

TIERS = {
    "FREE":          {"emoji": "🆓", "color": discord.Color.greyple(),             "vanity_slots": 0},
    "BASIC":         {"emoji": "⭐", "color": discord.Color.from_rgb(100,149,237), "vanity_slots": 1},
    "PRO":           {"emoji": "💎", "color": discord.Color.from_rgb(138,43,226),  "vanity_slots": 3},
    "ULTRA":         {"emoji": "👑", "color": discord.Color.gold(),                "vanity_slots": 5},
    "GRANDFATHERED": {"emoji": "🏆", "color": discord.Color.from_rgb(255,140,0),   "vanity_slots": 5},
}

PRICING = [
    {
        "tier":     "BASIC",
        "monthly":  "$1",
        "yearly":   "$10",
        "features": ["1 Vanity Role", "Status Matching", "Basic priority support"],
    },
    {
        "tier":     "PRO",
        "monthly":  "$3",
        "yearly":   "$30",
        "features": ["3 Vanity Roles", "Audit logging", "Priority support"],
    },
    {
        "tier":     "ULTRA",
        "monthly":  "$5",
        "yearly":   "$50",
        "features": ["5 Vanity Roles", "Audit logging", "Top priority support", "All future features"],
    },
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _is_expired(doc: dict) -> bool:
    exp = doc.get("expires_at")
    if exp is None:
        return False  # permanent
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp)
        except ValueError:
            return False
    # Make timezone-aware if naive
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    return exp < utcnow()


def _fmt_expiry(doc: dict) -> str:
    exp = doc.get("expires_at")
    if exp is None:
        return "∞ Permanent"
    if isinstance(exp, str):
        try:
            exp = datetime.fromisoformat(exp)
        except ValueError:
            return "Unknown"
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < utcnow():
        return "❌ Expired"
    ts = int(exp.timestamp())
    return f"<t:{ts}:R>  (<t:{ts}:D>)"


# ── Cog ────────────────────────────────────────────────────────────────────────

class Premium(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.col = None  # set in cog_load

    async def cog_load(self):
        db = getattr(self.bot, "mongo_db", None)
        if db is not None:
            self.col = db["premium"]
            logger.info("Premium: connected to MongoDB")
        else:
            logger.warning("Premium: mongo_db unavailable — premium checks will always return False")

        # Patch bot so other cogs can call bot.is_premium_guild(guild_id)
        async def _is_premium(guild_id: int) -> bool:
            return await self.is_premium(guild_id)

        self.bot.is_premium_guild = _is_premium

    # ── Core checks ────────────────────────────────────────────────────────────

    async def get_doc(self, guild_id: int) -> dict:
        if self.col is None:
            return {}
        doc = await self.col.find_one({"_id": guild_id})
        return doc or {}

    async def is_premium(self, guild_id: int) -> bool:
        doc = await self.get_doc(guild_id)
        if not doc:
            return False
        if doc.get("tier") == "GRANDFATHERED":
            return True
        if _is_expired(doc):
            return False
        return doc.get("tier", "FREE") != "FREE"

    async def get_tier(self, guild_id: int) -> str:
        doc = await self.get_doc(guild_id)
        if not doc:
            return "FREE"
        if _is_expired(doc):
            return "FREE"
        return doc.get("tier", "FREE")

    async def get_vanity_roles(self, guild_id: int) -> dict:
        doc = await self.get_doc(guild_id)
        return doc.get("vanity_roles", {})

    # ── /premium ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="premium",
        description="Check this server's premium status",
    )
    @commands.guild_only()
    async def premium_status(self, ctx: commands.Context):
        await ctx.defer()
        doc  = await self.get_doc(ctx.guild.id)
        tier = doc.get("tier", "FREE")

        # Handle expired subs
        if tier != "FREE" and tier != "GRANDFATHERED" and _is_expired(doc):
            tier = "FREE"

        tier_info = TIERS.get(tier, TIERS["FREE"])
        is_prem   = tier not in ("FREE",) and not _is_expired(doc)

        embed = discord.Embed(
            title=f"{tier_info['emoji']} {ctx.guild.name}  —  Premium Status",
            color=tier_info["color"],
            timestamp=utcnow(),
        )

        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        embed.add_field(
            name="📦 Tier",
            value=f"**{tier}** {tier_info['emoji']}",
            inline=True,
        )
        embed.add_field(
            name="✅ Active",
            value="Yes" if is_prem else "No",
            inline=True,
        )
        embed.add_field(
            name="🎭 Vanity Slots",
            value=str(tier_info["vanity_slots"]),
            inline=True,
        )

        if doc:
            embed.add_field(
                name="🕐 Expires",
                value=_fmt_expiry(doc),
                inline=True,
            )

            purchased_by = doc.get("purchased_by")
            if purchased_by:
                user = self.bot.get_user(int(purchased_by))
                embed.add_field(
                    name="🛒 Purchased By",
                    value=user.mention if user else f"`{purchased_by}`",
                    inline=True,
                )

            purchased_at = doc.get("purchased_at")
            if purchased_at:
                if isinstance(purchased_at, str):
                    try:
                        purchased_at = datetime.fromisoformat(purchased_at)
                    except ValueError:
                        purchased_at = None
                if purchased_at:
                    ts = int(purchased_at.timestamp()) if purchased_at.tzinfo else int(purchased_at.replace(tzinfo=timezone.utc).timestamp())
                    embed.add_field(name="📅 Since", value=f"<t:{ts}:D>", inline=True)

            if doc.get("notes"):
                embed.add_field(name="📝 Notes", value=doc["notes"], inline=False)

        if not is_prem:
            embed.add_field(
                name="🚀 Upgrade",
                value="Use `n!premium_price` to see plans — starting at **$1/month**!",
                inline=False,
            )

        embed.set_footer(text="Nexora Premium")
        await ctx.send(embed=embed)

    # ── /set_premium (owner only) ──────────────────────────────────────────────

    @commands.command(name="set_premium")
    @commands.is_owner()
    async def set_premium(
        self,
        ctx: commands.Context,
        guild_id: Optional[str] = None,
        tier: str = "ULTRA",
        days: int = 30,
    ):
        """
        [Owner] Grant premium to a guild.
        Usage: n!set_premium [guild_id] [tier] [days]
          days = -1 for permanent
          tier = BASIC | PRO | ULTRA | GRANDFATHERED
        """
        if self.col is None:
            return await ctx.send("❌ MongoDB not connected.")

        gid     = int(guild_id) if guild_id else ctx.guild.id
        tier    = tier.upper()
        expires = None if days == -1 else utcnow() + timedelta(days=days)

        if tier not in TIERS:
            return await ctx.send(
                f"❌ Unknown tier `{tier}`. Valid: {', '.join(TIERS)}", ephemeral=True
            )

        doc = {
            "_id":            gid,
            "tier":           tier,
            "expires_at":     expires,
            "purchased_by":   ctx.author.id,
            "purchased_at":   utcnow(),
            "payment_method": "Manual",
            "amount_paid":    0,
            "notes":          f"Set by {ctx.author} ({ctx.author.id})",
            "vanity_roles":   {},
        }

        await self.col.update_one({"_id": gid}, {"$set": doc}, upsert=True)

        guild = self.bot.get_guild(gid)
        name  = guild.name if guild else str(gid)
        dur   = "permanent" if days == -1 else f"{days}d"

        embed = discord.Embed(
            title="✅ Premium Updated",
            description=f"**{name}** (`{gid}`) → **{tier}** ({dur})",
            color=TIERS[tier]["color"],
            timestamp=utcnow(),
        )
        if expires:
            embed.add_field(name="Expires", value=_fmt_expiry(doc))
        embed.set_footer(text=f"Set by {ctx.author}")
        await ctx.send(embed=embed)
        logger.info("set_premium: %s → %s (%s) by %s", gid, tier, dur, ctx.author)

    # ── /revoke_premium (owner only) ───────────────────────────────────────────

    @commands.command(name="revoke_premium")
    @commands.is_owner()
    async def revoke_premium(self, ctx: commands.Context, guild_id: Optional[str] = None):
        """[Owner] Remove premium from a guild."""
        if self.col is None:
            return await ctx.send("❌ MongoDB not connected.")

        gid = int(guild_id) if guild_id else ctx.guild.id
        await self.col.update_one(
            {"_id": gid},
            {"$set": {"tier": "FREE", "expires_at": utcnow()}},
            upsert=True,
        )
        guild = self.bot.get_guild(gid)
        name  = guild.name if guild else str(gid)
        await ctx.send(f"✅ Revoked premium from **{name}** (`{gid}`)")
        logger.info("revoke_premium: %s by %s", gid, ctx.author)

    # ── /premium_price ─────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="premium_price",
        description="Show Nexora premium plans and pricing",
        aliases=["plans", "upgrade"],
    )
    async def premium_price(self, ctx: commands.Context):
        embed = discord.Embed(
            title="💎 Nexora Premium Plans",
            description="Unlock advanced features for your server — starting at just **$1/month**.",
            color=discord.Color.gold(),
            timestamp=utcnow(),
        )

        for plan in PRICING:
            tier_info = TIERS[plan["tier"]]
            features  = "\n".join(f"• {f}" for f in plan["features"])
            embed.add_field(
                name=f"{tier_info['emoji']} {plan['tier']}  —  {plan['monthly']}/mo  ·  {plan['yearly']}/yr",
                value=features,
                inline=False,
            )

        embed.add_field(
            name="🎁 Why so affordable?",
            value=(
                "✅ Cheapest feature-rich Discord bot\n"
                "✅ Cancel anytime — no lock-in\n"
                "✅ Instant activation\n"
                "✅ All future tier features included"
            ),
            inline=False,
        )
        embed.set_footer(text="Nexora Premium  ·  Contact the bot owner to subscribe")
        await ctx.send(embed=embed)

    # ── /vanity ────────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="vanity",
        description="View this server's vanity role configuration",
    )
    @commands.guild_only()
    async def vanity(self, ctx: commands.Context):
        if not await self.is_premium(ctx.guild.id):
            embed = discord.Embed(
                description=(
                    "❌ **This server doesn't have premium.**\n\n"
                    "Use `n!premium_price` to see plans."
                ),
                color=discord.Color.red(),
            )
            return await ctx.send(embed=embed, ephemeral=True)

        doc   = await self.get_doc(ctx.guild.id)
        roles = doc.get("vanity_roles", {})
        tier  = doc.get("tier", "FREE")
        slots = TIERS.get(tier, TIERS["FREE"])["vanity_slots"]

        embed = discord.Embed(
            title="🎭 Vanity Roles",
            color=TIERS.get(tier, TIERS["FREE"])["color"],
            timestamp=utcnow(),
        )
        embed.add_field(name="📦 Tier",       value=tier,                    inline=True)
        embed.add_field(name="🎰 Slots Used", value=f"{len(roles)} / {slots}", inline=True)

        if roles:
            lines = []
            for keyword, role_id in list(roles.items())[:slots]:
                role = ctx.guild.get_role(int(role_id))
                lines.append(f"`{keyword}` → {role.mention if role else f'`{role_id}` (deleted)'}")
            embed.add_field(name="🔗 Configured Roles", value="\n".join(lines), inline=False)
        else:
            embed.add_field(
                name="🔗 Configured Roles",
                value="None yet. Contact the bot owner to configure vanity roles.",
                inline=False,
            )

        embed.set_footer(text="Nexora Premium  ·  Vanity roles auto-assign based on status keywords")
        await ctx.send(embed=embed)

    # ── Error handlers ─────────────────────────────────────────────────────────

    @premium_status.error
    async def premium_error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("❌ This command can only be used in a server.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Premium(bot))
    logger.info("Loaded Premium")
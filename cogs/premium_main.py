"""
cogs/core/premium.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MongoDB-backed premium system — tiers loaded from config.

MongoDB collection: "premium"
Document schema per guild:
  {
    _id:            int  (guild_id)
    tier:           str  (FREE | BASIC | PRO | ENTERPRISE | CUSTOM | GRANDFATHERED)
    expires_at:     datetime | None   — None = permanent
    purchased_by:   int  (user_id)
    purchased_at:   datetime
    payment_method: str
    amount_paid:    float
    notes:          str
    vanity_roles:   {keyword: role_id_str, ...}
    vanity_settings:{match_mode, priority_mode, case_sensitive, log_*, ...}
  }

bot.is_premium_guild(guild_id) → bool   (async, patched in cog_load)
bot.get_premium_tier(guild_id) → str    (async, patched in cog_load)
bot.get_tier_config(tier)      → dict   (sync, patched in cog_load)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger(__name__)

UNSAFE_VANITY_WEBHOOK_FIELDS = (
    "log_webhook",
    "webhook",
    "webhook_url",
    "discord_webhook",
    "discord_webhook_url",
)

# ══════════════════════════════════════════════════════════════════
# TIER CONFIG  — matches your premium_config.json exactly
# ══════════════════════════════════════════════════════════════════

TIER_CONFIG = {
    "FREE": {
        "display_name": "🆓 Free",
        "emoji":        "🆓",
        "price":        0,
        "color":        discord.Color.from_rgb(153, 170, 181),
        "features": {
            "vanity_roles":         0,
            "message_history":      10,
            "custom_responses":     False,
            "priority_support":     False,
            "analytics":            False,
            "auto_moderation":      False,
            "scheduled_messages":   False,
        },
        "limits": {
            "api_calls_per_day":        100,
            "response_time_priority":   3,
        },
    },
    "BASIC": {
        "display_name": "💎 Basic",
        "emoji":        "💎",
        "price":        4.99,
        "color":        discord.Color.from_rgb(93, 173, 226),
        "features": {
            "vanity_roles":         5,
            "message_history":      25,
            "custom_responses":     True,
            "priority_support":     True,
            "analytics":            True,
            "auto_moderation":      False,
            "scheduled_messages":   False,
        },
        "limits": {
            "api_calls_per_day":        500,
            "response_time_priority":   2,
        },
    },
    "PRO": {
        "display_name": "🚀 Pro",
        "emoji":        "🚀",
        "price":        12.99,
        "color":        discord.Color.from_rgb(87, 242, 135),
        "features": {
            "vanity_roles":         20,
            "message_history":      50,
            "custom_responses":     True,
            "priority_support":     True,
            "analytics":            True,
            "auto_moderation":      True,
            "scheduled_messages":   True,
        },
        "limits": {
            "api_calls_per_day":        1500,
            "response_time_priority":   1,
        },
    },
    "ENTERPRISE": {
        "display_name": "🏢 Enterprise",
        "emoji":        "🏢",
        "price":        29.99,
        "color":        discord.Color.from_rgb(255, 215, 0),
        "features": {
            "vanity_roles":         -1,   # unlimited
            "message_history":      100,
            "custom_responses":     True,
            "priority_support":     True,
            "analytics":            True,
            "auto_moderation":      True,
            "scheduled_messages":   True,
        },
        "limits": {
            "api_calls_per_day":        -1,
            "response_time_priority":   0,
        },
    },
    "CUSTOM": {
        "display_name": "🛃 Custom",
        "emoji":        "🛃",
        "price":        None,   # negotiated
        "color":        discord.Color.from_rgb(255, 100, 200),
        "features": {
            "vanity_roles":         -1,
            "message_history":      100,
            "custom_responses":     True,
            "priority_support":     True,
            "analytics":            True,
            "auto_moderation":      True,
            "scheduled_messages":   True,
            "voice_support":        True,
            "image_generation":     True,
            "music_integration":    True,
            "web_dashboard":        True,
            "early_access":         True,
        },
        "limits": {
            "api_calls_per_day":        -1,
            "response_time_priority":   0,
        },
    },
    "GRANDFATHERED": {
        "display_name": "🏆 Grandfathered",
        "emoji":        "🏆",
        "price":        0,
        "color":        discord.Color.from_rgb(255, 140, 0),
        "features": {
            "vanity_roles":         -1,
            "message_history":      100,
            "custom_responses":     True,
            "priority_support":     True,
            "analytics":            True,
            "auto_moderation":      True,
            "scheduled_messages":   True,
        },
        "limits": {
            "api_calls_per_day":        -1,
            "response_time_priority":   0,
        },
    },
}

PAID_TIERS = {"BASIC", "PRO", "ENTERPRISE", "CUSTOM", "GRANDFATHERED"}

OWNER_ID = 1013851779886231685

# Yearly discount %
YEARLY_DISCOUNT = 20
BULK_DISCOUNTS  = {5: 15, 10: 20, 25: 30}

# ── Feature display names ──────────────────────────────────────────
FEATURE_LABELS = {
    "vanity_roles":       "Vanity Roles",
    "message_history":    "Message History",
    "custom_responses":   "Custom Responses",
    "priority_support":   "Priority Support",
    "analytics":          "Analytics",
    "auto_moderation":    "Auto Moderation",
    "scheduled_messages": "Scheduled Messages",
    "voice_support":      "Voice Support",
    "image_generation":   "Image Generation",
    "music_integration":  "Music Integration",
    "web_dashboard":      "Web Dashboard",
    "early_access":       "Early Access",
}


# ══════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════

def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensure datetime is timezone-aware (UTC)."""
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
        return "∞  Permanent"
    if exp < utcnow():
        return "❌  Expired"
    ts = int(exp.timestamp())
    return f"<t:{ts}:R>  ·  <t:{ts}:D>"


def _vanity_slots(tier: str) -> str:
    cfg = TIER_CONFIG.get(tier, TIER_CONFIG["FREE"])
    val = cfg["features"].get("vanity_roles", 0)
    return "Unlimited" if val == -1 else str(val)


def _feature_row(key: str, value) -> str:
    label = FEATURE_LABELS.get(key, key.replace("_", " ").title())
    if isinstance(value, bool):
        icon = "✅" if value else "❌"
        return f"{icon} {label}"
    if value == -1:
        return f"✅ {label}: Unlimited"
    return f"✅ {label}: {value}"


class PremiumActionsView(discord.ui.View):
    """Small, non-intrusive navigation for premium information cards."""

    def __init__(self, timeout=180):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="View Plans", style=discord.ButtonStyle.secondary, emoji="💎")
    async def view_plans(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Use `/premium_price` to compare plans and see what each tier adds.",
            ephemeral=True,
        )

    @discord.ui.button(label="What Stays Free?", style=discord.ButtonStyle.secondary, emoji="🆓")
    async def free_features(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            "Core commands remain free. Premium is for optional scale, automation, and customization.",
            ephemeral=True,
        )


# ══════════════════════════════════════════════════════════════════
# COG
# ══════════════════════════════════════════════════════════════════

class Premium(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.col = None

    async def cog_load(self):
        db = getattr(self.bot, "mongo_db", None)
        if db is not None:
            self.col = db["premium"]
            logger.info("Premium: MongoDB connected")
            await self._scrub_unsafe_webhook_fields()
        else:
            logger.warning("Premium: mongo_db unavailable")

        # ── Patch helpers onto bot so other cogs can import nothing ───────────
        cog = self

        async def _is_premium(guild_id: int) -> bool:
            return await cog.is_premium(guild_id)

        async def _get_tier(guild_id: int) -> str:
            return await cog.get_tier(guild_id)

        def _tier_config(tier: str) -> dict:
            return TIER_CONFIG.get(tier.upper(), TIER_CONFIG["FREE"])

        self.bot.is_premium_guild = _is_premium
        self.bot.get_premium_tier = _get_tier
        self.bot.get_tier_config  = _tier_config

    async def _scrub_unsafe_webhook_fields(self):
        if self.col is None:
            return

        unset_fields = {
            f"vanity_settings.{field}": ""
            for field in UNSAFE_VANITY_WEBHOOK_FIELDS
        }
        filter_query = {
            "$or": [
                {f"vanity_settings.{field}": {"$exists": True}}
                for field in UNSAFE_VANITY_WEBHOOK_FIELDS
            ]
        }

        try:
            result = await self.col.update_many(filter_query, {"$unset": unset_fields})
            if result.modified_count:
                logger.warning(
                    "Premium: removed webhook URLs from %d MongoDB document(s)",
                    result.modified_count,
                )
        except Exception as e:
            logger.error("Premium: failed to scrub MongoDB webhook fields: %s", e)

    # ── DB helpers ─────────────────────────────────────────────────────────────

    async def get_doc(self, guild_id: int) -> dict:
        if self.col is None:
            return {}
        doc = await self.col.find_one({"_id": guild_id})
        return doc or {}

    async def is_premium(self, guild_id: int) -> bool:
        doc = await self.get_doc(guild_id)
        if not doc:
            return False
        tier = doc.get("tier", "FREE").upper()
        if tier == "GRANDFATHERED":
            return True
        if tier not in PAID_TIERS:
            return False
        return not _is_expired(doc)

    async def get_tier(self, guild_id: int) -> str:
        doc = await self.get_doc(guild_id)
        if not doc:
            return "FREE"
        tier = doc.get("tier", "FREE").upper()
        if tier == "GRANDFATHERED":
            return "GRANDFATHERED"
        if _is_expired(doc):
            return "FREE"
        return tier

    # ══════════════════════════════════════════════════════════════
    # COMMANDS
    # ══════════════════════════════════════════════════════════════

    # ── n!premium ─────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="premium",
        description="Check this server's premium status",
    )
    @commands.guild_only()
    async def premium_status(self, ctx: commands.Context):
        await ctx.defer()
        doc  = await self.get_doc(ctx.guild.id)
        tier = (doc.get("tier", "FREE") or "FREE").upper()

        if tier not in ("GRANDFATHERED",) and _is_expired(doc):
            tier = "FREE"

        cfg     = TIER_CONFIG.get(tier, TIER_CONFIG["FREE"])
        is_prem = tier in PAID_TIERS and not _is_expired(doc)

        embed = discord.Embed(
            title=f"{cfg['emoji']}  {ctx.guild.name}",
            color=cfg["color"],
            timestamp=utcnow(),
        )
        if ctx.guild.icon:
            embed.set_thumbnail(url=ctx.guild.icon.url)

        # ── Main status row ────────────────────────────────────────────────────
        embed.add_field(name="📦 Tier",    value=cfg["display_name"], inline=True)
        embed.add_field(name="✅ Active", value="Yes" if is_prem else "No · Free tier", inline=True)
        embed.add_field(name="🎭 Vanity",  value=_vanity_slots(tier) + " slots", inline=True)

        # ── Subscription details ───────────────────────────────────────────────
        if doc:
            embed.add_field(name="🕐 Expires", value=_fmt_expiry(doc), inline=True)

            purchased_by = doc.get("purchased_by")
            if purchased_by:
                user = self.bot.get_user(int(purchased_by))
                embed.add_field(
                    name="🛒 Purchased By",
                    value=user.mention if user else f"`{purchased_by}`",
                    inline=True,
                )

            purchased_at = _parse_dt(doc.get("purchased_at"))
            if purchased_at:
                ts = int(purchased_at.timestamp())
                embed.add_field(name="📅 Since", value=f"<t:{ts}:D>", inline=True)

            if doc.get("notes"):
                embed.add_field(name="📝 Notes", value=doc["notes"], inline=False)

        # ── Features for current tier ──────────────────────────────────────────
        feats = cfg["features"]
        feat_lines = [_feature_row(k, v) for k, v in feats.items()]
        # split into two columns
        half = (len(feat_lines) + 1) // 2
        embed.add_field(name="🔓 Features", value="\n".join(feat_lines[:half]) or "—", inline=True)
        if feat_lines[half:]:
            embed.add_field(name="\u200b",   value="\n".join(feat_lines[half:]),        inline=True)
            embed.add_field(name="\u200b",   value="\u200b",                            inline=True)

        if not is_prem:
            embed.add_field(
                name="🚀 Upgrade",
                value=(
                    "Premium is optional and core commands stay available on the free tier.\n"
                    f"Use `/premium_price` to compare plans, or contact <@{OWNER_ID}> when ready."
                ),
                inline=False,
            )

        embed.set_footer(text="Nexora Premium  ·  Contact owner to subscribe")
        await ctx.send(embed=embed, view=PremiumActionsView())

    # ── n!set_premium (owner only) ────────────────────────────────────────────

    @commands.command(name="set_premium")
    @commands.is_owner()
    async def set_premium(
        self,
        ctx: commands.Context,
        guild_id: Optional[str] = None,
        tier: str = "PRO",
        days: int = 30,
    ):
        """
        [Owner] Grant/update premium for a guild.
        Usage: n!set_premium [guild_id] [tier] [days]
          days=-1 → permanent
          tier: FREE | BASIC | PRO | ENTERPRISE | CUSTOM | GRANDFATHERED
        """
        if self.col is None:
            return await ctx.send("❌ MongoDB not connected.")

        gid  = int(guild_id) if guild_id else ctx.guild.id
        tier = tier.upper()

        if tier not in TIER_CONFIG:
            valid = " | ".join(TIER_CONFIG)
            return await ctx.send(f"❌ Unknown tier. Valid: `{valid}`")

        expires = None if days == -1 else utcnow() + timedelta(days=days)

        await self.col.update_one(
            {"_id": gid},
            {"$set": {
                "tier":           tier,
                "expires_at":     expires,
                "purchased_by":   ctx.author.id,
                "purchased_at":   utcnow(),
                "payment_method": "Manual",
                "amount_paid":    0,
                "notes":          f"Set by {ctx.author} ({ctx.author.id})",
            }},
            upsert=True,
        )

        guild   = self.bot.get_guild(gid)
        name    = guild.name if guild else str(gid)
        dur_str = "permanent" if days == -1 else f"{days}d"
        cfg     = TIER_CONFIG[tier]

        embed = discord.Embed(
            title="✅ Premium Updated",
            description=f"**{name}** (`{gid}`)\n{cfg['display_name']}  ·  {dur_str}",
            color=cfg["color"],
            timestamp=utcnow(),
        )
        if expires:
            ts = int(expires.timestamp())
            embed.add_field(name="Expires", value=f"<t:{ts}:R>  ·  <t:{ts}:D>")
        embed.set_footer(text=f"Set by {ctx.author}")
        await ctx.send(embed=embed)
        logger.info("set_premium: guild=%s tier=%s days=%s by=%s", gid, tier, days, ctx.author)

    # ── n!revoke_premium (owner only) ─────────────────────────────────────────

    @commands.command(name="revoke_premium")
    @commands.is_owner()
    async def revoke_premium(self, ctx: commands.Context, guild_id: Optional[str] = None):
        """[Owner] Remove premium from a guild."""
        if self.col is None:
            return await ctx.send("❌ MongoDB not connected.")

        gid = int(guild_id) if guild_id else ctx.guild.id
        await self.col.update_one(
            {"_id": gid},
            {"$set": {"tier": "FREE", "expires_at": utcnow(), "notes": f"Revoked by {ctx.author}"}},
            upsert=True,
        )
        guild = self.bot.get_guild(gid)
        name  = guild.name if guild else str(gid)
        await ctx.send(f"✅ Revoked premium from **{name}** (`{gid}`)")

    # ── n!premium_price ────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="premium_price",
        description="View Nexora premium plans and pricing",
        aliases=["plans", "upgrade"],
    )
    async def premium_price(self, ctx: commands.Context):
        embed = discord.Embed(
            title="💎 Nexora Premium Plans",
            description=(
                f"To subscribe, contact <@{OWNER_ID}> with your server ID and desired tier.\n"
                f"Payment via **UPI**.\n\u200b"
            ),
            color=discord.Color.gold(),
            timestamp=utcnow(),
        )

        # Paid tiers only
        for key in ("BASIC", "PRO", "ENTERPRISE", "CUSTOM"):
            cfg      = TIER_CONFIG[key]
            price    = cfg["price"]
            feats    = cfg["features"]

            if price is None:
                price_str = "Negotiated"
                yearly    = "Negotiated"
            else:
                yearly_price = round(price * 12 * (1 - YEARLY_DISCOUNT / 100), 2)
                price_str    = f"${price}/mo"
                yearly       = f"${yearly_price}/yr  *(save {YEARLY_DISCOUNT}%)*"

            slots     = feats.get("vanity_roles", 0)
            slots_str = "Unlimited" if slots == -1 else str(slots)
            history   = feats.get("message_history", 0)
            calls     = cfg["limits"].get("api_calls_per_day", 0)
            calls_str = "Unlimited" if calls == -1 else str(calls)

            # Build feature list
            feat_lines = []
            feat_lines.append(f"🎭 **{slots_str}** vanity role{'s' if slots != 1 else ''}")
            feat_lines.append(f"📜 **{history}** message history")
            feat_lines.append(f"⚡ **{calls_str}** API calls/day")
            for fkey in ("custom_responses", "priority_support", "analytics",
                         "auto_moderation", "scheduled_messages"):
                if feats.get(fkey):
                    feat_lines.append(f"✅ {FEATURE_LABELS[fkey]}")
            if key == "CUSTOM":
                for fkey in ("voice_support", "image_generation", "music_integration",
                             "web_dashboard", "early_access"):
                    if feats.get(fkey):
                        feat_lines.append(f"✅ {FEATURE_LABELS[fkey]}")

            value = (
                f"**{price_str}**  ·  {yearly}\n"
                + "\n".join(feat_lines)
            )
            embed.add_field(
                name=f"{cfg['display_name']}",
                value=value,
                inline=True,
            )

        # Discounts
        bulk_lines = "\n".join(
            f"• **{k} servers** → {v}% off" for k, v in BULK_DISCOUNTS.items()
        )
        embed.add_field(
            name="🎁 Discounts",
            value=(
                f"📅 **Yearly** → {YEARLY_DISCOUNT}% off\n"
                f"**Bulk (per server):**\n{bulk_lines}"
            ),
            inline=False,
        )

        embed.set_footer(text=f"Contact @{OWNER_ID} via Discord DM  ·  Payment: UPI")
        await ctx.send(embed=embed, view=PremiumActionsView())

    # ── n!vanity ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="vanity",
        description="View this server's vanity role configuration",
    )
    @commands.guild_only()
    async def vanity(self, ctx: commands.Context):
        if not await self.is_premium(ctx.guild.id):
            return await ctx.send(
                embed=discord.Embed(
                    description=(
                        "❌ **Premium required** for vanity roles.\n\n"
                        f"Contact <@{OWNER_ID}> or use `n!premium_price` to upgrade."
                    ),
                    color=discord.Color.red(),
                ),
                ephemeral=True,
            )

        doc      = await self.get_doc(ctx.guild.id)
        tier     = (doc.get("tier") or "FREE").upper()
        cfg      = TIER_CONFIG.get(tier, TIER_CONFIG["FREE"])
        roles    = doc.get("vanity_roles", {})
        settings = doc.get("vanity_settings", {})
        slots    = cfg["features"].get("vanity_roles", 0)
        slots_str = "Unlimited" if slots == -1 else str(slots)

        embed = discord.Embed(
            title="🎭 Vanity Roles",
            color=cfg["color"],
            timestamp=utcnow(),
        )

        embed.add_field(name="📦 Tier",        value=cfg["display_name"],               inline=True)
        embed.add_field(name="🎰 Slots Used",  value=f"{len(roles)} / {slots_str}",     inline=True)
        embed.add_field(name="🔍 Match Mode",  value=settings.get("match_mode", "substring"), inline=True)

        embed.add_field(
            name="⚙️ Settings",
            value=(
                f"Priority: `{settings.get('priority_mode', 'longest_first')}`\n"
                f"Case Sensitive: `{settings.get('case_sensitive', False)}`\n"
                f"Logging: `{'enabled' if settings.get('log_enabled') else 'disabled'}`"
            ),
            inline=True,
        )

        if roles:
            lines = []
            for keyword, role_id in roles.items():
                role = ctx.guild.get_role(int(role_id))
                lines.append(
                    f"`{keyword}` → {role.mention if role else f'~~`{role_id}`~~ (deleted)'}"
                )
            embed.add_field(
                name=f"🔗 Keyword → Role ({len(roles)})",
                value="\n".join(lines) or "—",
                inline=False,
            )
        else:
            embed.add_field(
                name="🔗 Keyword → Role",
                value="No vanity roles configured yet.",
                inline=False,
            )

        embed.set_footer(text="Nexora Premium  ·  Roles auto-assign when status contains the keyword")
        await ctx.send(embed=embed)

    # ── n!premium_list (owner only) ────────────────────────────────────────────

    @commands.command(name="premium_list")
    @commands.is_owner()
    async def premium_list(self, ctx: commands.Context):
        """[Owner] List all premium subscriptions."""
        if self.col is None:
            return await ctx.send("❌ MongoDB not connected.")

        docs  = await self.col.find({}).to_list(length=100)
        if not docs:
            return await ctx.send("No premium subscriptions found.")

        embed = discord.Embed(
            title=f"👑 Premium Subscriptions ({len(docs)})",
            color=discord.Color.gold(),
            timestamp=utcnow(),
        )

        for doc in docs:
            gid   = doc["_id"]
            guild = self.bot.get_guild(gid)
            name  = guild.name if guild else str(gid)
            tier  = doc.get("tier", "FREE")
            exp   = _fmt_expiry(doc)
            embed.add_field(
                name=f"{TIER_CONFIG.get(tier, {}).get('emoji', '•')} {name}",
                value=f"`{gid}`  ·  **{tier}**  ·  {exp}",
                inline=False,
            )

        await ctx.send(embed=embed)

    # ── Error handlers ─────────────────────────────────────────────────────────

    @premium_status.error
    async def _premium_error(self, ctx, error):
        if isinstance(error, commands.NoPrivateMessage):
            await ctx.send("❌ Server only.", ephemeral=True)
        else:
            raise error


async def setup(bot: commands.Bot):
    await bot.add_cog(Premium(bot))
    logger.info("Loaded Premium")

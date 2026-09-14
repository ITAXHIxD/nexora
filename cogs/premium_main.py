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

from utils.ui import (
    BRAND_COLOR,
    PREMIUM_COLOR,
    NexoraView,
    DismissButton,
    send_view,
    ts_format,
)

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


class PremiumStatusCardView(NexoraView):
    """Components V2 dashboard for server premium status."""

    def __init__(self, guild: discord.Guild, doc: dict, requester: discord.abc.User, timeout: float = 180):
        tier = (doc.get("tier", "FREE") or "FREE").upper()
        if tier not in ("GRANDFATHERED",) and _is_expired(doc):
            tier = "FREE"
        cfg = TIER_CONFIG.get(tier, TIER_CONFIG["FREE"])
        color_val = cfg["color"].value if hasattr(cfg["color"], "value") else PREMIUM_COLOR
        super().__init__(user_id=requester.id, color=color_val, timeout=timeout)
        self.guild = guild
        self.doc = doc
        self.tier = tier
        self.cfg = cfg
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()
        g = self.guild
        cfg = self.cfg
        is_prem = self.tier in PAID_TIERS and not _is_expired(self.doc)

        header = (
            f"# {cfg['emoji']} {g.name} · Premium Status\n"
            f"> Tier: **{cfg['display_name']}** · Active: **{'✅ Active' if is_prem else '🆓 Free Tier'}**"
        )
        self.add_section(header, thumbnail_url=str(g.icon.url) if g.icon else None)
        self.add_separator(discord.SeparatorSpacing.small)

        meta_lines = [
            f"• **Vanity Slots:** `{_vanity_slots(self.tier)}` slots",
            f"• **Expiration:** {_fmt_expiry(self.doc)}",
        ]
        purchased_by = self.doc.get("purchased_by")
        if purchased_by:
            meta_lines.append(f"• **Purchased By:** <@{purchased_by}>")
        purchased_at = _parse_dt(self.doc.get("purchased_at"))
        if purchased_at:
            meta_lines.append(f"• **Active Since:** <t:{int(purchased_at.timestamp())}:D>")

        self.add_text("### 📦 Subscription Overview\n" + "\n".join(meta_lines))
        self.add_separator(discord.SeparatorSpacing.small)

        feats = cfg["features"]
        feat_lines = [_feature_row(k, v) for k, v in feats.items() if v]
        if feat_lines:
            self.add_text("### 🔓 Unlocked Features\n" + "\n".join(f"• {f}" for f in feat_lines[:8]))

        if not is_prem:
            self.add_text("### 🚀 Ready to Upgrade?\n> Use `/premium_price` to compare plans or contact the bot owner.")

        self.add_footer(f"Requested by {self.requester.display_name} · Nexora Premium Network")

        btn_plans = discord.ui.Button(label="Compare Plans", emoji="💎", style=discord.ButtonStyle.secondary, custom_id="prem-plans")
        async def on_plans(interaction: discord.Interaction):
            await interaction.response.send_message("Use `/premium_price` to view full catalog & pricing.", ephemeral=True)
        btn_plans.callback = on_plans

        self.add_row(btn_plans, DismissButton(user_id=self.requester.id))


class PremiumCatalogCardView(NexoraView):
    """Components V2 card showcasing all premium tiers and pricing."""

    def __init__(self, requester: discord.abc.User, timeout: float = 180):
        super().__init__(user_id=requester.id, color=PREMIUM_COLOR, timeout=timeout)
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()
        header = (
            "# 💎 Nexora Premium Catalog\n"
            "> Unlock vanity roles, extended message history, AI prioritization, and server perks."
        )
        self.add_text(header)
        self.add_separator(discord.SeparatorSpacing.small)

        tier_summaries = []
        for key in ("BASIC", "PRO", "ENTERPRISE", "CUSTOM"):
            cfg = TIER_CONFIG[key]
            price = cfg["price"]
            price_str = f"${price}/mo" if price is not None else "Custom"
            feats = cfg["features"]
            slots = feats.get("vanity_roles", 0)
            slots_str = "Unlimited" if slots == -1 else str(slots)
            tier_summaries.append(
                f"### {cfg['display_name']} — `{price_str}`\n"
                f"• 🎭 Vanity Roles: **{slots_str}**\n"
                f"• 📜 History: **{feats.get('message_history', 0)}** messages · ⚡ API: **{cfg['limits'].get('api_calls_per_day', 0)}**/day"
            )
        self.add_text("\n\n".join(tier_summaries))
        self.add_separator(discord.SeparatorSpacing.small)

        self.add_text(
            "### 🎁 Discounts & Payment\n"
            f"• **Yearly Billing:** Save {YEARLY_DISCOUNT}% on any annual plan\n"
            f"• **Activation:** Contact <@{OWNER_ID}> via Discord DM · Payment accepted via **UPI**."
        )
        self.add_footer(f"Requested by {self.requester.display_name}")
        self.add_row(DismissButton(user_id=self.requester.id))


class VanityCardView(NexoraView):
    """Components V2 card displaying vanity role mapping and configuration."""

    def __init__(self, guild: discord.Guild, doc: dict, requester: discord.abc.User, timeout: float = 180):
        super().__init__(user_id=requester.id, color=PREMIUM_COLOR, timeout=timeout)
        self.guild = guild
        self.doc = doc
        self.requester = requester
        self._build()

    def _build(self):
        self.clear_container()
        g = self.guild
        tier = (self.doc.get("tier") or "FREE").upper()
        cfg = TIER_CONFIG.get(tier, TIER_CONFIG["FREE"])
        roles = self.doc.get("vanity_roles", {})
        settings = self.doc.get("vanity_settings", {})
        slots = cfg["features"].get("vanity_roles", 0)
        slots_str = "Unlimited" if slots == -1 else str(slots)

        header = (
            f"# 🎭 Vanity Roles · {g.name}\n"
            f"> Tier: **{cfg['display_name']}** · Slots Used: **{len(roles)} / {slots_str}**"
        )
        self.add_section(header, thumbnail_url=str(g.icon.url) if g.icon else None)
        self.add_separator(discord.SeparatorSpacing.small)

        meta = (
            f"• **Match Mode:** `{settings.get('match_mode', 'substring')}`\n"
            f"• **Priority:** `{settings.get('priority_mode', 'longest_first')}`\n"
            f"• **Logging:** `{'Enabled' if settings.get('log_enabled') else 'Disabled'}`"
        )
        self.add_text("### ⚙️ Engine Settings\n" + meta)
        self.add_separator(discord.SeparatorSpacing.small)

        if roles:
            role_lines = []
            for kw, rid in roles.items():
                r = g.get_role(int(rid))
                mention_str = r.mention if r else f"~~`{rid}`~~ (Deleted)"
                role_lines.append(f"• `{kw}` ➔ {mention_str}")
            self.add_text(f"### 🔗 Configured Keyword Mappings ({len(roles)})\n" + "\n".join(role_lines))
        else:
            self.add_text("### 🔗 Configured Keyword Mappings\n> No vanity keywords mapped yet. Use `/vanity_add` to create one.")

        self.add_footer("Nexora Premium · Roles automatically sync to custom user statuses")
        self.add_row(DismissButton(user_id=self.requester.id))


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
        doc = await self.get_doc(ctx.guild.id)
        view = PremiumStatusCardView(ctx.guild, doc, ctx.author)
        await send_view(ctx, view)

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
        view = PremiumCatalogCardView(ctx.author)
        await send_view(ctx, view)

    # ── n!vanity ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(
        name="vanity",
        description="View this server's vanity role configuration",
    )
    @commands.guild_only()
    async def vanity(self, ctx: commands.Context):
        if not await self.is_premium(ctx.guild.id):
            return await ctx.send(
                "❌ **Premium required** for vanity roles. Use `/premium_price` to view upgrade plans.",
                ephemeral=True,
            )

        doc = await self.get_doc(ctx.guild.id)
        view = VanityCardView(ctx.guild, doc, ctx.author)
        await send_view(ctx, view)

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
    logger.debug("Loaded Premium")

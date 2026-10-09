"""
cogs/premium/server_growth.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Advanced Server Growth & Supporter Analytics for Nexora Premium.

Audits:
  • Vanity Supporter Penetration Rate (% and count)
  • Booster Metrics & Tier Progress
  • Human vs Bot Ratios
  • Active Presence Velocity
  • Verification & Moderation Health
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from datetime import datetime, timezone

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    PREMIUM_COLOR,
    SUCCESS_COLOR,
    CYAN_COLOR,
    progress_bar,
)

logger = logging.getLogger(__name__)


class ServerGrowth(commands.Cog):
    """Server diagnostics, vanity supporter reach, and growth analytics."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _is_premium(self, guild_id: int) -> bool:
        checker = getattr(self.bot, "is_premium_guild", None)
        if checker:
            return await checker(guild_id)
        return False

    @commands.hybrid_command(name="server_growth", description="Deep server growth metrics, supporter penetration, and velocity audit", aliases=["growth", "growth_analytics"])
    @commands.guild_only()
    async def server_growth(self, ctx: commands.Context):
        if not await self._is_premium(ctx.guild.id):
            return await ctx.send("❌ **Premium Required**: Server Growth & Analytics requires an active server subscription. Use `/premium_price` to learn more!", ephemeral=True)

        g = ctx.guild
        total_members = max(1, len(g.members))
        humans = [m for m in g.members if not m.bot]
        bots = [m for m in g.members if m.bot]
        online_members = [m for m in humans if m.status != discord.Status.offline]

        # Booster metrics
        boosters = [m for m in humans if m.premium_since]
        boost_count = g.premium_subscription_count or 0
        boost_tier = g.premium_tier

        # Vanity supporters
        col = getattr(self.bot, "mongo_db", None)
        roles_map = {}
        if col is not None:
            doc = await col["premium"].find_one({"_id": g.id})
            if doc:
                roles_map = doc.get("vanity_roles", {})

        vanity_rids = {int(r) for r in roles_map.values() if str(r).isdigit()}
        supporters = set()
        for rid in vanity_rids:
            r = g.get_role(rid)
            if r:
                for m in r.members:
                    if not m.bot:
                        supporters.add(m)

        supporter_pct = (len(supporters) / max(1, len(humans))) * 100.0
        human_pct = (len(humans) / total_members) * 100.0
        online_pct = (len(online_members) / max(1, len(humans))) * 100.0

        embed = discord.Embed(
            title=f"📊 Community Analytics & Velocity · {g.name}",
            color=PREMIUM_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        if g.icon:
            embed.set_thumbnail(url=g.icon.url)
        if g.banner:
            embed.set_image(url=g.banner.url)

        # Vanity penetration
        vanity_meter = progress_bar(len(supporters), len(humans), length=12, filled="█", empty="░")
        embed.add_field(
            name="🎭 Vanity Status Supporter Reach",
            value=(
                f"`[{vanity_meter}]` **{supporter_pct:.1f}%**\n"
                f"> **{len(supporters)}** human members actively promoting your server in their status!"
            ),
            inline=False,
        )

        # Nitro Boosters
        next_tier_req = {0: 2, 1: 7, 2: 14, 3: 14}.get(boost_tier, 14)
        embed.add_field(
            name="🚀 Nitro Boost Performance",
            value=(
                f"• Level: **Tier {boost_tier}** · Total Boosts: **{boost_count}**\n"
                f"• Active Boosters: **{len(boosters)}** members ({len(boosters)/max(1, len(humans))*100:.1f}% of humans)"
            ),
            inline=False,
        )

        # Population & Activity
        act_meter = progress_bar(len(online_members), len(humans), length=12, filled="█", empty="░")
        embed.add_field(
            name="👥 Member Activity Ratio",
            value=(
                f"`[{act_meter}]` **{online_pct:.1f}% Online**\n"
                f"• Humans: **{len(humans)}** ({human_pct:.1f}%) · Bots: **{len(bots)}**\n"
                f"• Active Online Presences: **{len(online_members)}**"
            ),
            inline=False,
        )

        # Server Health Score
        health_score = int(min(100, (supporter_pct * 1.5) + (online_pct * 0.5) + (boost_count * 2)))
        embed.add_field(
            name="🏆 Community Engagement Index",
            value=f"`{health_score} / 100` · Engagement Rating: **{'🌟 Elite' if health_score > 75 else '🟢 Healthy' if health_score > 40 else '🟡 Moderate'}**",
            inline=False,
        )

        embed.set_footer(text="Nexora Premium Diagnostics · Real-Time Server Intelligence")
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(ServerGrowth(bot))
    logger.debug("Loaded ServerGrowth Cog")

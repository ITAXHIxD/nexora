import discord
import json
import os
from discord.ext import commands
from datetime import datetime, timedelta

class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.file = "data/premium.json"

    def _get_data(self):
        """Always fresh data - fixes stale cache issue"""
        if os.path.exists(self.file):
            with open(self.file, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"subscriptions": {}, "vanity": {"roles": {}, "settings": {}}, "grandfathered": []}

    def _save_data(self, data):
        """Save with UTF-8 encoding"""
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def is_premium(self, guild_id: int) -> bool:
        data = self._get_data()
        gid = str(guild_id)
        if int(gid) in data.get("grandfathered", []): 
            return True
        sub = data["subscriptions"].get(gid)
        if not sub: 
            return False
        expires = sub.get("expires_at")
        if expires and expires != "null":
            try: 
                if datetime.fromisoformat(expires) < datetime.now(): 
                    return False
            except: 
                pass
        return True

    def get_tier(self, guild_id: int) -> str:
        data = self._get_data()
        gid = str(guild_id)
        if int(gid) in data.get("grandfathered", []): 
            return "GRANDFATHERED"
        return data["subscriptions"].get(gid, {}).get("tier", "FREE")

    def get_vanity_roles(self, guild_id: int) -> dict:
        data = self._get_data()
        return data["vanity"]["roles"].get(str(guild_id), {})

    @commands.command()
    @commands.is_owner()
    async def set_premium(self, ctx, guild_id: str = None, tier: str = "ULTRA", days: int = 30):
        """!set_premium [guild_id] [tier] [days]"""
        if guild_id is None: 
            guild_id = str(ctx.guild.id)
        
        data = self._get_data()
        expires = None if days == -1 else (datetime.now() + timedelta(days=days)).isoformat()
        
        data["subscriptions"][guild_id] = {
            "tier": tier.upper(),
            "expires_at": expires,
            "purchased_by": str(ctx.author.id),
            "purchased_at": datetime.now().isoformat(),
            "payment_method": "Manual",
            "amount_paid": 0,
            "notes": f"Set by {ctx.author}"
        }
        
        self._save_data(data)
        await ctx.send(f"✅ Guild `{guild_id}` → **{tier}** ({'permanent' if days == -1 else f'{days}d'})")

    @commands.command()
    async def premium(self, ctx):
        """Check server premium status with full details"""
        data = self._get_data()
        gid = str(ctx.guild.id)

        # Get subscription info
        sub = data["subscriptions"].get(gid, {})
        tier = sub.get("tier", "FREE")
        purchased_by = sub.get("purchased_by")
        purchased_at = sub.get("purchased_at")
        expires_at = sub.get("expires_at")

        # Calculate time left
        time_left = "∞ Permanent"
        if expires_at and expires_at != "null":
            try:
                expires = datetime.fromisoformat(expires_at)
                days_left = (expires - datetime.now()).days
                if days_left > 0:
                    time_left = f"{days_left} days"
                else:
                    time_left = "❌ **EXPIRED**"
            except:
                time_left = "Unknown"

        # Status
        is_grandfathered = int(gid) in data.get("grandfathered", [])
        status_emoji = "👑" if is_grandfathered else "⭐"

        # Embed
        embed = discord.Embed(title=f"{ctx.guild.name}", color=discord.Color.blue())
        embed.add_field(name="Tier", value=f"**{tier}** {status_emoji}", inline=True)

        if purchased_by:
            purchaser = self.bot.get_user(int(purchased_by))
            embed.add_field(
                name="Purchased By", 
                value=purchaser.mention if purchaser else purchased_by, 
                inline=True
            )

        if purchased_at:
            try:
                purchase_date = datetime.fromisoformat(purchased_at).strftime("%Y-%m-%d %H:%M")
                embed.add_field(name="Purchase Date", value=purchase_date, inline=True)
            except:
                pass
            
        embed.add_field(name="Expires", value=time_left, inline=True)

        # Show role count
        roles = data["vanity"]["roles"].get(gid, {})
        embed.add_field(name="Vanity Roles", value=f"{len(roles)} configured", inline=True)

        embed.set_thumbnail(url=ctx.guild.icon.url if ctx.guild.icon else None)
        embed.timestamp = datetime.now()

        await ctx.send(embed=embed)

    @commands.command()
    @commands.is_owner()
    async def premium_price(self, ctx):
        """Display affordable premium pricing"""
        embed = discord.Embed(title="💎 Premium Pricing", color=discord.Color.gold())

        # SUPER CHEAP pricing for 1 command
        pricing_data = [
            {"tier": "BASIC", "monthly": "$1", "yearly": "$10", "features": "• 1 Vanity Roles\n• Status Matching"},
            {"tier": "PRO", "monthly": "$3", "yearly": "$30", "features": "• 3 Vanity Roles\n• Logging\n• Priority"},
            {"tier": "ULTRA", "monthly": "$5", "yearly": "$50", "features": "• 5 Roles\n• Logging\n• Priority"},
        ]

        table = "```\n"
        table += f"{'Tier':<8} {'Monthly':<8} {'Yearly':<8} Features\n"
        table += "─" * 45 + "\n"

        for plan in pricing_data:
            tier = plan["tier"][:7].ljust(7)
            monthly = plan["monthly"][:7].ljust(7)
            yearly = plan["yearly"][:7].ljust(7)
            table += f"{tier} {monthly} {yearly} {plan['features']}\n"

        table += "```"
        embed.description = table

        benefits = [
            "✅ **$1/month** - Cheapest premium bot!",
            "✅ **Cancel anytime** - No risk",
            "✅ **Instant activation**",
            "✅ **Works immediately**"
        ]

        embed.add_field(name="🎁 Why so cheap?", value="\n".join(benefits), inline=False)
        embed.add_field(name="🚀 Start Now", value="`!set_premium [server] BASIC 30`\n`!set_premium [server] ULTRA -1`", inline=False)

        embed.timestamp = datetime.now()
        await ctx.send(embed=embed)


    @commands.command()
    async def vanity(self, ctx):
        """View vanity roles + settings"""
        if not self.is_premium(ctx.guild.id):
            return await ctx.send("❌ Premium only!")
        
        roles = self.get_vanity_roles(ctx.guild.id)
        data = self._get_data()
        settings = data["vanity"]["settings"].get(str(ctx.guild.id), {})
        
        embed = discord.Embed(title="🎭 Vanity Status", color=discord.Color.purple())
        embed.add_field(name="Roles", value=f"{len(roles)} configured", inline=True)
        embed.add_field(name="Match Mode", value=settings.get("match_mode", "substring"), inline=True)
        embed.add_field(name="Priority", value=settings.get("priority_mode", "longest_first"), inline=True)
        
        if roles:
            role_list = "\n".join([f"`{k}` → {ctx.guild.get_role(int(v)) or v}" for k, v in list(roles.items())[:3]])
            embed.add_field(name="Roles", value=role_list or "None", inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Premium(bot))

import discord
import json
import os
from discord.ext import commands, tasks
from datetime import datetime
import asyncio

class Vanity(commands.Cog):
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
        """Save with proper encoding"""
        os.makedirs(os.path.dirname(self.file), exist_ok=True)
        with open(self.file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def _update_data(self, update_func):
        """Helper to update data atomically"""
        data = self._get_data()
        update_func(data)
        self._save_data(data)

    def is_premium(self, guild_id):
        """Self-contained premium check with fresh data"""
        data = self._get_data()
        gid = str(guild_id)
        if int(gid) in data.get("grandfathered", []): return True
        sub = data["subscriptions"].get(gid)
        if not sub: return False
        expires = sub.get("expires_at")
        if expires and expires != "null":
            try:
                if datetime.fromisoformat(expires) < datetime.now():
                    return False
            except: pass
        return True

    def get_vanity_roles(self, guild_id):
        data = self._get_data()
        return data["vanity"]["roles"].get(str(guild_id), {})

    def save_vanity_roles(self, guild_id, roles):
        def update(data):
            if "vanity" not in data: data["vanity"] = {"roles": {}, "settings": {}}
            data["vanity"]["roles"][str(guild_id)] = roles
        self._update_data(update)

    def get_vanity_settings(self, guild_id):
        data = self._get_data()
        return data["vanity"]["settings"].get(str(guild_id), {})

    @tasks.loop(minutes=5)
    async def check_task(self):
        for guild in self.bot.guilds:
            if not self.is_premium(guild.id): continue
            
            roles = self.get_vanity_roles(guild.id)
            if not roles: continue

            vanity_role_ids = {int(rid) for rid in roles.values()}
            
            # Process only online/active members to save API calls
            for member in [m for m in guild.members if not m.bot and m.status != discord.Status.offline]:
                status = " ".join([a.name for a in member.activities 
                                 if isinstance(a, discord.CustomActivity)])
                
                current_roles = {r.id for r in member.roles}
                
                # Find matching roles
                should_have = set()
                for trigger, role_id in roles.items():
                    if trigger.lower() in status.lower():
                        should_have.add(int(role_id))
                
                # Add missing roles
                for role_id in should_have - current_roles:
                    role = guild.get_role(role_id)
                    if role and role not in member.roles:
                        try:
                            await member.add_roles(role, reason="Vanity status match")
                            await asyncio.sleep(0.5)
                        except: pass
                
                # Remove extra vanity roles
                for role_id in current_roles & vanity_role_ids - should_have:
                    role = guild.get_role(role_id)
                    if role in member.roles:
                        try:
                            await member.remove_roles(role, reason="Vanity status changed")
                            await asyncio.sleep(0.5)
                        except: pass

    @check_task.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def vanity_add(self, ctx, trigger: str, *, role: discord.Role):
        """!vanity_add hello @Role"""
        data = self._get_data()
        gid = str(ctx.guild.id)
        sub = data["subscriptions"].get(gid, {})
        tier = sub.get("tier", "FREE")

        # ✅ TIER LIMITS
        role_limits = {
            "BASIC": 1,
            "PRO": 3, 
            "ULTRA": 5,
            "CUSTOM": 999,  # Unlimited
            "FREE": 0
        }

        max_roles = role_limits.get(tier.upper(), 0)
        current_roles = len(self.get_vanity_roles(ctx.guild.id))

        if current_roles >= max_roles:
            return await ctx.send(f"❌ **{tier}** tier: Max {max_roles} roles allowed!\n💎 Upgrade: `!premium_price`")

        if not self.is_premium(ctx.guild.id):
            return await ctx.send("❌ Premium only!")

        # Role validation
        if role == ctx.guild.default_role:
            return await ctx.send("❌ Cannot use @everyone!")
        if role.managed:
            return await ctx.send("❌ Cannot use managed role!")
        if role.position >= ctx.guild.me.top_role.position:
            return await ctx.send("❌ Role higher than my top role!")

        roles = self.get_vanity_roles(ctx.guild.id)
        roles[trigger.lower()] = str(role.id)
        self.save_vanity_roles(ctx.guild.id, roles)

        remaining = max_roles - len(roles)
        await ctx.send(f"✅ Added: `{trigger}` → {role.mention}\n**{tier}**: {len(roles)}/{max_roles} roles\n剩{remaining} slots left")

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def vanity_list(self, ctx):
        data = self._get_data()
        gid = str(ctx.guild.id)
        sub = data["subscriptions"].get(gid, {})
        tier = sub.get("tier", "FREE")
        
        role_limits = {"BASIC": 1, "PRO": 3, "ULTRA": 5, "CUSTOM": 999, "FREE": 0}
        max_roles = role_limits.get(tier.upper(), 0)
        
        if not self.is_premium(ctx.guild.id):
            return await ctx.send("❌ Premium only!")
        
        roles = self.get_vanity_roles(ctx.guild.id)
        if not roles:
            return await ctx.send(f"No vanity roles. **{tier}**: {len(roles)}/{max_roles}")
        
        embed = discord.Embed(title=f"🎭 Vanity Roles - {tier}", color=discord.Color.purple())
        embed.set_footer(text=f"{len(roles)}/{max_roles} | !premium_price to upgrade")
        
        for trigger, role_id in roles.items():
            role = ctx.guild.get_role(int(role_id))
            embed.add_field(
                name=trigger, 
                value=role.mention if role else f"ID: {role_id}", 
                inline=False
            )
        await ctx.send(embed=embed)
    

    @commands.command()
    @commands.has_permissions(manage_roles=True)
    async def vanity_del(self, ctx, trigger: str):
        if not self.is_premium(ctx.guild.id):
            return await ctx.send("❌ Premium only!")
        
        roles = self.get_vanity_roles(ctx.guild.id)
        if trigger.lower() in roles:
            del roles[trigger.lower()]
            self.save_vanity_roles(ctx.guild.id, roles)
            await ctx.send(f"✅ Removed `{trigger}`")
        else:
            await ctx.send("❌ Trigger not found.")

    @commands.command()
    async def vanity_debug(self, ctx, member: discord.Member = None):
        """Debug current status matching"""
        member = member or ctx.author
        if not self.is_premium(ctx.guild.id):
            return await ctx.send("❌ Premium only!")
        
        status = " ".join([a.name for a in member.activities 
                          if isinstance(a, discord.CustomActivity)])
        roles = self.get_vanity_roles(ctx.guild.id)
        
        matches = []
        for trigger, role_id in roles.items():
            if trigger.lower() in status.lower():
                role = ctx.guild.get_role(int(role_id))
                matches.append(f"✅ `{trigger}` → {role.mention if role else role_id}")
        
        embed = discord.Embed(title="🔍 Vanity Debug", color=discord.Color.blue())
        embed.add_field(name="Status", value=status or "No custom status", inline=False)
        embed.add_field(name="Matches", value="\n".join(matches) or "None", inline=False)
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Vanity(bot))

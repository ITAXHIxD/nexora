import discord
from discord.ext import commands
from discord import app_commands
import datetime
from typing import Optional
import logging
import asyncio

logger = logging.getLogger(__name__)


class AFKView(discord.ui.View):
    def __init__(self, timeout=180):
        super().__init__(timeout=timeout)

    @discord.ui.button(label="👋 Remove AFK", style=discord.ButtonStyle.green)
    async def remove_afk_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = interaction.client.get_cog("AFK")
        if cog:
            data = await cog.get_afk(interaction.user.id)
            if data:
                await cog.remove_afk_status(interaction.user, interaction.guild, silent=True)
                return await interaction.response.send_message("✅ AFK status removed!", ephemeral=True)
        await interaction.response.send_message("❌ You are not currently AFK!", ephemeral=True)


class AFK(commands.Cog):
    """AFK system — MongoDB via bot.mongo_db"""

    def __init__(self, bot):
        self.bot = bot
        self.col = None
        self.processing_removal = set()

    async def cog_load(self):
        if self.bot.mongo_db is not None:
            self.col = self.bot.mongo_db["afk"]
            logger.info("AFK ready — MongoDB collection 'afk'")
        else:
            logger.warning("AFK: mongo_db not available")
        logger.info("Loaded AFK")

    # ── DB helpers ─────────────────────────────────────────────────────────────

    async def get_afk(self, user_id: int):
        if self.col is None: return None
        return await self.col.find_one({"_id": user_id})

    async def set_afk(self, user_id: int, data: dict):
        if self.col is None: return
        await self.col.update_one({"_id": user_id}, {"$set": data}, upsert=True)

    async def delete_afk(self, user_id: int):
        if self.col is None: return
        await self.col.delete_one({"_id": user_id})

    def format_duration(self, delta: datetime.timedelta) -> str:
        days  = delta.days
        hours = delta.seconds // 3600
        mins  = (delta.seconds % 3600) // 60
        parts = []
        if days:  parts.append(f"{days}d")
        if hours: parts.append(f"{hours}h")
        if mins or not parts: parts.append(f"{mins}m")
        return " ".join(parts)

    async def remove_afk_status(self, member: discord.Member, guild: discord.Guild, silent=False):
        if member.id in self.processing_removal:
            return None
        afk_data = await self.get_afk(member.id)
        if not afk_data:
            return None
        try:
            self.processing_removal.add(member.id)
            await self.delete_afk(member.id)
            try:
                if member.display_name.startswith("[AFK] "):
                    original = afk_data.get("name", "")
                    await member.edit(nick=original if original and len(original) <= 32 else None)
            except (discord.Forbidden, discord.HTTPException):
                pass
            if not silent and afk_data.get("dm_notifications", True) and afk_data.get("mentions"):
                try:
                    mentions     = afk_data["mentions"]
                    mention_list = "\n".join(f"• {m}" for m in mentions[-10:])
                    embed = discord.Embed(
                        title="📬 AFK Mention Summary",
                        description=f"You were mentioned **{len(mentions)}** time(s) while AFK:\n\n{mention_list}",
                        color=discord.Color.blue(),
                        timestamp=datetime.datetime.now(datetime.timezone.utc)
                    )
                    embed.set_footer(text=f"From {guild.name}")
                    await member.send(embed=embed)
                except discord.Forbidden:
                    pass
            return afk_data
        finally:
            self.processing_removal.discard(member.id)

    # ── Commands ───────────────────────────────────────────────────────────────

    @commands.hybrid_command(name="afk", description="Set your AFK status")
    @app_commands.describe(reason="Reason for going AFK", global_afk="Apply across all servers")
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def afk(self, ctx: commands.Context, global_afk: Optional[bool] = False, *, reason: Optional[str] = "AFK"):
        if await self.get_afk(ctx.author.id):
            return await ctx.send(embed=discord.Embed(description="❌ You are already AFK!", color=discord.Color.red()))
        original_name = ctx.author.display_name.replace("[AFK] ", "")
        now = datetime.datetime.now(datetime.timezone.utc)
        await self.set_afk(ctx.author.id, {
            "reason": reason, "time": now.isoformat(), "name": original_name,
            "guild_id": ctx.guild.id if not global_afk else None,
            "mentions": [], "global": global_afk, "dm_notifications": True,
        })
        try:
            await ctx.author.edit(nick=f"[AFK] {original_name}"[:32])
        except discord.Forbidden:
            pass
        scope = "globally" if global_afk else f"in {ctx.guild.name}"
        embed = discord.Embed(
            title="💤 AFK Status Set",
            description=f"**Reason:** {reason}\n**Scope:** {scope}\n\n*Send any message to remove AFK status*",
            color=discord.Color.green(), timestamp=now
        )
        embed.set_footer(text=f"Set by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed, view=AFKView())

    @commands.hybrid_command(name="unafk", description="Manually remove your AFK status")
    async def unafk(self, ctx: commands.Context):
        afk_data = await self.get_afk(ctx.author.id)
        if not afk_data:
            return await ctx.send(embed=discord.Embed(description="❌ You are not AFK!", color=discord.Color.red()))
        delta    = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(afk_data["time"])
        duration = self.format_duration(delta)
        await self.remove_afk_status(ctx.author, ctx.guild)
        await ctx.send(embed=discord.Embed(
            description=f"✅ AFK removed! You were AFK for **{duration}**.", color=discord.Color.green()
        ))

    @commands.hybrid_command(name="afkstatus", description="Check AFK status of a user")
    @app_commands.describe(user="User to check (leave blank for yourself)")
    async def afkstatus(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        target   = user or ctx.author
        afk_data = await self.get_afk(target.id)
        if not afk_data:
            return await ctx.send(embed=discord.Embed(
                description=f"{'You are' if target == ctx.author else f'{target.mention} is'} not AFK.",
                color=discord.Color.blue()
            ))
        delta    = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(afk_data["time"])
        duration = self.format_duration(delta)
        embed = discord.Embed(title=f"💤 {target.display_name}'s AFK Status", color=discord.Color.blue())
        embed.add_field(name="📝 Reason",   value=afk_data["reason"],                                    inline=False)
        embed.add_field(name="⏱️ Duration", value=duration,                                              inline=True)
        embed.add_field(name="🌐 Scope",    value="Global" if afk_data.get("global") else "Server",      inline=True)
        embed.add_field(name="📬 Mentions", value=str(len(afk_data.get("mentions", []))),                inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="afklist", description="List all AFK users in this server")
    @commands.has_permissions(manage_messages=True)
    async def afklist(self, ctx: commands.Context):
        if self.col is None:
            return await ctx.send(embed=discord.Embed(description="❌ Database not connected.", color=discord.Color.red()))
        cursor = self.col.find({"$or": [{"global": True}, {"guild_id": ctx.guild.id}]})
        rows   = []
        async for doc in cursor:
            member = ctx.guild.get_member(doc["_id"])
            if member:
                delta    = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(doc["time"])
                duration = self.format_duration(delta)
                rows.append(f"**{member.display_name}** — {doc['reason']} ({duration})")
        if not rows:
            return await ctx.send(embed=discord.Embed(description="📭 No AFK users.", color=discord.Color.blue()))
        embed = discord.Embed(title=f"💤 AFK Users in {ctx.guild.name}", description="\n".join(rows[:25]), color=discord.Color.blue())
        embed.set_footer(text=f"Total: {len(rows)}")
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="afksettings", description="Toggle DM notifications for AFK mentions")
    @app_commands.describe(dm_notifications="Enable or disable DM notifications")
    async def afksettings(self, ctx: commands.Context, dm_notifications: bool):
        if not await self.get_afk(ctx.author.id):
            return await ctx.send(embed=discord.Embed(description="❌ You must be AFK first!", color=discord.Color.red()), ephemeral=True)
        if self.col:
            await self.col.update_one({"_id": ctx.author.id}, {"$set": {"dm_notifications": dm_notifications}})
        status = "enabled" if dm_notifications else "disabled"
        await ctx.send(embed=discord.Embed(description=f"✅ DM notifications **{status}**.", color=discord.Color.green()), ephemeral=True)

    # ── Listeners ──────────────────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        if message.author.bot or not message.guild:
            return
        ctx = await self.bot.get_context(message)
        if ctx.valid and ctx.command:
            return
        try:
            if message.author.id not in self.processing_removal:
                afk_data = await self.get_afk(message.author.id)
                if afk_data and (afk_data.get("global") or afk_data.get("guild_id") == message.guild.id):
                    delta    = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(afk_data["time"])
                    duration = self.format_duration(delta)
                    removed  = await self.remove_afk_status(message.author, message.guild)
                    if removed:
                        embed = discord.Embed(
                            description=f"👋 Welcome back, {message.author.mention}! AFK removed.\n**Duration:** {duration}",
                            color=discord.Color.green()
                        )
                        if removed.get("mentions"):
                            embed.add_field(name="📬 Mentions", value=f"You were mentioned **{len(removed['mentions'])}** time(s).")
                        msg = await message.channel.send(embed=embed)
                        await asyncio.sleep(10)
                        try: await msg.delete()
                        except: pass

            for mentioned in message.mentions:
                afk_data = await self.get_afk(mentioned.id)
                if afk_data and (afk_data.get("global") or afk_data.get("guild_id") == message.guild.id):
                    delta       = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(afk_data["time"])
                    duration    = self.format_duration(delta)
                    mention_str = f"[{message.author.name} in #{message.channel.name}]({message.jump_url})"
                    if self.col:
                        await self.col.update_one({"_id": mentioned.id}, {"$push": {"mentions": mention_str}})
                    embed = discord.Embed(
                        title=f"💤 {mentioned.display_name} is AFK",
                        description=f"**Reason:** {afk_data['reason']}\n**Duration:** {duration}",
                        color=discord.Color.orange()
                    )
                    embed.set_thumbnail(url=mentioned.display_avatar.url)
                    notif = await message.channel.send(embed=embed)
                    await asyncio.sleep(15)
                    try: await notif.delete()
                    except: pass
                    if afk_data.get("dm_notifications", True):
                        try:
                            dm_embed = discord.Embed(
                                title="📬 New Mention While AFK",
                                description=(
                                    f"**From:** {message.author.mention} in {message.guild.name}\n"
                                    f"**Channel:** {message.channel.mention}\n"
                                    f"**Message:** {message.content[:100] or '*No content*'}\n\n"
                                    f"[Jump to Message]({message.jump_url})"
                                ),
                                color=discord.Color.blue(),
                                timestamp=datetime.datetime.now(datetime.timezone.utc)
                            )
                            await mentioned.send(embed=dm_embed)
                        except discord.Forbidden:
                            pass
        except Exception as e:
            logger.error("on_message error: %s", e)

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        if after.bot: return
        afk_data = await self.get_afk(before.id)
        if afk_data:
            try:
                if before.display_name.startswith("[AFK] ") and not after.display_name.startswith("[AFK] "):
                    await after.edit(nick=f"[AFK] {afk_data.get('name', '')}"[:32])
            except Exception:
                pass


async def setup(bot):
    await bot.add_cog(AFK(bot))
    logger.info("Loaded AFK")
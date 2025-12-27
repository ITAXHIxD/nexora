import discord
from discord.ext import commands
from discord import app_commands
import datetime
from typing import Optional
import logging
import json
import os
import asyncio

# Set up logging
logger = logging.getLogger(__name__)
log = logger  # Alias for compatibility


class AFKView(discord.ui.View):
    """View with buttons for AFK notifications"""
    def __init__(self, timeout=180):
        super().__init__(timeout=timeout)
    
    @discord.ui.button(label="👋 Remove AFK", style=discord.ButtonStyle.green)
    async def remove_afk_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Quick button to remove AFK status"""
        cog = interaction.client.get_cog('AFK')
        if cog and interaction.user.id in cog.afk_users:
            await cog.remove_afk_status(interaction.user, interaction.guild, silent=True)
            await interaction.response.send_message("✅ Your AFK status has been removed!", ephemeral=True)
        else:
            await interaction.response.send_message("❌ You are not currently AFK!", ephemeral=True)


class AFK(commands.Cog):
    """AFK system with persistent storage and notifications"""
    
    def __init__(self, bot):
        self.bot = bot
        self.afk_users = {}
        self.afk_file = "data/afk_data.json"
        self.processing_removal = set()
        
        os.makedirs("data", exist_ok=True)
        self.load_afk_data()
        
        logger.info("%s loaded with %d AFK users", self.__class__.__name__, len(self.afk_users))

    def load_afk_data(self):
        """Load AFK data from JSON file"""
        try:
            if os.path.exists(self.afk_file):
                with open(self.afk_file, 'r') as f:
                    data = json.load(f)
                    for user_id, afk_data in data.items():
                        self.afk_users[int(user_id)] = {
                            "reason": afk_data["reason"],
                            "time": datetime.datetime.fromisoformat(afk_data["time"]),
                            "name": afk_data["name"],
                            "guild_id": afk_data.get("guild_id"),
                            "mentions": afk_data.get("mentions", []),
                            "global": afk_data.get("global", False),
                            "dm_notifications": afk_data.get("dm_notifications", True)
                        }
                logger.info("Loaded %d AFK users from file", len(self.afk_users))
        except Exception as e:
            logger.error("Error loading AFK data: %s", str(e))

    def save_afk_data(self):
        """Save AFK data to JSON file"""
        try:
            data = {}
            for user_id, afk_data in self.afk_users.items():
                data[str(user_id)] = {
                    "reason": afk_data["reason"],
                    "time": afk_data["time"].isoformat(),
                    "name": afk_data["name"],
                    "guild_id": afk_data.get("guild_id"),
                    "mentions": afk_data.get("mentions", []),
                    "global": afk_data.get("global", False),
                    "dm_notifications": afk_data.get("dm_notifications", True)
                }
            with open(self.afk_file, 'w') as f:
                json.dump(data, f, indent=4)
            logger.debug("Saved %d AFK users to file", len(self.afk_users))
        except Exception as e:
            logger.error("Error saving AFK data: %s", str(e))

    def format_duration(self, delta: datetime.timedelta) -> str:
        """Format timedelta into readable string"""
        days = delta.days
        hours = delta.seconds // 3600
        minutes = (delta.seconds % 3600) // 60
        
        parts = []
        if days > 0:
            parts.append(f"{days}d")
        if hours > 0:
            parts.append(f"{hours}h")
        if minutes > 0 or not parts:
            parts.append(f"{minutes}m")
        
        return " ".join(parts)

    async def remove_afk_status(self, member: discord.Member, guild: discord.Guild, silent: bool = False):
        """Remove AFK status for a user"""
        if member.id in self.processing_removal:
            return False
        
        if member.id not in self.afk_users:
            return False
        
        try:
            self.processing_removal.add(member.id)
            
            afk_data = self.afk_users[member.id].copy()
            del self.afk_users[member.id]
            self.save_afk_data()
            
            # Restore original nickname
            try:
                if member.display_name.startswith("[AFK] "):
                    original_name = afk_data["name"]
                    # Only restore if the name is valid and different
                    if original_name and not original_name.startswith("[AFK] "):
                        if len(original_name) <= 32:
                            await member.edit(nick=original_name)
                        else:
                            await member.edit(nick=None)
                    else:
                        await member.edit(nick=None)
            except discord.Forbidden:
                logger.warning("Missing permissions to change nickname for user %s in guild %s", 
                           member.id, guild.id)
            except discord.HTTPException as e:
                logger.error("HTTP error restoring nickname: %s", str(e))
            except Exception as e:
                logger.error("Error restoring nickname: %s", str(e))
            
            # Send DM with mention summary if enabled and not silent
            if not silent and afk_data.get("dm_notifications", True) and afk_data.get("mentions"):
                try:
                    mention_count = len(afk_data['mentions'])
                    mention_list = "\n".join([f"• {m}" for m in afk_data["mentions"][-10:]])
                    
                    embed = discord.Embed(
                        title="📬 AFK Mention Summary",
                        description=f"You were mentioned **{mention_count}** time(s) while AFK:\n\n{mention_list}",
                        color=discord.Color.blue(),
                        timestamp=datetime.datetime.now(datetime.timezone.utc)
                    )
                    embed.set_footer(text=f"From {guild.name}")
                    await member.send(embed=embed)
                except discord.Forbidden:
                    logger.warning("Cannot send DM to user %s", member.id)
                except Exception as e:
                    logger.error("Error sending DM: %s", str(e))
            
            return afk_data
            
        finally:
            self.processing_removal.discard(member.id)

    @commands.hybrid_command(name="afk", description="Set your AFK status with an optional reason")
    @app_commands.describe(
        reason="The reason for going AFK",
        global_afk="Set AFK status globally across all servers (default: False)"
    )
    @commands.cooldown(1, 10, commands.BucketType.user)
    async def afk(self, ctx: commands.Context, global_afk: Optional[bool] = False, *, reason: Optional[str] = "AFK"):
        """Set your AFK status with an optional reason"""
        try:
            member = ctx.author
            
            if member.id in self.afk_users:
                embed = discord.Embed(
                    description="❌ You are already AFK! Send a message to remove your AFK status.",
                    color=discord.Color.red()
                )
                return await ctx.send(embed=embed, ephemeral=True)
            
            # Store original name (without [AFK] prefix if present)
            original_name = member.display_name.replace("[AFK] ", "")
            
            self.afk_users[member.id] = {
                "reason": reason,
                "time": datetime.datetime.now(datetime.timezone.utc),
                "name": original_name,
                "guild_id": ctx.guild.id if not global_afk else None,
                "mentions": [],
                "global": global_afk,
                "dm_notifications": True
            }
            
            self.save_afk_data()
            
            # Change nickname to show AFK status
            try:
                if not member.display_name.startswith("[AFK] "):
                    new_nick = f"[AFK] {original_name}"[:32]
                    await member.edit(nick=new_nick)
            except discord.Forbidden:
                await ctx.send("Missing permissions to change nickname for user %s in", member.id)
            except Exception as e:
                logger.error("Error changing nickname: %s", str(e))

            scope = "globally" if global_afk else f"in {ctx.guild.name}"
            embed = discord.Embed(
                title="💤 AFK Status Set",
                description=f"**Reason:** {reason}\n**Scope:** {scope}\n\n*Send any message to automatically remove your AFK status*",
                color=discord.Color.green(),
                timestamp=datetime.datetime.now(datetime.timezone.utc)
            )
            embed.set_footer(text=f"Set by {member.display_name}", icon_url=member.display_avatar.url)
            
            view = AFKView()
            await ctx.send(embed=embed, view=view)
            logger.info("User %s set AFK %s with reason: %s", member.id, scope, reason)
            
        except Exception as e:
            logger.error("Error in afk command: %s", str(e))
            embed = discord.Embed(
                description="❌ An error occurred while setting your AFK status.",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)

    @commands.hybrid_command(name="unafk", description="Manually remove your AFK status")
    async def unafk(self, ctx: commands.Context):
        """Manually remove AFK status"""
        if ctx.author.id not in self.afk_users:
            embed = discord.Embed(
                description="❌ You are not currently AFK!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed, ephemeral=True)
        
        afk_data = self.afk_users.get(ctx.author.id)
        duration = "Unknown"
        if afk_data:
            time_delta = datetime.datetime.now(datetime.timezone.utc) - afk_data["time"]
            duration = self.format_duration(time_delta)
        
        removed_data = await self.remove_afk_status(ctx.author, ctx.guild)
        
        if removed_data:
            embed = discord.Embed(
                description=f"✅ Welcome back! Your AFK status has been removed.\n**Duration:** {duration}",
                color=discord.Color.green()
            )
            await ctx.send(embed=embed)
            
    @commands.hybrid_command(name="afkstatus", description="Check your or another user's AFK status")
    @app_commands.describe(user="The user to check (optional)")
    async def afkstatus(self, ctx: commands.Context, user: Optional[discord.Member] = None):
        """Check AFK status of yourself or another user"""
        target = user or ctx.author
        
        if target.id not in self.afk_users:
            embed = discord.Embed(
                description=f"{'You are' if target == ctx.author else f'{target.mention} is'} not currently AFK.",
                color=discord.Color.blue()
            )
            return await ctx.send(embed=embed)
        
        afk_data = self.afk_users[target.id]
        time_delta = datetime.datetime.now(datetime.timezone.utc) - afk_data["time"]
        duration = self.format_duration(time_delta)
        
        scope = "Global" if afk_data.get("global", False) else "Server-specific"
        
        embed = discord.Embed(
            title=f"💤 {target.display_name}'s AFK Status",
            color=discord.Color.blue(),
            timestamp=afk_data["time"]
        )
        embed.add_field(name="📝 Reason", value=afk_data["reason"], inline=False)
        embed.add_field(name="⏱️ Duration", value=duration, inline=True)
        embed.add_field(name="🌐 Scope", value=scope, inline=True)
        embed.add_field(name="📬 Mentions", value=str(len(afk_data.get("mentions", []))), inline=True)
        embed.set_thumbnail(url=target.display_avatar.url)
        embed.set_footer(text="AFK since")
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="afklist", description="View all AFK users in this server")
    @commands.has_permissions(manage_messages=True)
    async def afklist(self, ctx: commands.Context):
        """List all AFK users in the server (requires Manage Messages)"""
        guild_afk_users = []
        
        for user_id, afk_data in self.afk_users.items():
            if afk_data.get("global", False) or afk_data.get("guild_id") == ctx.guild.id:
                member = ctx.guild.get_member(user_id)
                if member:
                    time_delta = datetime.datetime.now(datetime.timezone.utc) - afk_data["time"]
                    duration = self.format_duration(time_delta)
                    guild_afk_users.append(f"**{member.display_name}** - {afk_data['reason']} ({duration})")
        
        if not guild_afk_users:
            embed = discord.Embed(
                description="📭 No users are currently AFK in this server.",
                color=discord.Color.blue()
            )
            return await ctx.send(embed=embed)
        
        embed = discord.Embed(
            title=f"💤 AFK Users in {ctx.guild.name}",
            description="\n".join(guild_afk_users[:25]),
            color=discord.Color.blue(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.set_footer(text=f"Total: {len(guild_afk_users)} AFK users")
        
        await ctx.send(embed=embed)

    @commands.hybrid_command(name="afksettings", description="Configure your AFK notification settings")
    @app_commands.describe(dm_notifications="Enable or disable DM notifications for mentions")
    async def afksettings(self, ctx: commands.Context, dm_notifications: bool):
        """Configure AFK notification preferences"""
        if ctx.author.id not in self.afk_users:
            embed = discord.Embed(
                description="❌ You need to be AFK to change settings. Use `/afk` first!",
                color=discord.Color.red()
            )
            return await ctx.send(embed=embed, ephemeral=True)
        
        self.afk_users[ctx.author.id]["dm_notifications"] = dm_notifications
        self.save_afk_data()
        
        status = "enabled" if dm_notifications else "disabled"
        embed = discord.Embed(
            description=f"✅ DM notifications for mentions have been **{status}**.",
            color=discord.Color.green()
        )
        await ctx.send(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle AFK status on message send and mention notifications"""
        if message.author.bot or not message.guild:
            return

        # Check if this message is a command - if so, ignore it for AFK removal
        ctx = await self.bot.get_context(message)
        if ctx.valid and ctx.command:
            return  # Don't remove AFK for command invocations

        try:
            # AUTOMATIC REMOVAL: Remove AFK status if user sends ANY non-command message
            if message.author.id in self.afk_users and message.author.id not in self.processing_removal:
                afk_data = self.afk_users[message.author.id]
                
                # Check if AFK is global or specific to this guild
                if afk_data.get("global", False) or afk_data.get("guild_id") == message.guild.id:
                    time_delta = datetime.datetime.now(datetime.timezone.utc) - afk_data["time"]
                    duration = self.format_duration(time_delta)
                    
                    # Remove AFK status
                    removed_data = await self.remove_afk_status(message.author, message.guild)
                    
                    if removed_data:
                        embed = discord.Embed(
                            description=f"👋 Welcome back, {message.author.mention}! Your AFK status has been removed.\n**Duration:** {duration}",
                            color=discord.Color.green()
                        )
                        
                        if removed_data.get("mentions"):
                            embed.add_field(
                                name="📬 Mentions",
                                value=f"You were mentioned **{len(removed_data['mentions'])}** time(s) while AFK.",
                                inline=False
                            )
                        
                        # Send welcome back message and delete after 10 seconds
                        welcome_msg = await message.channel.send(embed=embed)
                        await asyncio.sleep(10)
                        try:
                            await welcome_msg.delete()
                        except:
                            pass
                        
            # Notify if mentioned user is AFK
            if message.mentions:
                for mentioned_user in message.mentions:
                    if mentioned_user.id in self.afk_users:
                        afk_info = self.afk_users[mentioned_user.id]
                        
                        # Check if AFK is global or specific to this guild
                        if afk_info.get("global", False) or afk_info.get("guild_id") == message.guild.id:
                            time_delta = datetime.datetime.now(datetime.timezone.utc) - afk_info["time"]
                            duration = self.format_duration(time_delta)
                            
                            # Store mention for later notification
                            mention_info = f"[{message.author.name} in #{message.channel.name}]({message.jump_url})"
                            afk_info["mentions"].append(mention_info)
                            self.save_afk_data()
                            
                            embed = discord.Embed(
                                title=f"💤 {mentioned_user.display_name} is AFK",
                                description=f"**Reason:** {afk_info['reason']}\n**Duration:** {duration}",
                                color=discord.Color.orange(),
                                timestamp=afk_info["time"]
                            )
                            embed.set_thumbnail(url=mentioned_user.display_avatar.url)
                            embed.set_footer(text="AFK since")
                            
                            afk_msg = await message.channel.send(embed=embed)
                            await asyncio.sleep(15)
                            try:
                                await afk_msg.delete()
                            except:
                                pass
                            
                            # Send DM to AFK user if enabled
                            if afk_info.get("dm_notifications", True):
                                try:
                                    dm_embed = discord.Embed(
                                        title="📬 New Mention While AFK",
                                        description=f"**From:** {message.author.mention} in {message.guild.name}\n"
                                                   f"**Channel:** {message.channel.mention}\n"
                                                   f"**Message:** {message.content[:100] if message.content else '*No content*'}...\n\n"
                                                   f"[Jump to Message]({message.jump_url})",
                                        color=discord.Color.blue(),
                                        timestamp=datetime.datetime.now(datetime.timezone.utc)
                                    )
                                    await mentioned_user.send(embed=dm_embed)
                                except discord.Forbidden:
                                    log.warning("Cannot send DM to user %s", mentioned_user.id)
                                except Exception as e:
                                    log.error("Error sending DM: %s", str(e))
                    
        except Exception as e:
            log.error("Error in on_message event: %s", str(e))

    @commands.Cog.listener()
    async def on_member_update(self, before, after):
        """Track nickname changes to prevent AFK tag removal by users"""
        if before.id in self.afk_users and not after.bot:
            try:
                # If user manually removes [AFK] tag, re-apply it
                if before.display_name.startswith("[AFK] ") and not after.display_name.startswith("[AFK] "):
                    original_name = self.afk_users[before.id]['name']
                    await after.edit(nick=f"[AFK] {original_name}"[:32])
                    log.info("Re-applied AFK tag for user %s", before.id)
            except Exception as e:
                log.debug("Could not re-apply AFK tag: %s", str(e))

    async def cog_unload(self):
        """Clean up when cog is unloaded"""
        self.save_afk_data()
        logger.info("%s unloaded", self.__class__.__name__)


async def setup(bot):
    await bot.add_cog(AFK(bot))
    logger.info("Loaded %s", AFK.__name__)
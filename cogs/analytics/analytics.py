import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime
from collections import defaultdict, Counter # <--- CRITICAL FIX: Added Counter and defaultdict
import json
import asyncio
import logging
import io
import math 
import discord.utils # Import discord.utils to use utcnow()

logger = logging.getLogger(__name__)

# --- Helper Function for Color Consistency ---
def get_config_color(bot, key: str, fallback: int = 0x5865F2) -> int:
    """Safely retrieves a color from the bot config."""
    try:
        return int(bot.bot_config['ui_settings'][key], 16)
    except (AttributeError, KeyError, ValueError):
        return fallback

# --- Views, Modals, and Cogs ---

class AnalyticsView(discord.ui.View):
    def __init__(self, bot, guild: discord.Guild):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild = guild
        self.message = None 
        self.color_map = {
            "primary": get_config_color(bot, 'embed_color', 0x5865F2),
            "secondary": get_config_color(bot, 'success_color', 0x57F287),
            "success": get_config_color(bot, 'warning_color', 0xFEE75C),
            "danger": get_config_color(bot, 'error_color', 0xED4245)
        }

    # FIX APPLIED HERE: Replaced self.message.interaction.user.id with self.message.interaction_metadata.user_id
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        """Ensure only the original command user can interact with the view."""
        if self.message and self.message.interaction_metadata:
            original_user_id = self.message.interaction_metadata.user_id
        elif self.message and self.message.interaction:
            # Fallback for older discord.py versions
            original_user_id = self.message.interaction.user.id
        else:
            # Should not happen, but prevents crash
            original_user_id = None

        if original_user_id and interaction.user.id != original_user_id:
            await interaction.response.send_message("❌ This session is not yours.", ephemeral=True)
            return False
        return True


    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            if self.message:
                await self.message.edit(view=None)
        except discord.NotFound:
            pass

    # --- Button Callbacks (Remain unchanged) ---
    @discord.ui.button(label="Server Overview", style=discord.ButtonStyle.primary, emoji="🏠")
    async def server_overview(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = await self.create_server_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

    @discord.ui.button(label="Member Stats", style=discord.ButtonStyle.secondary, emoji="👥")
    async def member_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = await self.create_member_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

    @discord.ui.button(label="Channel Stats", style=discord.ButtonStyle.success, emoji="📝")
    async def channel_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = await self.create_channel_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)

    @discord.ui.button(label="Role Stats", style=discord.ButtonStyle.danger, emoji="🎭")
    async def role_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        embed = await self.create_role_embed()
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=self)
    
    # --- Embed Creation Methods (Updated Member/Role Embeds) ---

    async def create_server_embed(self) -> discord.Embed:
        """Create server overview embed"""
        embed = discord.Embed(
            title=f"🏠 Server Overview - {self.guild.name}",
            description=f"Comprehensive server statistics",
            color=self.color_map['primary'],
            timestamp=discord.utils.utcnow()
        )
        
        embed.set_thumbnail(url=self.guild.icon.url if self.guild.icon else None)
        
        # Basic stats
        total_members = self.guild.member_count
        online_members = sum(1 for m in self.guild.members if m.status != discord.Status.offline)
        total_bots = sum(1 for m in self.guild.members if m.bot)
        humans = total_members - total_bots
        
        embed.add_field(
            name="👥 Members",
            value=f"**Total:** {total_members:,}\n"
                  f"**Humans:** {humans:,}\n"
                  f"**Bots:** {total_bots:,}\n"
                  f"**Online:** {online_members:,}",
            inline=True
        )
        
        # Channels
        text_channels = len(self.guild.text_channels)
        voice_channels = len(self.guild.voice_channels)
        categories = len(self.guild.categories)
        threads = sum(len(channel.threads) for channel in self.guild.text_channels)
        
        embed.add_field(
            name="📝 Channels",
            value=f"**Text:** {text_channels:,}\n"
                  f"**Voice:** {voice_channels:,}\n"
                  f"**Categories:** {categories:,}\n"
                  f"**Threads:** {threads:,}",
            inline=True
        )
        
        # Server info
        boost_level = self.guild.premium_tier
        boost_count = self.guild.premium_subscription_count
        
        embed.add_field(
            name="ℹ️ Server Info",
            value=f"**Created:** <t:{int(self.guild.created_at.timestamp())}:R>\n"
                  f"**Owner:** {self.guild.owner.mention if self.guild.owner else 'Unknown'}\n"
                  f"**Boost Level:** {boost_level}\n"
                  f"**Boosts:** {boost_count}",
            inline=True
        )
        
        # Features
        features = []
        if "COMMUNITY" in self.guild.features: features.append("🏘️ Community")
        if "PARTNERED" in self.guild.features: features.append("🤝 Partnered")
        if "VERIFIED" in self.guild.features: features.append("✅ Verified")
        if "DISCOVERABLE" in self.guild.features: features.append("🔍 Discoverable")
        
        if features:
            embed.add_field(
                name="🌟 Special Features",
                value="\n".join(features[:5]),
                inline=False
            )
        
        embed.set_footer(text=f"Server ID: {self.guild.id}")
        return embed

    async def create_member_embed(self) -> discord.Embed:
        """Create member analytics embed"""
        embed = discord.Embed(
            title=f"👥 Member Analytics - {self.guild.name}",
            color=self.color_map['secondary'],
            timestamp=discord.utils.utcnow()
        )
        
        # Status breakdown
        status_counts = {"online": 0, "idle": 0, "dnd": 0, "offline": 0}
        for member in self.guild.members:
            if not member.bot:
                status_counts[str(member.status)] += 1
        
        embed.add_field(
            name="📊 Status Distribution (Humans)",
            value=f"🟢 **Online:** {status_counts['online']:,}\n"
                  f"🟡 **Idle:** {status_counts['idle']:,}\n"
                  f"🔴 **DND:** {status_counts['dnd']:,}\n"
                  f"⚫ **Offline:** {status_counts['offline']:,}",
            inline=True
        )
        
        # Join patterns (last 30 days)
        now = discord.utils.utcnow()
        recent_joins = [m for m in self.guild.members if m.joined_at and (now - m.joined_at).days <= 30]
        week_joins = [m for m in recent_joins if (now - m.joined_at).days <= 7]
        
        avg_joins = len(recent_joins) / 30 if len(recent_joins) > 0 else 0
        
        embed.add_field(
            name="📈 Recent Activity",
            value=f"**Last 7 days:** {len(week_joins):,} joins\n"
                  f"**Last 30 days:** {len(recent_joins):,} joins\n"
                  f"**Daily average:** {avg_joins:.1f}",
            inline=True
        )
        
        # Top roles by member count
        # FIX APPLIED HERE: Counter is now defined via import
        role_counts = Counter() 
        for member in self.guild.members:
            if not member.bot:
                for role in member.roles:
                    if role != self.guild.default_role:
                        role_counts[role.name] += 1
        
        top_roles = role_counts.most_common(5)
        if top_roles:
            roles_text = "\n".join([f"**{role}:** {count:,}" for role, count in top_roles])
            embed.add_field(
                name="🎭 Popular Roles",
                value=roles_text,
                inline=False
            )
        
        embed.set_footer(text="Human members only (bots excluded)")
        return embed

    async def create_channel_embed(self) -> discord.Embed:
        """Create channel analytics embed"""
        embed = discord.Embed(
            title=f"📝 Channel Analytics - {self.guild.name}",
            color=self.color_map['success'],
            timestamp=discord.utils.utcnow()
        )
        
        # Channel breakdown
        text_channels = self.guild.text_channels
        voice_channels = self.guild.voice_channels
        categories = self.guild.categories
        
        # Voice channel activity
        voice_members = sum(len(vc.members) for vc in voice_channels)
        active_voice = [vc for vc in voice_channels if len(vc.members) > 0]
        
        usage_rate = (len(active_voice) / len(voice_channels) * 100) if voice_channels else 0
        
        embed.add_field(
            name="🎤 Voice Activity",
            value=f"**Members in voice:** {voice_members:,}\n"
                  f"**Active channels:** {len(active_voice)}/{len(voice_channels)}\n"
                  f"**Usage rate:** {usage_rate:.1f}%",
            inline=True
        )
        
        # Channel types
        embed.add_field(
            name="📊 Channel Breakdown",
            value=f"**Text Channels:** {len(text_channels):,}\n"
                  f"**Voice Channels:** {len(voice_channels):,}\n"
                  f"**Categories:** {len(categories):,}\n"
                  f"**Total:** {len(self.guild.channels):,}",
            inline=True
        )
        
        # Recent channel activity
        recent_activity = []
        for channel in text_channels:
            if channel.permissions_for(self.guild.me).read_message_history:
                try:
                    async for message in channel.history(limit=1):
                        recent_activity.append((channel, message.created_at))
                        break
                except discord.Forbidden:
                    continue
                except discord.HTTPException:
                    continue
        
        if recent_activity:
            # FIX APPLIED HERE: Changed key from x[20] to x[1] (the timestamp)
            recent_activity.sort(key=lambda x: x[1], reverse=True) 
            active_channels = recent_activity[:5]
            
            activity_text = "\n".join([
                f"**{channel.name}:** <t:{int(last_msg.timestamp())}:R>"
                for channel, last_msg in active_channels
            ])
            
            embed.add_field(
                name="⚡ Recent Activity (Last Message)",
                value=activity_text,
                inline=False
            )

        return embed

    async def create_role_embed(self) -> discord.Embed:
        """Create role analytics embed"""
        embed = discord.Embed(
            title=f"🎭 Role Analytics - {self.guild.name}",
            color=self.color_map['primary'],
            timestamp=discord.utils.utcnow()
        )
        
        roles = [role for role in self.guild.roles if role != self.guild.default_role]
        
        # Role distribution
        role_members = [(role, len(role.members)) for role in roles]
        role_members.sort(key=lambda x: x[1], reverse=True)
        
        # Most popular roles
        popular_roles = role_members[:8]
        if popular_roles:
            roles_text = "\n".join([
                f"**{role.name}:** {count:,} members"
                for role, count in popular_roles
            ])
            embed.add_field(
                name="👑 Most Popular Roles",
                value=roles_text,
                inline=False
            )
        
        # Role statistics
        total_roles = len(roles)
        assigned_roles = len([role for role in roles if len(role.members) > 0])
        
        usage_rate = (assigned_roles/total_roles*100) if total_roles else 0
        
        embed.add_field(
            name="📊 Role Statistics",
            value=f"**Total Roles:** {total_roles:,}\n"
                  f"**Assigned:** {assigned_roles:,}\n"
                  f"**Unused:** {total_roles - assigned_roles:,}\n"
                  f"**Usage Rate:** {usage_rate:.1f}%",
            inline=True
        )
        
        # Permission roles
        admin_roles = len([role for role in roles if role.permissions.administrator])
        mod_roles = len([role for role in roles if role.permissions.manage_messages and not role.permissions.administrator])
        
        embed.add_field(
            name="🔐 Permission Breakdown",
            value=f"**Admin Roles:** {admin_roles:,}\n"
                  f"**Moderator Roles:** {mod_roles:,}\n"
                  f"**Regular Roles:** {total_roles - admin_roles - mod_roles:,}",
            inline=True
        )
        
        return embed

class Analytics(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        
        if not hasattr(self.bot, 'command_stats'):
            self.bot.command_stats = defaultdict(int)

    @commands.Cog.listener()
    async def on_app_command_completion(self, interaction: discord.Interaction, command):
        """Track slash command usage"""
        self.bot.command_stats[command.name] += 1
        
    # --- COMMAND 1: Interactive Server Analytics Dashboard ---
    @commands.hybrid_command(name="server_analytics", description="Comprehensive server analytics with interactive navigation.")
    async def server_analytics(self, ctx: commands.Context):
        """Interactive server analytics dashboard"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server!", ephemeral=True)
            return
        
        await ctx.defer()
        
        view = AnalyticsView(self.bot, ctx.guild)
        embed = await view.create_server_embed()
        
        message = await ctx.send(embed=embed, view=view)
        view.message = message

    # --- COMMAND 2: Detailed Bot Stats (Usage Stats) ---
    @commands.hybrid_command(name="usage_stats", description="Display bot statistics and popular command usage.")
    async def usage_stats(self, ctx: commands.Context):
        """Show bot analytics and performance"""
        await ctx.defer()
        
        embed_color = get_config_color(self.bot, 'warning_color', 0xFFD700)

        embed = discord.Embed(
            title="🤖 Bot Usage Analytics",
            description="Performance metrics and usage statistics across all servers.",
            color=embed_color,
            timestamp=discord.utils.utcnow()
        )
        
        stats = getattr(self.bot, 'bot_stats', {})
        
        uptime = datetime.now() - stats.get('start_time', datetime.now())
        uptime_str = f"{uptime.days}d {uptime.seconds//3600}h {(uptime.seconds//60)%60}m {uptime.seconds%60}s"

        total_commands = len(self.bot.tree.get_commands())
        
        embed.add_field(
            name="📊 Core Stats",
            value=(
                f"**Messages Processed:** {stats.get('messages_processed', 0):,}\n"
                f"**Commands Used (Prefix/Slash):** {stats.get('commands_used', 0):,}\n"
                f"**API Calls:** {stats.get('api_calls_made', 0):,}\n"
                f"**Errors:** {stats.get('errors_encountered', 0):,}"
            ), 
            inline=True
        )
        
        embed.add_field(
            name="⚙️ System & Network",
            value=(
                f"**Uptime:** {uptime_str}\n"
                f"**Servers:** {len(self.bot.guilds):,}\n"
                f"**Total Commands:** {total_commands:,}\n"
                f"**Latency:** {round(self.bot.latency * 1000)}ms"
            ), 
            inline=True
        )
        
        if self.bot.command_stats:
            top_commands = sorted(
                self.bot.command_stats.items(), 
                key=lambda x: x[1], 
                reverse=True
            )[:5]
            
            commands_text = "\n".join([
                f"**/{cmd}:** {count:,} uses"
                for cmd, count in top_commands
            ])
            
            embed.add_field(
                name="🔥 Top 5 Commands (Slash Usage)",
                value=commands_text,
                inline=False
            )
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}")
        
        await ctx.send(embed=embed)


    # --- COMMAND 3: Analytics Export (Server Owner Only) ---
    @commands.hybrid_command(name="analytics_export", description="Export server analytics data (Server Owner only).")
    async def analytics_export(self, ctx: commands.Context):
        """Export analytics data for server owners"""
        if not ctx.guild:
            await ctx.send("❌ This command can only be used in a server.", ephemeral=True)
            return

        if ctx.author.id != ctx.guild.owner_id:
            await ctx.send("❌ Only the server owner can export analytics data!", ephemeral=True)
            return
        
        await ctx.defer(ephemeral=True)
        
        guild = ctx.guild
        
        analytics_data = {
            "server_info": {
                "name": guild.name,
                "id": guild.id,
                "created_at": guild.created_at.isoformat(),
                "member_count": guild.member_count,
                "owner": str(guild.owner) if guild.owner else None
            },
            "members": {
                "total": guild.member_count,
                "bots": sum(1 for m in guild.members if m.bot),
                "humans": sum(1 for m in guild.members if not m.bot),
                "online": sum(1 for m in guild.members if m.status != discord.Status.offline)
            },
            "timestamp_utc": datetime.utcnow().isoformat()
        }
        
        data_bytes = json.dumps(analytics_data, indent=2, default=str).encode('utf-8')
        
        file = discord.File(
            io.BytesIO(data_bytes),
            filename=f"{guild.name}_analytics_{datetime.now().strftime('%Y%m%d')}.json"
        )
        
        embed_color = get_config_color(self.bot, 'success_color')
        embed = discord.Embed(
            title="📊 Analytics Export Complete",
            description="Your server analytics data has been exported.",
            color=embed_color
        )
        
        await ctx.followup.send(embed=embed, file=file, ephemeral=True)

async def setup(bot):
    await bot.add_cog(Analytics(bot))
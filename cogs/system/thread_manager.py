import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta
import json
import os
import asyncio
import logging

logger = logging.getLogger(__name__)


class ThreadManagerSetupView(discord.ui.View):
    def __init__(self, bot, guild_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        
        # Add channel select as a component
        self.channel_selector = discord.ui.ChannelSelect(
            placeholder="Select forum channels to monitor...",
            channel_types=[discord.ChannelType.forum],
            min_values=0,
            max_values=25,
            row=0
        )
        self.channel_selector.callback = self.channel_select_callback
        self.add_item(self.channel_selector)
    
    async def channel_select_callback(self, interaction: discord.Interaction):
        cog = self.bot.get_cog('ThreadManager')
        config = cog.load_guild_config(self.guild_id)
        
        selected_ids = [channel.id for channel in self.channel_selector.values]
        config['forum_channels'] = selected_ids
        config['enabled'] = len(selected_ids) > 0
        
        cog.save_guild_config(self.guild_id, config)
        
        embed = discord.Embed(
            title="✅ Channels Updated",
            description=f"Now monitoring **{len(selected_ids)}** forum channel(s)",
            color=discord.Color.green()
        )
        
        if selected_ids:
            channel_list = "\n".join([f"• <#{cid}>" for cid in selected_ids])
            embed.add_field(name="Monitored Channels", value=channel_list, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Set Inactivity Hours", style=discord.ButtonStyle.primary, emoji="⏰", row=1)
    async def set_inactivity_hours(self, interaction: discord.Interaction, button: discord.ui.Button):
        modal = InactivityModal(self.bot, self.guild_id)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Toggle Enable/Disable", style=discord.ButtonStyle.secondary, emoji="🔄", row=1)
    async def toggle_enabled(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = self.bot.get_cog('ThreadManager')
        config = cog.load_guild_config(self.guild_id)
        config['enabled'] = not config.get('enabled', False)
        
        cog.save_guild_config(self.guild_id, config)
        
        status = "enabled" if config['enabled'] else "disabled"
        color = discord.Color.green() if config['enabled'] else discord.Color.red()
        emoji = "✅" if config['enabled'] else "❌"
        
        embed = discord.Embed(
            title=f"{emoji} Thread Manager {status.title()}",
            description=f"Thread management is now **{status}**.",
            color=color
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="View Current Settings", style=discord.ButtonStyle.success, emoji="📊", row=2)
    async def view_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        cog = self.bot.get_cog('ThreadManager')
        config = cog.load_guild_config(self.guild_id)
        
        embed = discord.Embed(
            title="🔧 Current Thread Manager Settings",
            color=discord.Color.blue(),
            timestamp=datetime.now()
        )
        
        status_emoji = "✅" if config.get('enabled') else "❌"
        embed.add_field(name="Status", value=f"{status_emoji} {'Enabled' if config.get('enabled') else 'Disabled'}", inline=True)
        embed.add_field(name="Inactivity Hours", value=f"⏰ {config.get('inactivity_hours', 48)} hours", inline=True)
        
        monitored = config.get('forum_channels', [])
        if monitored:
            channel_list = "\n".join([f"• <#{cid}>" for cid in monitored[:10]])
            if len(monitored) > 10:
                channel_list += f"\n... and {len(monitored) - 10} more"
            embed.add_field(name=f"Monitored Channels ({len(monitored)})", value=channel_list, inline=False)
        else:
            embed.add_field(name="Monitored Channels", value="None", inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Close", style=discord.ButtonStyle.danger, emoji="❌", row=2)
    async def close_menu(self, interaction: discord.Interaction, button: discord.ui.Button):
        embed = discord.Embed(
            title="✅ Setup Complete",
            description="Thread Manager configuration saved!",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(embed=embed, view=None)

class InactivityModal(discord.ui.Modal):
    def __init__(self, bot, guild_id):
        super().__init__(title="Set Inactivity Hours")
        self.bot = bot
        self.guild_id = guild_id
        
        cog = bot.get_cog('ThreadManager')
        current_hours = cog.load_guild_config(guild_id).get('inactivity_hours', 48)
        
        self.hours_input = discord.ui.TextInput(
            label="Inactivity Hours",
            placeholder="Enter hours before inactivity notice (e.g., 48)",
            default=str(current_hours),
            style=discord.TextStyle.short,
            max_length=4,
            required=True
        )
        self.add_item(self.hours_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            hours = int(self.hours_input.value)
            if hours < 1 or hours > 720:  # 1 hour to 30 days
                await interaction.response.send_message(
                    "❌ Hours must be between 1 and 720 (30 days)!",
                    ephemeral=True
                )
                return
            
            cog = self.bot.get_cog('ThreadManager')
            config = cog.load_guild_config(self.guild_id)
            config['inactivity_hours'] = hours
            cog.save_guild_config(self.guild_id, config)
            
            embed = discord.Embed(
                title="✅ Inactivity Hours Updated",
                description=f"Threads will be checked after **{hours} hours** of inactivity.",
                color=discord.Color.green()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number!",
                ephemeral=True
            )


class ConfirmCloseView(discord.ui.View):
    def __init__(self, bot, thread, creator_id, thanked_helpers):
        super().__init__(timeout=120)
        self.bot = bot
        self.thread = thread
        self.creator_id = creator_id
        self.thanked_helpers = thanked_helpers
    
    @discord.ui.button(label="Yes, Close Thread", style=discord.ButtonStyle.danger, emoji="🔒")
    async def confirm_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message(
                "❌ Only the thread creator can close this thread!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        embed = discord.Embed(
            title="🔒 Thread Closed",
            description="This help thread has been closed and archived.",
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        
        if self.thanked_helpers:
            thanked_mentions = ", ".join(f"<@{hid}>" for hid in self.thanked_helpers)
            embed.add_field(name="🙏 Helpers Thanked", value=thanked_mentions, inline=False)
        
        embed.add_field(name="Thread Creator", value=f"<@{self.creator_id}>", inline=True)
        embed.add_field(name="Closed By", value=interaction.user.mention, inline=True)
        
        await interaction.followup.send(embed=embed)
        
        try:
            await asyncio.sleep(2)
            await self.thread.edit(archived=True, locked=True)
            
            cog = self.bot.get_cog('ThreadManager')
            if cog:
                cog.log_thread_closure(
                    interaction.guild.id,
                    self.thread.id,
                    self.creator_id,
                    interaction.user.id,
                    list(self.thanked_helpers)
                )
            
            logger.info(f"Thread {self.thread.id} closed in guild {interaction.guild.id}")
        except Exception as e:
            logger.error(f"Error closing thread {self.thread.id}: {e}")
    
    @discord.ui.button(label="No, Keep Open", style=discord.ButtonStyle.success, emoji="✅")
    async def keep_open(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message(
                "❌ Only the thread creator can make this choice!",
                ephemeral=True
            )
            return
        
        embed = discord.Embed(
            title="✅ Thread Kept Open",
            description="The thread will remain open. You can close it anytime with `/close_thread`.",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed)
        
        cog = self.bot.get_cog('ThreadManager')
        if cog:
            cog.update_thread_activity(self.thread.id)


class ThankHelpersView(discord.ui.View):
    def __init__(self, bot, thread, creator_id, helpers):
        super().__init__(timeout=180)
        self.bot = bot
        self.thread = thread
        self.creator_id = creator_id
        self.helpers = helpers
        self.thanked = set()
        
        if helpers:
            options = [
                discord.SelectOption(
                    label=helper.display_name,
                    value=str(helper.id),
                    description=f"Thank {helper.name} for their help",
                    emoji="🙏"
                )
                for helper in helpers[:25]
            ]
            
            self.helper_select = discord.ui.Select(
                placeholder="Select helpers to thank...",
                options=options,
                min_values=0,
                max_values=min(len(options), 25),
                custom_id="helper_select"
            )
            self.helper_select.callback = self.thank_helpers_callback
            self.add_item(self.helper_select)
    
    async def thank_helpers_callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message(
                "❌ Only the thread creator can thank helpers!",
                ephemeral=True
            )
            return
        
        await interaction.response.defer()
        
        selected_ids = [int(value) for value in self.helper_select.values]
        newly_thanked = []
        
        for helper_id in selected_ids:
            if helper_id not in self.thanked:
                self.thanked.add(helper_id)
                newly_thanked.append(helper_id)
                
                cog = self.bot.get_cog('ThreadManager')
                if cog:
                    cog.add_helper_thanks(interaction.guild.id, helper_id)
        
        if newly_thanked:
            mentions = ", ".join(f"<@{hid}>" for hid in newly_thanked)
            embed = discord.Embed(
                title="🙏 Helpers Thanked",
                description=f"Thanked: {mentions}",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            
            confirm_embed = discord.Embed(
                title="🔒 Close Thread?",
                description="Would you like to close this thread now?",
                color=discord.Color.blue()
            )
            confirm_embed.add_field(name="Thanked Helpers", value=mentions, inline=False)
            confirm_embed.set_footer(text="You can always close the thread later with /close_thread")
            
            confirm_view = ConfirmCloseView(self.bot, self.thread, self.creator_id, self.thanked)
            await interaction.followup.send(embed=confirm_embed, view=confirm_view)
        else:
            await interaction.followup.send("ℹ️ These helpers were already thanked!", ephemeral=True)
    
    @discord.ui.button(label="Skip to Close Options", style=discord.ButtonStyle.secondary, emoji="⏭️", row=2)
    async def skip_to_close(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("❌ Only the thread creator can do this!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        confirm_embed = discord.Embed(
            title="🔒 Close Thread?",
            description="Would you like to close this thread?",
            color=discord.Color.blue()
        )
        
        if self.thanked:
            mentions = ", ".join(f"<@{hid}>" for hid in self.thanked)
            confirm_embed.add_field(name="Previously Thanked", value=mentions, inline=False)
        
        confirm_embed.set_footer(text="You can always close the thread later with /close_thread")
        
        confirm_view = ConfirmCloseView(self.bot, self.thread, self.creator_id, self.thanked)
        await interaction.followup.send(embed=confirm_embed, view=confirm_view)
    
    @discord.ui.button(label="Cancel", style=discord.ButtonStyle.danger, emoji="❌", row=2)
    async def cancel_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("❌ Only the thread creator can cancel!", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="❌ Cancelled",
            description="Thread closure cancelled. Use `/close_thread` when you're ready to close.",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class InactivityView(discord.ui.View):
    def __init__(self, bot, thread, creator_id, helpers):
        super().__init__(timeout=172800)
        self.bot = bot
        self.thread = thread
        self.creator_id = creator_id
        self.helpers = helpers
    
    @discord.ui.button(label="Close Thread", style=discord.ButtonStyle.danger, emoji="🔒")
    async def close_inactive_thread(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("❌ Only the thread creator can close this thread!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        if self.helpers:
            embed = discord.Embed(
                title="🙏 Thank Helpers First?",
                description="Would you like to thank any helpers before closing?",
                color=discord.Color.blue()
            )
            
            helper_list = "\n".join([f"• {h.mention}" for h in self.helpers[:10]])
            embed.add_field(name="Helpers in Thread", value=helper_list, inline=False)
            
            thank_view = ThankHelpersView(self.bot, self.thread, self.creator_id, self.helpers)
            await interaction.followup.send(embed=embed, view=thank_view)
        else:
            embed = discord.Embed(
                title="🔒 Inactive Thread Closed",
                description="This thread was closed due to inactivity.",
                color=discord.Color.red(),
                timestamp=datetime.now()
            )
            
            await interaction.followup.send(embed=embed)
            
            try:
                await asyncio.sleep(2)
                await self.thread.edit(archived=True, locked=True)
                logger.info(f"Inactive thread {self.thread.id} closed in guild {interaction.guild.id}")
            except Exception as e:
                logger.error(f"Error closing inactive thread {self.thread.id}: {e}")
    
    @discord.ui.button(label="I Still Need Help", style=discord.ButtonStyle.success, emoji="🆘")
    async def request_more_help(self, interaction: discord.Interaction, button: discord.ui.Button):
        if interaction.user.id != self.creator_id:
            await interaction.response.send_message("❌ Only the thread creator can request help!", ephemeral=True)
            return
        
        await interaction.response.defer()
        
        helper_mentions = " ".join(f"<@{h.id}>" for h in self.helpers) if self.helpers else "No previous helpers"
        
        embed = discord.Embed(
            title="🆘 Help Requested",
            description=f"{interaction.user.mention} still needs help!",
            color=discord.Color.green(),
            timestamp=datetime.now()
        )
        
        if self.helpers:
            embed.add_field(name="Previous Helpers Notified", value=helper_mentions, inline=False)
        
        await interaction.followup.send(embed=embed)
        
        cog = self.bot.get_cog('ThreadManager')
        if cog:
            cog.update_thread_activity(self.thread.id)


class ThreadManager(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_path = self.get_data_path()
        self.thread_activity = {}
        self.inactivity_hours = 48
        self.check_inactive_threads.start()
    
    def cog_unload(self):
        self.check_inactive_threads.cancel()
    
    def get_data_path(self):
        """Get path for help system data"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            data_dir = os.path.join(project_root, "data", "help_system")
        except:
            data_dir = os.path.join("data", "help_system")
        
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    
    def load_guild_config(self, guild_id):
        """Load guild configuration for thread management"""
        try:
            file_path = os.path.join(self.data_path, f"{guild_id}_thread_config.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading thread config for guild {guild_id}: {e}")
        
        return {
            'enabled': False,
            'forum_channels': [],
            'inactivity_hours': 48
        }
    
    def save_guild_config(self, guild_id, config):
        """Save guild configuration"""
        try:
            file_path = os.path.join(self.data_path, f"{guild_id}_thread_config.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved thread config for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error saving thread config for guild {guild_id}: {e}")
    
    def is_monitored_channel(self, guild_id, channel_id):
        """Check if a forum channel is being monitored"""
        config = self.load_guild_config(guild_id)
        return config.get('enabled', False) and channel_id in config.get('forum_channels', [])
    
    def load_helper_stats(self, guild_id):
        """Load helper statistics"""
        try:
            file_path = os.path.join(self.data_path, f"{guild_id}_helper_stats.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading helper stats for guild {guild_id}: {e}")
        
        return {}
    
    def save_helper_stats(self, guild_id, stats):
        """Save helper statistics"""
        try:
            file_path = os.path.join(self.data_path, f"{guild_id}_helper_stats.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving helper stats for guild {guild_id}: {e}")
    
    def add_helper_thanks(self, guild_id, helper_id):
        """Add a thank to a helper's stats"""
        stats = self.load_helper_stats(guild_id)
        helper_key = str(helper_id)
        
        if helper_key not in stats:
            stats[helper_key] = {
                'total_thanks': 0,
                'weekly_thanks': 0,
                'last_reset': datetime.now().isoformat()
            }
        
        stats[helper_key]['total_thanks'] += 1
        stats[helper_key]['weekly_thanks'] += 1
        stats[helper_key]['last_thank'] = datetime.now().isoformat()
        
        self.save_helper_stats(guild_id, stats)
        logger.info(f"Added thank for helper {helper_id} in guild {guild_id}")
    
    def log_thread_closure(self, guild_id, thread_id, creator_id, closer_id, thanked_helpers):
        """Log thread closure for analytics"""
        try:
            file_path = os.path.join(self.data_path, f"{guild_id}_closures.json")
            
            closures = []
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    closures = json.load(f)
            
            closures.append({
                'thread_id': thread_id,
                'creator_id': creator_id,
                'closed_by': closer_id,
                'thanked_helpers': thanked_helpers,
                'closed_at': datetime.now().isoformat()
            })
            
            closures = closures[-1000:]
            
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(closures, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error logging thread closure: {e}")
    
    def update_thread_activity(self, thread_id):
        """Update thread activity timestamp"""
        self.thread_activity[thread_id] = datetime.now()
    
    async def get_thread_helpers(self, thread):
        """Get list of unique helpers in a thread"""
        helpers = []
        creator = thread.owner
        
        try:
            async for message in thread.history(limit=100):
                if message.author.bot or message.author == creator:
                    continue
                
                if message.author not in helpers:
                    helpers.append(message.author)
        except Exception as e:
            logger.error(f"Error fetching thread helpers for thread {thread.id}: {e}")
        
        return helpers
    
    @tasks.loop(minutes=30)
    async def check_inactive_threads(self):
        """Check for inactive threads and prompt closure"""
        try:
            for guild in self.bot.guilds:
                config = self.load_guild_config(guild.id)
                
                if not config.get('enabled', False):
                    continue
                
                monitored_channels = config.get('forum_channels', [])
                if not monitored_channels:
                    continue
                
                inactivity_hours = config.get('inactivity_hours', self.inactivity_hours)
                
                for channel in guild.channels:
                    if channel.type == discord.ChannelType.forum and channel.id in monitored_channels:
                        try:
                            active_threads = channel.threads
                            
                            for thread in active_threads:
                                if thread.archived:
                                    continue
                                
                                last_message = None
                                try:
                                    async for msg in thread.history(limit=1):
                                        last_message = msg
                                        break
                                except:
                                    continue
                                
                                if not last_message:
                                    continue
                                
                                time_since_last = datetime.now(last_message.created_at.tzinfo) - last_message.created_at
                                hours_inactive = time_since_last.total_seconds() / 3600
                                
                                if hours_inactive >= inactivity_hours:
                                    if thread.id in self.thread_activity:
                                        last_check = self.thread_activity[thread.id]
                                        if (datetime.now() - last_check).total_seconds() < 86400:
                                            continue
                                    
                                    creator = thread.owner
                                    if not creator:
                                        continue
                                    
                                    helpers = await self.get_thread_helpers(thread)
                                    
                                    embed = discord.Embed(
                                        title="⏰ Thread Inactivity Notice",
                                        description=f"{creator.mention}, this thread has been inactive for {int(hours_inactive)} hours.\n\nWould you like to close it, or do you still need help?",
                                        color=discord.Color.orange(),
                                        timestamp=datetime.now()
                                    )
                                    
                                    view = InactivityView(self.bot, thread, creator.id, helpers)
                                    
                                    await thread.send(embed=embed, view=view)
                                    self.thread_activity[thread.id] = datetime.now()
                                    
                                    logger.info(f"Sent inactivity notice for thread {thread.id} in guild {guild.id}")
                                    
                        except Exception as e:
                            logger.error(f"Error checking forum channel {channel.id}: {e}")
        except Exception as e:
            logger.error(f"Error in inactive thread checker: {e}")
    
    @check_inactive_threads.before_loop
    async def before_check_inactive(self):
        await self.bot.wait_until_ready()
    
    @commands.hybrid_command(name="setup_thread_manager", description="Configure thread management settings")
    @app_commands.default_permissions(manage_guild=True)
    async def setup_thread_manager(self, ctx: commands.Context):
        """Single command to configure all thread manager settings"""
        
        config = self.load_guild_config(ctx.guild.id)
        
        embed = discord.Embed(
            title="🔧 Thread Manager Setup",
            description="Configure automatic thread management and inactivity monitoring using the controls below.",
            color=discord.Color.blue()
        )
        
        status_emoji = "✅" if config.get('enabled') else "❌"
        embed.add_field(name="Status", value=f"{status_emoji} {'Enabled' if config.get('enabled') else 'Disabled'}", inline=True)
        embed.add_field(name="Inactivity Timeout", value=f"⏰ {config.get('inactivity_hours', 48)} hours", inline=True)
        
        monitored = config.get('forum_channels', [])
        if monitored:
            channel_list = "\n".join([f"• <#{cid}>" for cid in monitored[:5]])
            if len(monitored) > 5:
                channel_list += f"\n... and {len(monitored) - 5} more"
            embed.add_field(name=f"Monitored Channels ({len(monitored)})", value=channel_list, inline=False)
        else:
            embed.add_field(name="Monitored Channels", value="None selected", inline=False)
        
        embed.add_field(
            name="💡 How to Use",
            value="• **Channel Select**: Choose forum channels to monitor\n• **Set Inactivity Hours**: Configure timeout duration\n• **Toggle**: Enable/disable the system\n• **View Settings**: See current configuration",
            inline=False
        )
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        view = ThreadManagerSetupView(self.bot, ctx.guild.id)
        await ctx.send(embed=embed, view=view)
    
    @commands.hybrid_command(name="close_thread", description="Close this help thread and thank helpers")
    async def close_thread(self, ctx: commands.Context):
        """Close a help thread with option to thank helpers"""
        
        if not isinstance(ctx.channel, discord.Thread):
            embed = discord.Embed(
                title="❌ Invalid Channel",
                description="This command can only be used in threads!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        thread = ctx.channel
        
        if thread.parent and thread.parent.type == discord.ChannelType.forum:
            if not self.is_monitored_channel(ctx.guild.id, thread.parent.id):
                embed = discord.Embed(
                    title="ℹ️ Not Monitored",
                    description="This forum channel is not set up for thread management. Ask an admin to add it with `/setup_thread_manager`.",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed, ephemeral=True)
                return
        
        creator = thread.owner
        
        if ctx.author != creator and not ctx.author.guild_permissions.manage_threads:
            embed = discord.Embed(
                title="❌ Permission Denied",
                description="Only the thread creator or staff can close threads!",
                color=discord.Color.red()
            )
            await ctx.send(embed=embed, ephemeral=True)
            return
        
        helpers = await self.get_thread_helpers(thread)
        
        embed = discord.Embed(
            title="🔒 Close Help Thread",
            description="Select helpers to thank before proceeding to close options.",
            color=discord.Color.blue()
        )
        
        if helpers:
            helper_list = "\n".join([f"• {h.mention}" for h in helpers[:10]])
            embed.add_field(name="Helpers in this thread", value=helper_list, inline=False)
            embed.add_field(
                name="💡 How to use",
                value="1. Select helpers from the dropdown to thank them\n2. After thanking, you'll be asked if you want to close\n3. Or click 'Skip to Close Options' to proceed directly",
                inline=False
            )
        else:
            embed.add_field(name="ℹ️ No Helpers Found", value="No other users participated in this thread.", inline=False)
        
        embed.set_footer(text=f"Requested by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)
        
        view = ThankHelpersView(self.bot, thread, creator.id, helpers)
        await ctx.send(embed=embed, view=view)
    
    @commands.hybrid_command(name="helper_stats", description="View helper statistics and rankings")
    @app_commands.describe(user="The user to view stats for (optional)")
    async def helper_stats(self, ctx: commands.Context, user: discord.Member = None):
        """View helper statistics"""
        
        stats = self.load_helper_stats(ctx.guild.id)
        
        if user:
            user_key = str(user.id)
            if user_key not in stats:
                embed = discord.Embed(
                    title="📊 Helper Statistics",
                    description=f"{user.mention} has no recorded helper activity yet!",
                    color=discord.Color.blue()
                )
                await ctx.send(embed=embed)
                return
            
            user_stats = stats[user_key]
            
            embed = discord.Embed(
                title=f"📊 Helper Statistics - {user.display_name}",
                color=discord.Color.blue(),
                timestamp=datetime.now()
            )
            embed.set_thumbnail(url=user.display_avatar.url)
            embed.add_field(name="Total Thanks", value=f"🙏 {user_stats.get('total_thanks', 0)}", inline=True)
            embed.add_field(name="This Week", value=f"📅 {user_stats.get('weekly_thanks', 0)}", inline=True)
            
            if 'last_thank' in user_stats:
                last_thank = datetime.fromisoformat(user_stats['last_thank'])
                embed.add_field(name="Last Thanked", value=f"<t:{int(last_thank.timestamp())}:R>", inline=False)
            
            await ctx.send(embed=embed)
        else:
            sorted_helpers = sorted(
                stats.items(),
                key=lambda x: x[1].get('weekly_thanks', 0),
                reverse=True
            )[:10]
            
            embed = discord.Embed(
                title="🏆 Helper Leaderboard - This Week",
                description="Top 10 most thanked helpers this week",
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            if sorted_helpers:
                leaderboard_text = ""
                medals = ["🥇", "🥈", "🥉"]
                
                for idx, (helper_id, helper_stats) in enumerate(sorted_helpers, 1):
                    medal = medals[idx-1] if idx <= 3 else f"`{idx}.`"
                    weekly_thanks = helper_stats.get('weekly_thanks', 0)
                    total_thanks = helper_stats.get('total_thanks', 0)
                    leaderboard_text += f"{medal} <@{helper_id}> - **{weekly_thanks}** this week ({total_thanks} total)\n"
                
                embed.add_field(name="Rankings", value=leaderboard_text, inline=False)
            else:
                embed.description = "No helper statistics recorded yet!"
            
            await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(ThreadManager(bot))

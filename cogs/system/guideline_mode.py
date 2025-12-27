import discord
from discord.ext import commands
from discord import app_commands
import json
import os
import asyncio
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)


class GuidelinesModal(discord.ui.Modal):
    def __init__(self, current_message=""):
        super().__init__(title="Set Guidelines Message")
        
        self.guidelines_input = discord.ui.TextInput(
            label="Guidelines Message",
            placeholder="Enter your guidelines message here...",
            default=current_message,
            style=discord.TextStyle.paragraph,
            max_length=2000,
            required=True
        )
        self.add_item(self.guidelines_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        self.guidelines_message = self.guidelines_input.value
        embed = discord.Embed(
            title="✅ Guidelines Message Set",
            description="Your guidelines message has been saved!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class EmbedCustomizationModal(discord.ui.Modal):
    def __init__(self, parent_view, current_settings):
        super().__init__(title="Embed Customization")
        self.parent_view = parent_view
        
        self.title_input = discord.ui.TextInput(
            label="Embed Title",
            placeholder="Enter embed title (e.g., Guidelines)",
            default=current_settings.get('embed_title', '📋 Guidelines'),
            style=discord.TextStyle.short,
            max_length=256,
            required=True
        )
        self.add_item(self.title_input)
        
        self.color_input = discord.ui.TextInput(
            label="Embed Color (Hex)",
            placeholder="Enter hex color (e.g., #3498db or 3498db)",
            default=current_settings.get('embed_color', '#3498db'),
            style=discord.TextStyle.short,
            max_length=7,
            required=False
        )
        self.add_item(self.color_input)
        
        self.footer_input = discord.ui.TextInput(
            label="Embed Footer",
            placeholder="Enter footer text (optional)",
            default=current_settings.get('embed_footer', 'Automatic guidelines message'),
            style=discord.TextStyle.short,
            max_length=2048,
            required=False
        )
        self.add_item(self.footer_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        color_value = self.color_input.value.strip()
        if color_value.startswith('#'):
            color_value = color_value[1:]
        
        try:
            int(color_value, 16)
            self.parent_view.embed_color = color_value
        except ValueError:
            self.parent_view.embed_color = "3498db"
        
        self.parent_view.embed_title = self.title_input.value
        self.parent_view.embed_footer = self.footer_input.value
        
        embed = discord.Embed(
            title="✅ Embed Customization Saved",
            description=f"**Title:** {self.title_input.value}\n**Color:** #{color_value}\n**Footer:** {self.footer_input.value or 'None'}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class GuidelinesSettingsView(discord.ui.View):
    def __init__(self, bot, guild_id):
        super().__init__(timeout=300)
        self.bot = bot
        self.guild_id = guild_id
        self.selected_type = None
        self.selected_channel = None
        self.selected_mode = None
        self.guidelines_message = ""
        self.message_type = "embed"
        self.embed_title = "📋 Guidelines"
        self.embed_color = "3498db"
        self.embed_footer = "Automatic guidelines message"
        
        # Add initial components
        self.setup_components()
        self.setup_buttons()
    
    def setup_components(self):
        """Setup all UI components"""
        # Row 0: Message type select
        message_type_select = discord.ui.Select(
            placeholder="Choose message type (Embed/Plain)...",
            options=[
                discord.SelectOption(
                    label="Embed Message",
                    description="Send as a rich embed (recommended)",
                    value="embed",
                    emoji="📋",
                    default=True
                ),
                discord.SelectOption(
                    label="Plain Text Message",
                    description="Send as plain text",
                    value="plain",
                    emoji="📝"
                )
            ]
        )
        message_type_select.callback = self.message_type_callback
        self.add_item(message_type_select)
        
        # Row 1: Channel type select
        channel_type_select = discord.ui.Select(
            placeholder="Choose channel type (Forum/Text)...",
            options=[
                discord.SelectOption(
                    label="Forum Channel",
                    description="Auto-send in forum threads",
                    value="forum",
                    emoji="📋"
                ),
                discord.SelectOption(
                    label="Text Channel",
                    description="Send in regular text channels",
                    value="text",
                    emoji="💬"
                )
            ]
        )
        channel_type_select.callback = self.channel_type_callback
        self.add_item(channel_type_select)
        
        # Row 2: Send mode select
        send_mode_select = discord.ui.Select(
            placeholder="Choose send mode...",
            options=[
                discord.SelectOption(
                    label="Thread Creation Only",
                    description="Only on new forum thread creation",
                    value="thread_creation",
                    emoji="🧵"
                ),
                discord.SelectOption(
                    label="After Every Message",
                    description="Send after every new message",
                    value="every_message",
                    emoji="📝"
                ),
                discord.SelectOption(
                    label="Once Per Day",
                    description="Send once per day maximum",
                    value="once_daily",
                    emoji="📅"
                ),
                discord.SelectOption(
                    label="Once Per User",
                    description="Send once per user",
                    value="once_per_user",
                    emoji="👤"
                )
            ]
        )
        send_mode_select.callback = self.send_mode_callback
        self.add_item(send_mode_select)
    
    def setup_buttons(self):
        """Setup all buttons"""
        set_guidelines_btn = discord.ui.Button(label="Set Guidelines", style=discord.ButtonStyle.primary, emoji="✏️")
        set_guidelines_btn.callback = self.set_message_button
        self.add_item(set_guidelines_btn)
        
        customize_btn = discord.ui.Button(label="Customize Embed", style=discord.ButtonStyle.primary, emoji="🎨")
        customize_btn.callback = self.customize_embed_button
        self.add_item(customize_btn)
        
        preview_btn = discord.ui.Button(label="Preview", style=discord.ButtonStyle.secondary, emoji="👁️")
        preview_btn.callback = self.preview_message_button
        self.add_item(preview_btn)
        
        save_btn = discord.ui.Button(label="Save", style=discord.ButtonStyle.success, emoji="💾")
        save_btn.callback = self.save_settings
        self.add_item(save_btn)
        
        disable_btn = discord.ui.Button(label="Disable", style=discord.ButtonStyle.danger, emoji="❌")
        disable_btn.callback = self.disable_guidelines
        self.add_item(disable_btn)
    
    async def message_type_callback(self, interaction: discord.Interaction):
        select = [item for item in self.children if isinstance(item, discord.ui.Select) and item.placeholder and "message type" in item.placeholder.lower()][0]
        self.message_type = select.values[0]
        
        embed = discord.Embed(
            title="✅ Message Type Selected",
            description=f"Selected: **{select.values[0].title()} Message**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def channel_type_callback(self, interaction: discord.Interaction):
        select = [item for item in self.children if isinstance(item, discord.ui.Select) and item.placeholder and "channel type" in item.placeholder.lower()][0]
        self.selected_type = select.values[0]
        
        # Remove existing channel selector if present
        for item in self.children[:]:
            if isinstance(item, discord.ui.ChannelSelect):
                self.remove_item(item)
        
        # Add appropriate channel selector based on type
        if self.selected_type == "forum":
            channel_types = [discord.ChannelType.forum]
            placeholder_text = "Select a forum channel..."
        else:
            channel_types = [discord.ChannelType.text]
            placeholder_text = "Select a text channel..."
        
        channel_selector = discord.ui.ChannelSelect(
            placeholder=placeholder_text,
            channel_types=channel_types,
            min_values=1,
            max_values=1
        )
        channel_selector.callback = self.channel_select_callback
        self.add_item(channel_selector)
        
        embed = discord.Embed(
            title="✅ Channel Type Selected",
            description=f"Selected: **{select.values[0].title()} Channel**\n\nNow select the specific channel from the dropdown below.",
            color=discord.Color.green()
        )
        await interaction.response.edit_message(view=self)
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    async def channel_select_callback(self, interaction: discord.Interaction):
        channel_selector = [item for item in self.children if isinstance(item, discord.ui.ChannelSelect)][0]
        self.selected_channel = channel_selector.values[0]
        
        embed = discord.Embed(
            title="✅ Channel Selected",
            description=f"Selected channel: {self.selected_channel.mention}",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def send_mode_callback(self, interaction: discord.Interaction):
        select = [item for item in self.children if isinstance(item, discord.ui.Select) and item.placeholder and "send mode" in item.placeholder.lower()][0]
        self.selected_mode = select.values[0]
        
        embed = discord.Embed(
            title="✅ Send Mode Selected",
            description=f"Selected: **{select.values[0].replace('_', ' ').title()}**",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    async def set_message_button(self, interaction: discord.Interaction):
        current_data = self.bot.get_cog('HelpSystem').load_guild_settings(self.guild_id)
        current_message = current_data.get('guidelines_message', '')
        
        modal = GuidelinesModal(current_message)
        await interaction.response.send_modal(modal)
        await modal.wait()
        
        if hasattr(modal, 'guidelines_message'):
            self.guidelines_message = modal.guidelines_message
    
    async def customize_embed_button(self, interaction: discord.Interaction):
        if self.message_type != "embed":
            await interaction.response.send_message(
                "❌ Embed customization is only available for Embed message type!",
                ephemeral=True
            )
            return
        
        current_data = self.bot.get_cog('HelpSystem').load_guild_settings(self.guild_id)
        modal = EmbedCustomizationModal(self, current_data)
        await interaction.response.send_modal(modal)
    
    async def preview_message_button(self, interaction: discord.Interaction):
        if not self.guidelines_message:
            await interaction.response.send_message(
                "❌ Please set a guidelines message first using the 'Set Guidelines' button!",
                ephemeral=True
            )
            return
        
        if self.message_type == "embed":
            try:
                color_int = int(self.embed_color, 16)
            except:
                color_int = 0x3498db
            
            preview_embed = discord.Embed(
                title=self.embed_title,
                description=self.guidelines_message,
                color=discord.Color(color_int),
                timestamp=datetime.now()
            )
            if self.embed_footer:
                preview_embed.set_footer(text=self.embed_footer)
            
            await interaction.response.send_message("**Preview:**", embed=preview_embed, ephemeral=True)
        else:
            await interaction.response.send_message(
                f"**Preview (Plain Text):**\n\n{self.guidelines_message}",
                ephemeral=True
            )
    
    async def save_settings(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        # Validation
        missing = []
        if not self.selected_type:
            missing.append("Channel Type")
        if not self.selected_channel:
            missing.append("Target Channel")
        if not self.selected_mode:
            missing.append("Send Mode")
        if not self.guidelines_message:
            missing.append("Guidelines Message")
        
        if missing:
            embed = discord.Embed(
                title="❌ Missing Required Settings",
                description=f"Please configure: **{', '.join(missing)}**",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Get the actual channel object from the guild
        actual_channel = interaction.guild.get_channel(self.selected_channel.id)
        if not actual_channel:
            embed = discord.Embed(
                title="❌ Channel Not Found",
                description="Could not find the selected channel!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Validate channel type matches selection
        if self.selected_type == "forum" and actual_channel.type != discord.ChannelType.forum:
            embed = discord.Embed(
                title="❌ Channel Type Mismatch",
                description="You selected Forum Channel type but chose a non-forum channel!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        if self.selected_type == "text" and actual_channel.type != discord.ChannelType.text:
            embed = discord.Embed(
                title="❌ Channel Type Mismatch",
                description="You selected Text Channel type but chose a non-text channel!",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        # Check bot permissions
        bot_member = interaction.guild.get_member(self.bot.user.id)
        permissions = actual_channel.permissions_for(bot_member)
        
        help_system = self.bot.get_cog('HelpSystem')
        settings = {
            'channel_type': self.selected_type,
            'channel_id': self.selected_channel.id,
            'send_mode': self.selected_mode,
            'guidelines_message': self.guidelines_message,
            'message_type': self.message_type,
            'embed_title': self.embed_title,
            'embed_color': self.embed_color,
            'embed_footer': self.embed_footer,
            'enabled': True,
            'last_sent': None,
            'sent_users': []
        }
        
        help_system.save_guild_settings(self.guild_id, settings)
        
        embed = discord.Embed(
            title="✅ Guidelines System Configured",
            description="All settings have been saved successfully!",
            color=discord.Color.green()
        )
        embed.add_field(
            name="📋 Configuration Summary",
            value=f"**Type:** {self.selected_type.title()}\n**Channel:** {actual_channel.mention}\n**Mode:** {self.selected_mode.replace('_', ' ').title()}\n**Format:** {self.message_type.title()}",
            inline=False
        )
        
        if not permissions.send_messages:
            embed.add_field(
                name="⚠️ Permission Warning",
                value="Bot doesn't have `Send Messages` permission in the selected channel!",
                inline=False
            )
            embed.color = discord.Color.orange()
        
        if self.guidelines_message:
            preview = self.guidelines_message[:150] + ("..." if len(self.guidelines_message) > 150 else "")
            embed.add_field(name="📝 Message Preview", value=preview, inline=False)
        
        await interaction.followup.send(embed=embed)
        
        # Disable the view after saving
        for item in self.children:
            item.disabled = True
        await interaction.message.edit(view=self)
    
    async def disable_guidelines(self, interaction: discord.Interaction):
        await interaction.response.defer()
        
        help_system = self.bot.get_cog('HelpSystem')
        settings = help_system.load_guild_settings(self.guild_id)
        
        if not settings.get('enabled'):
            embed = discord.Embed(
                title="ℹ️ Already Disabled",
                description="Guidelines system is already disabled for this server.",
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=embed, ephemeral=True)
            return
        
        settings['enabled'] = False
        help_system.save_guild_settings(self.guild_id, settings)
        
        embed = discord.Embed(
            title="❌ Guidelines System Disabled",
            description="Automatic guidelines messages have been disabled for this server.",
            color=discord.Color.red()
        )
        await interaction.followup.send(embed=embed)


class HelpSystem(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.data_path = self.get_data_path()
    
    def get_data_path(self):
        """Get path for guild settings data"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            data_dir = os.path.join(project_root, "data", "help_system")
        except:
            data_dir = os.path.join("data", "help_system")
        
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    
    def load_guild_settings(self, guild_id):
        """Load guild-specific guidelines settings"""
        try:
            file_path = os.path.join(self.data_path, f"{guild_id}_guidelines.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading guild settings for {guild_id}: {e}")
        
        return {
            'enabled': False,
            'channel_type': None,
            'channel_id': None,
            'send_mode': None,
            'guidelines_message': '',
            'message_type': 'embed',
            'embed_title': '📋 Guidelines',
            'embed_color': '3498db',
            'embed_footer': 'Automatic guidelines message',
            'last_sent': None,
            'sent_users': []
        }
    
    def save_guild_settings(self, guild_id, settings):
        """Save guild-specific guidelines settings"""
        try:
            file_path = os.path.join(self.data_path, f"{guild_id}_guidelines.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved guidelines settings for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error saving guild settings for {guild_id}: {e}")
    
    def check_channel_permissions(self, channel, guild):
        """Check if bot has necessary permissions in channel"""
        bot_member = guild.get_member(self.bot.user.id)
        if not bot_member:
            return False
        
        permissions = channel.permissions_for(bot_member)
        return permissions.send_messages and permissions.view_channel
    
    @commands.hybrid_command(name="set_send_mode", description="Configure automatic guidelines messages")
    @app_commands.default_permissions(manage_guild=True)
    async def set_send_mode(self, ctx: commands.Context):
        """Configure guidelines message settings through an interactive UI"""
        
        view = GuidelinesSettingsView(self.bot, ctx.guild.id)
        current_settings = self.load_guild_settings(ctx.guild.id)
        
        embed = discord.Embed(
            title="📝 Guidelines System Setup",
            description="Configure automatic guidelines messages for your server using the interactive controls below.",
            color=discord.Color.blue()
        )
        
        if current_settings.get('enabled'):
            channel_obj = self.bot.get_channel(current_settings.get('channel_id'))
            channel_name = channel_obj.mention if channel_obj else "Unknown Channel"
            
            embed.add_field(
                name="📊 Current Configuration",
                value=f"**Status:** ✅ Enabled\n**Channel:** {channel_name}\n**Mode:** {current_settings.get('send_mode', 'Not set').replace('_', ' ').title()}\n**Format:** {current_settings.get('message_type', 'embed').title()}",
                inline=False
            )
            
            if channel_obj and not self.check_channel_permissions(channel_obj, ctx.guild):
                embed.add_field(
                    name="⚠️ Permission Issue",
                    value="Bot lacks permissions in the configured channel!",
                    inline=False
                )
        else:
            embed.add_field(
                name="📊 Current Status",
                value="❌ **Disabled**\n\nUse the controls below to set up the guidelines system.",
                inline=False
            )
        
        embed.add_field(
            name="🔧 Setup Instructions",
            value="1️⃣ Choose message type (Embed/Plain)\n2️⃣ Select channel type (Forum/Text)\n3️⃣ Pick the specific channel\n4️⃣ Choose send mode\n5️⃣ Set guidelines message\n6️⃣ Customize (optional)\n7️⃣ Preview and Save",
            inline=False
        )
        embed.set_footer(
            text=f"Requested by {ctx.author.display_name}",
            icon_url=ctx.author.display_avatar.url
        )
        
        await ctx.send(embed=embed, view=view)
    
    @commands.Cog.listener()
    async def on_thread_create(self, thread):
        """Handle new forum thread creation"""
        if not thread.guild or thread.parent.type != discord.ChannelType.forum:
            return
        
        settings = self.load_guild_settings(thread.guild.id)
        
        if not settings.get('enabled') or settings.get('channel_type') != 'forum':
            return
        
        if settings.get('channel_id') != thread.parent.id:
            return
        
        if not settings.get('guidelines_message'):
            return
        
        if not self.check_channel_permissions(thread, thread.guild):
            logger.warning(f"Bot lacks permissions to send in forum thread {thread.id}")
            return
        
        try:
            await asyncio.sleep(1)
            
            if settings.get('message_type') == 'embed':
                try:
                    color_int = int(settings.get('embed_color', '3498db'), 16)
                except:
                    color_int = 0x3498db
                
                embed = discord.Embed(
                    title=settings.get('embed_title', '📋 Guidelines'),
                    description=settings['guidelines_message'],
                    color=discord.Color(color_int),
                    timestamp=datetime.now()
                )
                if settings.get('embed_footer'):
                    embed.set_footer(text=settings['embed_footer'])
                
                await thread.send(embed=embed)
            else:
                await thread.send(settings['guidelines_message'])
            
            logger.info(f"Sent guidelines to forum thread {thread.id}")
            
        except discord.Forbidden as e:
            logger.error(f"Permission denied sending guidelines to thread {thread.id}: {e}")
        except Exception as e:
            logger.error(f"Error sending guidelines to thread {thread.id}: {e}")
    
    @commands.Cog.listener()
    async def on_message(self, message):
        """Handle messages in text channels based on send mode"""
        if message.author.bot or not message.guild:
            return
        
        settings = self.load_guild_settings(message.guild.id)
        
        if not settings.get('enabled') or settings.get('channel_type') != 'text':
            return
        
        if settings.get('channel_id') != message.channel.id:
            return
        
        if not settings.get('guidelines_message'):
            return
        
        if not self.check_channel_permissions(message.channel, message.guild):
            logger.warning(f"Bot lacks permissions in channel {message.channel.id}")
            return
        
        send_mode = settings.get('send_mode')
        should_send = False
        
        try:
            if send_mode == 'every_message':
                should_send = True
            
            elif send_mode == 'once_daily':
                last_sent = settings.get('last_sent')
                if not last_sent or datetime.fromisoformat(last_sent) < datetime.now() - timedelta(days=1):
                    should_send = True
            
            elif send_mode == 'once_per_user':
                sent_users = settings.get('sent_users', [])
                if str(message.author.id) not in sent_users:
                    should_send = True
                    sent_users.append(str(message.author.id))
                    settings['sent_users'] = sent_users
            
            if should_send:
                if settings.get('message_type') == 'embed':
                    try:
                        color_int = int(settings.get('embed_color', '3498db'), 16)
                    except:
                        color_int = 0x3498db
                    
                    embed = discord.Embed(
                        title=settings.get('embed_title', '📋 Guidelines'),
                        description=settings['guidelines_message'],
                        color=discord.Color(color_int),
                        timestamp=datetime.now()
                    )
                    if settings.get('embed_footer'):
                        embed.set_footer(text=settings['embed_footer'])
                    
                    await message.channel.send(embed=embed)
                else:
                    await message.channel.send(settings['guidelines_message'])
                
                settings['last_sent'] = datetime.now().isoformat()
                self.save_guild_settings(message.guild.id, settings)
                
                logger.info(f"Sent guidelines in channel {message.channel.id}")
                
        except discord.Forbidden as e:
            logger.error(f"Permission denied in channel {message.channel.id}: {e}")
        except Exception as e:
            logger.error(f"Error sending guidelines in channel {message.channel.id}: {e}")


async def setup(bot):
    await bot.add_cog(HelpSystem(bot))

import discord
from discord.ext import commands
from discord import app_commands
from datetime import datetime, timedelta
import logging
import json
import os
from typing import List


logger = logging.getLogger(__name__)


class PremiumLoggingModal(discord.ui.Modal):
    def __init__(self, current_webhook=""):
        super().__init__(title="Premium Logging Settings")
        
        self.webhook_input = discord.ui.TextInput(
            label="Discord Webhook URL (Optional)",
            placeholder="https://discord.com/api/webhooks/...",
            default=current_webhook,
            style=discord.TextStyle.short,
            max_length=200,
            required=False
        )
        self.add_item(self.webhook_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        webhook_url = self.webhook_input.value.strip()
        
        # Validate webhook URL if provided
        if webhook_url and not webhook_url.startswith('https://discord.com/api/webhooks/'):
            embed = discord.Embed(
                title="❌ Invalid Webhook URL",
                description="Please provide a valid Discord webhook URL starting with `https://discord.com/api/webhooks/`",
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return
        
        # Save webhook URL to premium system
        premium_cog = interaction.client.get_cog('Premium')
        if premium_cog:
            premium_cog.save_logging_setting('webhook_url', webhook_url)
        
        embed = discord.Embed(
            title="✅ Logging Settings Saved",
            description="Webhook URL updated successfully!" if webhook_url else "Webhook URL cleared",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


class PremiumLoggingView(discord.ui.View):
    def __init__(self, premium_cog):
        super().__init__(timeout=300)
        self.premium_cog = premium_cog
    
    @discord.ui.select(
        placeholder="Choose events to log...",
        options=[
            discord.SelectOption(
                label="Tier Changes",
                description="Log when premium tiers are modified",
                value="tier_changes",
                emoji="🔄"
            ),
            discord.SelectOption(
                label="Subscription Events",
                description="Log subscription activations/expirations",
                value="subscription_events",
                emoji="💎"
            ),
            discord.SelectOption(
                label="Premium Commands",
                description="Log premium command usage",
                value="premium_commands",
                emoji="⚡"
            ),
            discord.SelectOption(
                label="System Events",
                description="Log premium system startup/errors",
                value="system_events",
                emoji="🖥️"
            ),
            discord.SelectOption(
                label="Access Attempts",
                description="Log attempts to access premium features",
                value="access_attempts",
                emoji="🚪"
            )
        ],
        min_values=0,
        max_values=5,
        row=0
    )
    async def log_events_select(self, interaction: discord.Interaction, select: discord.ui.Select):
        selected_events = select.values
        self.premium_cog.save_logging_setting('log_events', selected_events)
        
        if selected_events:
            events_list = "• " + "\n• ".join([
                "Tier Changes" if e == "tier_changes" else
                "Subscription Events" if e == "subscription_events" else
                "Premium Commands" if e == "premium_commands" else
                "System Events" if e == "system_events" else
                "Access Attempts" for e in selected_events
            ])
            embed = discord.Embed(
                title="✅ Log Events Updated",
                description=f"**Selected Events:**\n{events_list}",
                color=discord.Color.green()
            )
        else:
            embed = discord.Embed(
                title="ℹ️ No Events Selected",
                description="Premium logging will be disabled",
                color=discord.Color.orange()
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="Webhook Settings", style=discord.ButtonStyle.secondary, emoji="📝", row=1)
    async def webhook_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        current_webhook = self.premium_cog.get_logging_setting('webhook_url', '')
        modal = PremiumLoggingModal(current_webhook)
        await interaction.response.send_modal(modal)
    
    @discord.ui.button(label="Test Logging", style=discord.ButtonStyle.primary, emoji="🧪", row=1)
    async def test_logging(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.premium_cog.log_event(
            "system_events",
            f"Premium logging test by {interaction.user.display_name}",
            interaction.user,
            {"Test": "Success", "Timestamp": datetime.now().isoformat()}
        )
        
        embed = discord.Embed(
            title="✅ Test Log Sent",
            description="Check your log channel or webhook for the test message!",
            color=discord.Color.green()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
    
    @discord.ui.button(label="View Settings", style=discord.ButtonStyle.success, emoji="👁️", row=1)
    async def view_settings(self, interaction: discord.Interaction, button: discord.ui.Button):
        settings = self.premium_cog.load_logging_settings()
        
        embed = discord.Embed(
            title="📊 Premium Logging Settings",
            description="Current logging configuration",
            color=discord.Color.blue()
        )
        
        log_events = settings.get('log_events', [])
        embed.add_field(
            name="📝 Tracked Events",
            value=f"{len(log_events)} event types" if log_events else "No events selected",
            inline=True
        )
        
        log_channel_id = settings.get('log_channel_id')
        if log_channel_id:
            channel = interaction.guild.get_channel(log_channel_id)
            embed.add_field(
                name="📄 Log Channel",
                value=f"#{channel.name}" if channel else "Unknown Channel",
                inline=True
            )
        
        webhook_url = settings.get('webhook_url', '')
        embed.add_field(
            name="🔗 Webhook",
            value="✅ Configured" if webhook_url else "❌ Not set",
            inline=True
        )
        
        if log_events:
            events_text = "\n".join([f"• {event.replace('_', ' ').title()}" for event in log_events])
            embed.add_field(name="Event Types", value=events_text, inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)


class Premium(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # Initialize premium data on cog startup
        self._sync_premium_data_on_startup()
        # Initialize logging settings
        self.logging_settings = self.load_logging_settings()

    def get_owner_id(self):
        """Safely get the owner ID from various sources"""
        if hasattr(self.bot, 'owner_id') and self.bot.owner_id:
            try:
                return int(self.bot.owner_id)
            except (ValueError, TypeError):
                pass
        try:
            from utils.config import OWNER_ID
            return int(OWNER_ID)
        except (ImportError, ValueError, TypeError):
            pass
        return 0  # fallback

    def get_data_path(self, filename: str) -> str:
        """Get absolute path to data file regardless of working directory"""
        try:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            project_root = os.path.dirname(os.path.dirname(current_dir))
            data_dir = os.path.join(project_root, "data")
        except Exception as e:
            logger.warning(f"Path resolution failed: {e}, using fallback")
            data_dir = "data"
        
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, filename)

    def load_logging_settings(self):
        """Load premium logging settings"""
        try:
            file_path = self.get_data_path("premium_logging.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            else:
                logger.info("Creating default premium logging settings")
        except Exception as e:
            logger.error(f"Error loading premium logging settings: {e}")
        
        return {
            "log_events": [],
            "log_channel_id": None,
            "webhook_url": ""
        }
    
    def save_logging_settings(self):
        """Save premium logging settings with error handling"""
        try:
            file_path = self.get_data_path("premium_logging.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.logging_settings, f, indent=2, ensure_ascii=False)
            logger.info("✅ Premium logging settings saved successfully")
        except Exception as e:
            logger.error(f"❌ Error saving premium logging settings: {e}")
    
    def save_logging_setting(self, key: str, value):
        """Save a specific logging setting"""
        self.logging_settings[key] = value
        self.save_logging_settings()
    
    def get_logging_setting(self, key: str, default=None):
        """Get a specific logging setting"""
        return self.logging_settings.get(key, default)

    async def log_event(self, event_type: str, message: str, user=None, additional_data=None):
        """Log premium events to configured channels or webhooks"""
        try:
            # Check if this event type should be logged
            log_events = self.logging_settings.get('log_events', [])
            if event_type not in log_events:
                return
            
            # Create log embed
            embed = discord.Embed(
                title=f"💎 Premium {event_type.replace('_', ' ').title()}",
                description=message,
                color=discord.Color.gold(),
                timestamp=datetime.now()
            )
            
            if user:
                embed.set_author(name=user.display_name, icon_url=user.display_avatar.url)
            
            # Add additional data if provided
            if additional_data:
                for key, value in additional_data.items():
                    embed.add_field(name=key, value=str(value), inline=True)
            
            # Try webhook first
            webhook_url = self.logging_settings.get('webhook_url')
            if webhook_url:
                try:
                    webhook = discord.Webhook.from_url(webhook_url, session=self.bot.session)
                    await webhook.send(embed=embed)
                    return
                except Exception as e:
                    logger.error(f"Failed to send premium webhook log: {e}")
            
            # Fall back to log channel
            log_channel_id = self.logging_settings.get('log_channel_id')
            if log_channel_id:
                # Find the channel in any guild the bot is in
                for guild in self.bot.guilds:
                    channel = guild.get_channel(log_channel_id)
                    if channel:
                        try:
                            await channel.send(embed=embed)
                            return
                        except discord.Forbidden:
                            logger.error(f"No permission to send premium logs in channel {channel.id}")
                        except Exception as e:
                            logger.error(f"Error sending premium log to channel: {e}")
                        break
                        
        except Exception as e:
            logger.error(f"Error logging premium event {event_type}: {e}")


    def load_premium_data(self):
        """Load premium data from JSON file with robust error handling"""
        try:
            file_path = self.get_data_path("premium_data.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if not isinstance(data, dict):
                    raise ValueError("Invalid data format")
                if "subscriptions" not in data:
                    data["subscriptions"] = {}
                logger.info(f"✅ Loaded premium data: {len(data.get('subscriptions', {}))} subscriptions")
                return data
            else:
                logger.info("Creating default premium data structure")
                default_data = {
                    "subscriptions": {},
                    "_instructions": [
                        "Add server subscriptions to the 'subscriptions' object",
                        "Use server ID as the key", 
                        "Set expires_at to null for permanent premium",
                        "Valid tiers: FREE, BASIC, PRO, ULTRA, CUSTOM"
                    ]
                }
                self.save_premium_data(default_data)
                return default_data
        except Exception as e:
            logger.error(f"❌ Error loading premium data: {e}")
            return {"subscriptions": {}, "_instructions": ["Error recovery - default structure"]}

    def save_premium_data(self, data):
        """Enhanced save with better error handling and verification"""
        try:
            file_path = self.get_data_path("premium_data.json")
            temp_path = file_path + ".tmp"
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            # Write to temp file
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())  # Force write to disk
            
            # Atomic replace
            os.replace(temp_path, file_path)
            
            logger.info(f"✅ Premium data saved successfully: {len(data.get('subscriptions', {}))} subscriptions")
            logger.info(f"✅ Saved to: {file_path}")
            
            # Verify the save worked
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    saved_data = json.load(f)
                    logger.info(f"✅ Verification: File contains {len(saved_data.get('subscriptions', {}))} subscriptions")
            
            self._update_bot_premium_state(data)
            
        except PermissionError as e:
            logger.error(f"❌ Permission denied saving premium data: {e}")
            logger.error(f"❌ Attempted path: {file_path}")
        except Exception as e:
            logger.error(f"❌ Error saving premium data: {e}")
            # Clean up temp file if it exists
            temp_path = self.get_data_path("premium_data.json.tmp")
            if os.path.exists(temp_path):
                try:
                    os.remove(temp_path)
                except:
                    pass

    def _update_bot_premium_state(self, data):
        """Update bot's in-memory premium state from saved data"""
        try:
            if hasattr(self.bot, 'premium_guild_ids'):
                self.bot.premium_guild_ids.clear()
            if hasattr(self.bot, 'premium_guild_tiers'):
                self.bot.premium_guild_tiers.clear()
            
            active_count = 0
            for guild_id, sub in data.get("subscriptions", {}).items():
                tier = sub.get("tier", "FREE").lower()
                expires_at = sub.get("expires_at")
                is_active = True
                
                if expires_at and expires_at != "null" and expires_at is not None:
                    try:
                        exp_date = datetime.fromisoformat(expires_at)
                        is_active = datetime.now() <= exp_date
                    except ValueError:
                        pass
                
                if tier != "free" and is_active:
                    if hasattr(self.bot, 'premium_guild_ids'):
                        self.bot.premium_guild_ids.add(guild_id)
                    if hasattr(self.bot, 'premium_guild_tiers'):
                        self.bot.premium_guild_tiers[guild_id] = tier
                    active_count += 1
            
            if hasattr(self.bot, 'save_premium_guilds'):
                self.bot.save_premium_guilds()
            if hasattr(self.bot, 'save_premium_tiers'):
                self.bot.save_premium_tiers()
            
            logger.info(f"✅ Updated bot premium state: {active_count} active premium guilds")
            
        except Exception as e:
            logger.error(f"❌ Error updating bot premium state: {e}")

    def _sync_premium_data_on_startup(self):
        """Sync premium data on cog startup"""
        try:
            data = self.load_premium_data()
            self._update_bot_premium_state(data)
            logger.info("✅ Premium data synced on cog startup")
        except Exception as e:
            logger.error(f"❌ Error syncing premium data on startup: {e}")

    @app_commands.command(name="debug_premium_paths", description="Debug file paths (Owner only)")
    async def debug_premium_paths(self, interaction: discord.Interaction):
        if interaction.user.id != self.get_owner_id():
            await interaction.response.send_message("❌ Owner only command.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🔍 Premium File Paths Debug", color=0x5DADE2)
        
        try:
            # Check current working directory
            cwd = os.getcwd()
            embed.add_field(name="Current Working Dir", value=f"`{cwd}`", inline=False)
            
            # Check file locations
            current_dir = os.path.dirname(os.path.abspath(__file__))
            embed.add_field(name="Cog File Location", value=f"`{current_dir}`", inline=False)
            
            try:
                project_root = os.path.dirname(os.path.dirname(current_dir))
                embed.add_field(name="Calculated Project Root", value=f"`{project_root}`", inline=False)
            except Exception as e:
                embed.add_field(name="Project Root Error", value=f"`{e}`", inline=False)
            
            # Check data paths
            premium_data_path = self.get_data_path("premium_data.json")
            logging_data_path = self.get_data_path("premium_logging.json")
            
            embed.add_field(name="Premium Data Path", value=f"`{premium_data_path}`", inline=False)
            embed.add_field(name="Logging Data Path", value=f"`{logging_data_path}`", inline=False)
            
            # Check if files exist and permissions
            for path, name in [(premium_data_path, "Premium Data"), (logging_data_path, "Logging Data")]:
                exists = os.path.exists(path)
                readable = writable = False
                
                if exists:
                    readable = os.access(path, os.R_OK)
                    writable = os.access(path, os.W_OK)
                    stat = os.stat(path)
                    size = stat.st_size
                    modified = datetime.fromtimestamp(stat.st_mtime)
                    
                    embed.add_field(
                        name=f"{name} Status", 
                        value=f"Exists: ✅\nReadable: {'✅' if readable else '❌'}\nWritable: {'✅' if writable else '❌'}\nSize: {size} bytes\nModified: {modified.strftime('%Y-%m-%d %H:%M:%S')}", 
                        inline=True
                    )
                else:
                    # Check directory permissions
                    dir_path = os.path.dirname(path)
                    dir_exists = os.path.exists(dir_path)
                    dir_writable = os.access(dir_path, os.W_OK) if dir_exists else False
                    
                    embed.add_field(
                        name=f"{name} Status", 
                        value=f"File: ❌ Not Found\nDir Exists: {'✅' if dir_exists else '❌'}\nDir Writable: {'✅' if dir_writable else '❌'}", 
                        inline=True
                    )
                
            # Try to create test file
            try:
                test_path = self.get_data_path("test_write.json")
                with open(test_path, "w") as f:
                    json.dump({"test": "success", "timestamp": datetime.now().isoformat()}, f)
                os.remove(test_path)
                embed.add_field(name="Write Test", value="✅ Success", inline=True)
            except Exception as e:
                embed.add_field(name="Write Test", value=f"❌ Failed: {e}", inline=True)
                
        except Exception as e:
            embed.add_field(name="Debug Error", value=str(e), inline=False)
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="test_premium_save", description="Test premium data saving (Owner only)")
    async def test_premium_save(self, interaction: discord.Interaction):
        if interaction.user.id != self.get_owner_id():
            await interaction.response.send_message("❌ Owner only command.", ephemeral=True)
            return
        
        try:
            # Load current data
            data = self.load_premium_data()
            original_count = len(data.get("subscriptions", {}))
            
            # Add test entry
            test_guild_id = f"test_{int(datetime.now().timestamp())}"
            data["subscriptions"][test_guild_id] = {
                "tier": "TEST",
                "expires_at": None,
                "purchased_by": str(interaction.user.id),
                "purchased_at": datetime.now().isoformat(),
                "payment_method": "Test",
                "amount_paid": 0,
                "notes": "Test save entry"
            }
            
            # Save data
            self.save_premium_data(data)
            
            # Load again to verify
            reloaded_data = self.load_premium_data()
            new_count = len(reloaded_data.get("subscriptions", {}))
            
            # Check if test entry exists
            test_exists = test_guild_id in reloaded_data.get("subscriptions", {})
            
            # Remove test entry
            if test_exists:
                del reloaded_data["subscriptions"][test_guild_id]
                self.save_premium_data(reloaded_data)
            
            embed = discord.Embed(
                title="🧪 Premium Save Test Results",
                color=discord.Color.green() if test_exists else discord.Color.red()
            )
            
            embed.add_field(name="Original Count", value=str(original_count), inline=True)
            embed.add_field(name="After Save Count", value=str(new_count), inline=True)
            embed.add_field(name="Test Entry Found", value="✅ YES" if test_exists else "❌ NO", inline=True)
            embed.add_field(name="Overall Result", value="✅ SUCCESS" if test_exists else "❌ FAILED", inline=True)
            
            file_path = self.get_data_path("premium_data.json")
            embed.add_field(name="File Path", value=f"`{file_path}`", inline=False)
            
            if os.path.exists(file_path):
                stat = os.stat(file_path)
                embed.add_field(name="File Size", value=f"{stat.st_size} bytes", inline=True)
                embed.add_field(name="Last Modified", value=f"<t:{int(stat.st_mtime)}:f>", inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except Exception as e:
            embed = discord.Embed(
                title="❌ Save Test Failed",
                description=str(e),
                color=discord.Color.red()
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="debug_bot_methods", description="Check bot premium methods (Owner only)")
    async def debug_bot_methods(self, interaction: discord.Interaction):
        if interaction.user.id != self.get_owner_id():
            await interaction.response.send_message("❌ Owner only command.", ephemeral=True)
            return
        
        embed = discord.Embed(title="🤖 Bot Premium Methods Debug", color=0x5DADE2)
        
        methods_to_check = [
            'premium_guild_ids',
            'premium_guild_tiers', 
            'vanity_limits',
            'get_guild_tier',
            'is_premium_guild',
            'get_vanity_limit_for_guild',
            'save_premium_guilds',
            'save_premium_tiers'
        ]
        
        for method in methods_to_check:
            has_method = hasattr(self.bot, method)
            embed.add_field(
                name=f"bot.{method}",
                value="✅ Exists" if has_method else "❌ Missing",
                inline=True
            )
        
        # Show current values if they exist
        if hasattr(self.bot, 'premium_guild_ids'):
            premium_count = len(self.bot.premium_guild_ids) if self.bot.premium_guild_ids else 0
            embed.add_field(
                name="Premium Guild IDs",
                value=f"{premium_count} guilds",
                inline=True
            )
        
        if hasattr(self.bot, 'premium_guild_tiers'):
            tiers_count = len(self.bot.premium_guild_tiers) if self.bot.premium_guild_tiers else 0
            embed.add_field(
                name="Premium Guild Tiers",
                value=f"{tiers_count} entries",
                inline=True
            )
        
        if hasattr(self.bot, 'vanity_limits'):
            embed.add_field(
                name="Vanity Limits",
                value=str(dict(self.bot.vanity_limits)),
                inline=False
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="set_premium_tier", description="Set premium tier for a guild (Owner only)")
    @app_commands.describe(
        guild_id="Guild ID to set premium tier for",
        tier="Premium tier to assign",
        duration_days="Duration in days (0 for permanent, -1 to remove)"
    )
    @app_commands.choices(tier=[
        app_commands.Choice(name="Free (no premium access)", value="free"),
        app_commands.Choice(name="Basic", value="basic"),
        app_commands.Choice(name="Pro", value="pro"),
        app_commands.Choice(name="Ultra", value="ultra")
    ])
    async def set_premium_tier(self, interaction: discord.Interaction, guild_id: str, tier: app_commands.Choice[str], duration_days: int = 0):
        owner_id = self.get_owner_id()
        if interaction.user.id != owner_id:
            await interaction.response.send_message("❌ This command is owner-only.", ephemeral=True)
            # Log access attempt
            await self.log_event(
                "access_attempts",
                f"Unauthorized attempt to use set_premium_tier by {interaction.user.display_name}",
                interaction.user,
                {"Command": "set_premium_tier", "Guild ID": guild_id, "Attempted Tier": tier.value}
            )
            return
        
        try:
            guild_id_int = int(guild_id)
            guild = self.bot.get_guild(guild_id_int)
            guild_name = guild.name if guild else "Unknown Guild"
            premium_data = self.load_premium_data()
            
            if duration_days == -1:
                if str(guild_id_int) in premium_data.get("subscriptions", {}):
                    old_tier = premium_data["subscriptions"][str(guild_id_int)].get("tier", "FREE")
                    del premium_data["subscriptions"][str(guild_id_int)]
                    self.save_premium_data(premium_data)
                    
                    # Log tier removal
                    await self.log_event(
                        "tier_changes",
                        f"Premium removed from guild {guild_name}",
                        interaction.user,
                        {
                            "Guild": guild_name,
                            "Guild ID": guild_id,
                            "Previous Tier": old_tier,
                            "New Tier": "FREE"
                        }
                    )
                
                embed = discord.Embed(
                    title="❌ Premium Removed",
                    description=f"Guild `{guild_name}` ({guild_id}) premium has been removed",
                    color=0xff6b6b,
                    timestamp=datetime.now()
                )
            else:
                expires_at = None
                if duration_days > 0:
                    expires_at = (datetime.now() + timedelta(days=duration_days)).isoformat()
                elif duration_days == 0:
                    expires_at = None  # Permanent
                
                tier_mapping = {
                    "free": "FREE",
                    "basic": "BASIC",
                    "pro": "PRO",
                    "ultra": "ULTRA",
                    "custom": "CUSTOM"
                }
                
                old_tier = "FREE"
                if str(guild_id_int) in premium_data.get("subscriptions", {}):
                    old_tier = premium_data["subscriptions"][str(guild_id_int)].get("tier", "FREE")
                
                subscription_data = {
                    "tier": tier_mapping.get(tier.value, tier.value.upper()),
                    "expires_at": expires_at,
                    "purchased_by": str(interaction.user.id),
                    "purchased_at": datetime.now().isoformat(),
                    "payment_method": "Manual",
                    "amount_paid": 0,
                    "notes": f"Set by {interaction.user.display_name} via /set_premium_tier"
                }
                
                if "subscriptions" not in premium_data:
                    premium_data["subscriptions"] = {}
                premium_data["subscriptions"][str(guild_id_int)] = subscription_data
                self.save_premium_data(premium_data)
                
                # Log tier change
                await self.log_event(
                    "tier_changes",
                    f"Premium tier updated for guild {guild_name}",
                    interaction.user,
                    {
                        "Guild": guild_name,
                        "Guild ID": guild_id,
                        "Previous Tier": old_tier,
                        "New Tier": tier_mapping.get(tier.value, tier.value.upper()),
                        "Duration": f"{duration_days} days" if duration_days > 0 else "Permanent"
                    }
                )
                
                embed = discord.Embed(
                    title="✅ Premium Tier Updated",
                    description=f"Guild `{guild_name}` ({guild_id}) is now **{tier.name}**",
                    color=0x00ff00,
                    timestamp=datetime.now()
                )
                
                if expires_at:
                    exp_date = datetime.fromisoformat(expires_at)
                    embed.add_field(
                        name="⏰ Expires",
                        value=f"<t:{int(exp_date.timestamp())}:F>",
                        inline=True
                    )
                else:
                    embed.add_field(
                        name="⏰ Duration",
                        value="**Permanent**",
                        inline=True
                    )
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Invalid guild ID format.", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error setting tier: {e}", ephemeral=True)
            # Log system error
            await self.log_event(
                "system_events",
                f"Error in set_premium_tier command: {str(e)}",
                interaction.user,
                {"Error": str(e), "Guild ID": guild_id}
            )

    @app_commands.command(name="premium_status", description="Check this server's premium status and vanity limits")
    async def premium_status(self, interaction: discord.Interaction):
        guild_id = interaction.guild_id

        tier = self.bot.get_guild_tier(guild_id)
        vanity_limit = self.bot.get_vanity_limit_for_guild(guild_id)

        tier_info = {
            'free': {'name': '🆓 Free', 'color': 0x95a5a6},
            'basic': {'name': '🥉 Basic', 'color': 0x8e44ad},
            'pro': {'name': '🥈 Pro', 'color': 0x3498db},
            'ultra': {'name': '🥇 Ultra', 'color': 0xf39c12},
            'custom': {'name': '💎 Custom', 'color': 0xe91e63}
        }
        tier_display = tier_info.get(tier, tier_info['free'])
        vanity_limit_text = "Unlimited" if vanity_limit == float('inf') else str(vanity_limit)

        embed = discord.Embed(
            title=f"{tier_display['name']} Tier",
            description=f"This server has **{tier_display['name']}** premium status.",
            color=tier_display['color'],
            timestamp=datetime.now()
        )
        embed.add_field(name="🎭 Vanity Role Limit", value=vanity_limit_text, inline=True)

        features = []
        if tier != 'free':
            features.append("✅ Vanity Roles")
            if tier in ['pro', 'ultra', 'custom']:
                features.append("✅ Advanced Analytics")
            if tier in ['ultra', 'custom']:
                features.append("✅ Priority Support")
            if tier == 'custom':
                features.append("✅ Custom Features")
        else:
            features.append("❌ Vanity Roles (Premium Only)")

        if features:
            embed.add_field(name="🎯 Features", value="\n".join(features), inline=False)
        
        # Log premium command usage
        await self.log_event(
            "premium_commands",
            f"Premium status checked by {interaction.user.display_name}",
            interaction.user,
            {"Guild": interaction.guild.name, "Current Tier": tier}
        )

        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="premium_logs", description="Configure premium system logging (Owner only)")
    @app_commands.describe(log_channel="Select a channel for premium logs (optional)")

    async def premium_logs(self, interaction: discord.Interaction, log_channel: str = None):
        """Configure premium logging settings"""
        if interaction.user.id != self.get_owner_id():
            await interaction.response.send_message("❌ This command is owner-only.", ephemeral=True)
            return
        
        # Set log channel if provided
        if log_channel:
            try:
                log_channel_id = int(log_channel)
                channel_obj = interaction.guild.get_channel(log_channel_id)
                if channel_obj:
                    self.save_logging_setting('log_channel_id', log_channel_id)
            except ValueError:
                pass
        
        # Show current settings
        settings = self.logging_settings
        
        embed = discord.Embed(
            title="💎 Premium Logging Configuration",
            description="Configure premium system logging and monitoring",
            color=discord.Color.gold()
        )
        
        log_events = settings.get('log_events', [])
        embed.add_field(
            name="📝 Current Status",
            value="✅ Enabled" if log_events else "❌ Disabled",
            inline=True
        )
        
        if log_events:
            embed.add_field(
                name="📊 Tracked Events",
                value=f"{len(log_events)} event types",
                inline=True
            )
        
        log_channel_id = settings.get('log_channel_id')
        if log_channel_id:
            channel = interaction.guild.get_channel(log_channel_id)
            embed.add_field(
                name="📄 Log Channel",
                value=f"#{channel.name}" if channel else "Unknown Channel",
                inline=True
            )
        
        webhook_url = settings.get('webhook_url', '')
        embed.add_field(
            name="🔗 Webhook",
            value="✅ Configured" if webhook_url else "❌ Not set",
            inline=True
        )
        
        embed.add_field(
            name="💡 Available Events",
            value="• Tier Changes\n• Subscription Events\n• Premium Commands\n• System Events\n• Access Attempts",
            inline=False
        )
        
        embed.add_field(
            name="ℹ️ Instructions",
            value="Use the interface below to configure which events to log, set up webhook integration, and test the logging system.",
            inline=False
        )
        
        view = PremiumLoggingView(self)
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

    @app_commands.command(name="list_premium_tiers", description="List all premium tiers and limits (Owner only)")
    async def list_premium_tiers(self, interaction: discord.Interaction):
        owner_id = self.get_owner_id()
        if interaction.user.id != owner_id:
            await interaction.response.send_message("❌ This command is owner-only.", ephemeral=True)
            return
        
        embed = discord.Embed(
            title="💎 Premium Tiers & Limits",
            description="Available premium tiers and their vanity role limits:",
            color=0xe91e63,
            timestamp=datetime.now()
        )
        
        tier_emojis = {
            'free': '🆓',
            'basic': '🥉',
            'pro': '🥈',
            'ultra': '🥇',
            'custom': '💎'
        }
        
        if hasattr(self.bot, 'vanity_limits'):
            for tier, limit in self.bot.vanity_limits.items():
                limit_text = "Unlimited" if limit == float('inf') else str(limit)
                emoji = tier_emojis.get(tier, '📦')
                embed.add_field(
                    name=f"{emoji} {tier.title()}",
                    value=f"**{limit_text}** vanity roles",
                    inline=True
                )
        else:
            embed.add_field(
                name="⚠️ Warning",
                value="Bot vanity limits not found! Check bot configuration.",
                inline=False
            )
        
        if hasattr(self.bot, 'premium_guild_tiers') and self.bot.premium_guild_tiers:
            tier_counts = {}
            for guild_tier in self.bot.premium_guild_tiers.values():
                tier_counts[guild_tier] = tier_counts.get(guild_tier, 0) + 1
            assignment_text = "\n".join([f"• **{tier.title()}**: {count} servers" for tier, count in tier_counts.items()])
            embed.add_field(
                name="📊 Current Assignments",
                value=assignment_text or "No premium assignments",
                inline=False
            )
        
        # Log premium command usage
        await self.log_event(
            "premium_commands",
            f"Premium tiers list accessed by {interaction.user.display_name}",
            interaction.user,
            {"Command": "list_premium_tiers"}
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    def get_guild_premium_info(self, guild_id: int):
        premium_data = self.load_premium_data()
        guild_str = str(guild_id)
        if guild_str in premium_data.get("subscriptions", {}):
            subscription = premium_data["subscriptions"][guild_str]
            expires_at = subscription.get("expires_at")
            is_expired = False
            if expires_at and expires_at != "null":
                try:
                    exp_date = datetime.fromisoformat(expires_at)
                    is_expired = datetime.now() > exp_date
                except ValueError:
                    pass
            return {
                "tier": subscription.get("tier", "FREE").lower(),
                "expires_at": expires_at,
                "is_expired": is_expired,
                "purchased_by": subscription.get("purchased_by"),
                "purchased_at": subscription.get("purchased_at"),
                "notes": subscription.get("notes")
            }
        return {"tier": "free", "expires_at": None, "is_expired": False}

    @app_commands.command(name="premium_info", description="Show detailed premium information for a guild")
    async def premium_info(self, interaction: discord.Interaction, guild_id: str = None):
        if guild_id and interaction.user.id != self.get_owner_id():
            await interaction.response.send_message("❌ Only the owner can check other guilds.", ephemeral=True)
            return
        
        target_guild_id = int(guild_id) if guild_id else interaction.guild_id
        target_guild = self.bot.get_guild(target_guild_id)
        guild_name = target_guild.name if target_guild else f"Guild {target_guild_id}"
        
        info = self.get_guild_premium_info(target_guild_id)
        
        colors = {
            "free": 0x95a5a6,
            "basic": 0x8e44ad,
            "pro": 0x3498db,
            "ultra": 0xf39c12,
            "custom": 0xe91e63
        }
        
        embed = discord.Embed(
            title=f"💎 Premium Info - {guild_name}",
            description=f"Tier: **{info['tier'].title()}**",
            color=colors.get(info['tier'], 0x95a5a6),
            timestamp=datetime.now()
        )
        
        if info['expires_at'] and info['expires_at'] != "null":
            try:
                exp_date = datetime.fromisoformat(info['expires_at'])
                status = "❌ Expired" if info['is_expired'] else "✅ Active"
                embed.add_field(
                    name="Status",
                    value=f"{status}\nExpires: <t:{int(exp_date.timestamp())}:F>",
                    inline=False
                )
            except ValueError:
                pass
        else:
            embed.add_field(name="Status", value="✅ Permanent", inline=False)
        
        if info.get('purchased_by'):
            embed.add_field(name="Set By", value=f"<@{info['purchased_by']}>", inline=True)
        
        if info.get('notes'):
            embed.add_field(name="Notes", value=info['notes'], inline=False)
        
        # Log premium command usage
        await self.log_event(
            "premium_commands",
            f"Premium info accessed for guild {guild_name}",
            interaction.user,
            {"Guild": guild_name, "Guild ID": str(target_guild_id)}
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="premium_stats", description="View premium system statistics (Owner only)")
    async def premium_stats(self, interaction: discord.Interaction):
        if interaction.user.id != self.get_owner_id():
            await interaction.response.send_message("❌ This command is owner-only.", ephemeral=True)
            return
        
        premium_data = self.load_premium_data()
        subscriptions = premium_data.get("subscriptions", {})
        
        embed = discord.Embed(
            title="📊 Premium System Statistics",
            description="Comprehensive premium system overview",
            color=discord.Color.gold(),
            timestamp=datetime.now()
        )
        
        # Count tiers
        tier_counts = {"basic": 0, "pro": 0, "ultra": 0, "custom": 0}
        active_subs = 0
        expired_subs = 0
        
        for guild_id, sub in subscriptions.items():
            tier = sub.get("tier", "FREE").lower()
            expires_at = sub.get("expires_at")
            
            is_active = True
            if expires_at and expires_at != "null":
                try:
                    exp_date = datetime.fromisoformat(expires_at)
                    is_active = datetime.now() <= exp_date
                except ValueError:
                    pass
            
            if tier in tier_counts:
                tier_counts[tier] += 1
                if is_active:
                    active_subs += 1
                else:
                    expired_subs += 1
        
        embed.add_field(name="📈 Total Subscriptions", value=str(len(subscriptions)), inline=True)
        embed.add_field(name="✅ Active", value=str(active_subs), inline=True)
        embed.add_field(name="❌ Expired", value=str(expired_subs), inline=True)
        
        # Tier breakdown
        tier_text = "\n".join([
            f"🥉 Basic: {tier_counts['basic']}",
            f"🥈 Pro: {tier_counts['pro']}",
            f"🥇 Ultra: {tier_counts['ultra']}",
            f"💎 Custom: {tier_counts['custom']}"
        ])
        embed.add_field(name="📋 Tier Breakdown", value=tier_text, inline=False)
        
        # Logging stats
        log_events = self.logging_settings.get('log_events', [])
        embed.add_field(
            name="📝 Logging Status",
            value=f"{'✅ Enabled' if log_events else '❌ Disabled'} ({len(log_events)} events)",
            inline=True
        )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="debug_premium_complete", description="Complete premium system debug (Owner only)")
    async def debug_premium_complete(self, interaction: discord.Interaction):
        if interaction.user.id != self.get_owner_id():
            await interaction.response.send_message("❌ Owner only command.", ephemeral=True)
            return
        
        guild_id = interaction.guild_id
        embed = discord.Embed(title="🔍 Complete Premium Debug", color=0x5DADE2)
        
        try:
            tier = self.bot.get_guild_tier(guild_id)
            is_premium = self.bot.is_premium_guild(guild_id)
            vanity_limit = self.bot.get_vanity_limit_for_guild(guild_id)
            
            embed.add_field(name="Tier", value=f"`{tier}`", inline=True)
            embed.add_field(name="Is Premium", value=f"`{is_premium}`", inline=True)
            embed.add_field(name="Vanity Limit", value=f"`{vanity_limit}`", inline=True)
            
            guild_str = str(guild_id)
            json_data = self.load_premium_data()
            in_json = guild_str in json_data.get("subscriptions", {})
            embed.add_field(name="In JSON File", value="✅ Yes" if in_json else "❌ No", inline=True)
            
            in_memory = hasattr(self.bot, 'premium_guild_ids') and guild_str in getattr(self.bot, 'premium_guild_ids', set())
            embed.add_field(name="In Memory", value="✅ Yes" if in_memory else "❌ No", inline=True)
            
            if hasattr(self.bot, 'vanity_limits'):
                limits_text = ", ".join([f"{k}: {v}" for k, v in self.bot.vanity_limits.items()])
                embed.add_field(name="Bot Vanity Limits", value=f"`{limits_text}`", inline=False)
            else:
                embed.add_field(name="Bot Vanity Limits", value="❌ Missing!", inline=False)
            
            # Logging debug
            log_events = self.logging_settings.get('log_events', [])
            embed.add_field(
                name="Logging Events",
                value=f"{len(log_events)} configured" if log_events else "None configured",
                inline=True
            )
            
        except Exception as e:
            embed.add_field(name="Error", value=str(e), inline=False)
            # Log the error
            await self.log_event(
                "system_events",
                f"Debug command error: {str(e)}",
                interaction.user,
                {"Command": "debug_premium_complete", "Error": str(e)}
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @app_commands.command(name="debug_premium_save", description="Debug premium save system (Owner only)")
    async def debug_premium_save(self, interaction: discord.Interaction):
        if interaction.user.id != self.get_owner_id():
            await interaction.response.send_message("❌ Owner only command.", ephemeral=True)
            return
        
        guild_id = interaction.guild_id
        embed = discord.Embed(title="🔍 Premium Save Debug", color=0x5DADE2)
        
        try:
            data = self.load_premium_data()
            embed.add_field(name="Load Test", value="✅ Success", inline=True)
            embed.add_field(name="Subscriptions Count", value=str(len(data.get("subscriptions", {}))), inline=True)
            
            guild_str = str(guild_id)
            in_data = guild_str in data.get("subscriptions", {})
            embed.add_field(name="Guild In Data", value="✅ Yes" if in_data else "❌ No", inline=True)
            
            in_memory = hasattr(self.bot, 'premium_guild_ids') and guild_str in getattr(self.bot, 'premium_guild_ids', set())
            embed.add_field(name="In Memory", value="✅ Yes" if in_memory else "❌ No", inline=True)
            
            file_path = self.get_data_path("premium_data.json")
            file_exists = os.path.exists(file_path)
            embed.add_field(name="File Exists", value="✅ Yes" if file_exists else "❌ No", inline=True)
            embed.add_field(name="File Path", value=f"`{file_path}`", inline=False)
            
            # Log the debug access
            await self.log_event(
                "system_events",
                f"Premium save debug accessed by {interaction.user.display_name}",
                interaction.user,
                {"Command": "debug_premium_save", "Guild": interaction.guild.name}
            )
            
        except Exception as e:
            embed.add_field(name="Error", value=str(e), inline=False)
            await self.log_event(
                "system_events",
                f"Premium save debug error: {str(e)}",
                interaction.user,
                {"Command": "debug_premium_save", "Error": str(e)}
            )
        
        await interaction.response.send_message(embed=embed, ephemeral=True)

    @commands.Cog.listener()
    async def on_ready(self):
        """Log when the premium system comes online"""
        await self.log_event(
            "system_events",
            "Premium system started successfully",
            None,
            {
                "Bot": self.bot.user.name,
                "Guilds": str(len(self.bot.guilds)),
                "Status": "Online"
            }
        )


async def setup(bot):
    await bot.add_cog(Premium(bot))

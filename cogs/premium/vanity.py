import discord
from discord.ext import commands, tasks
from discord import app_commands
from discord.ui import View, Select, Button
import asyncio
import logging
import json
import os
import re
from datetime import datetime, timedelta
from typing import List, Optional
from collections import deque
import aiohttp

logger = logging.getLogger(__name__)

# ===== RATE LIMITER CLASS =====
class RateLimiter:
    """Rate limiter to prevent Discord API 429 errors"""
    def __init__(self, max_requests=45, time_window=1):
        self.max_requests = max_requests  # Stay under 50/sec limit
        self.time_window = time_window
        self.requests = deque()
        self._lock = asyncio.Lock()
    
    async def wait_if_needed(self):
        async with self._lock:
            now = datetime.utcnow()
            # Remove old requests outside time window
            while self.requests and (now - self.requests[0]).total_seconds() > self.time_window:
                self.requests.popleft()
            
            if len(self.requests) >= self.max_requests:
                sleep_time = self.time_window - (now - self.requests[0]).total_seconds()
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                    # Clean up old requests after sleeping
                    now = datetime.utcnow()
                    while self.requests and (now - self.requests[0]).total_seconds() > self.time_window:
                        self.requests.popleft()
            
            self.requests.append(datetime.utcnow())

# ===== VANITY SETTINGS STORAGE =====
class VanitySettings:
    def __init__(self, vanity_cog):
        self.vanity_cog = vanity_cog
        self.settings = {}
    
    def get_guild_settings(self, guild_id: str) -> dict:
        return self.settings.get(guild_id, {
            "match_mode": "substring",
            "priority_mode": "longest_first", 
            "case_sensitive": False,
            "enabled_triggers": [],
            "role_log_enabled": False,
            "role_log_channel_id": None,
            "check_bio": True,
            "check_server_invite": True,
            "require_server_invite_match": False,
            "log_webhook": ""
        })
    
    def save_guild_setting(self, guild_id: str, key: str, value):
        if guild_id not in self.settings:
            self.settings[guild_id] = self.get_guild_settings(guild_id)
        self.settings[guild_id][key] = value
        self._save_to_file()
    
    def _save_to_file(self):
        try:
            file_path = self.vanity_cog.get_data_path("vanity_settings.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(self.settings, f, indent=2, ensure_ascii=False)
            logger.info("Vanity settings saved successfully")
        except Exception as e:
            logger.error(f"Error saving vanity settings: {e}")
    
    def load_from_file(self):
        try:
            file_path = self.vanity_cog.get_data_path("vanity_settings.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    self.settings = json.load(f)
                logger.info(f"Loaded vanity settings for {len(self.settings)} guilds")
        except Exception as e:
            logger.error(f"Error loading vanity settings: {e}")

# ===== MODAL FOR ADDING VANITY ROLE =====
class AddVanityRoleModal(discord.ui.Modal, title="Add Vanity Role"):
    trigger_text = discord.ui.TextInput(
        label="Trigger Text",
        placeholder="Enter the status text to trigger this role",
        required=True,
        max_length=100
    )
    
    def __init__(self, vanity_cog, guild_id: str):
        super().__init__()
        self.vanity_cog = vanity_cog
        self.guild_id = guild_id
    
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        
        trigger = self.trigger_text.value.strip()
        if not trigger:
            await interaction.followup.send("❌ Trigger text cannot be empty.", ephemeral=True)
            return
        
        view = RoleSelectionView(self.vanity_cog, self.guild_id, trigger)
        await interaction.followup.send(
            f"Select a role to assign when status contains: `{trigger}`",
            view=view,
            ephemeral=True
        )

# ===== ROLE SELECTION VIEW =====
class RoleSelectionView(discord.ui.View):
    def __init__(self, vanity_cog, guild_id: str, trigger_text: str):
        super().__init__(timeout=60)
        self.vanity_cog = vanity_cog
        self.guild_id = guild_id
        self.trigger_text = trigger_text
        self.add_role_select()
    
    def add_role_select(self):
        guild = self.vanity_cog.bot.get_guild(int(self.guild_id))
        if not guild:
            return
        
        roles = [r for r in guild.roles if r != guild.default_role and not r.managed]
        roles = sorted(roles, key=lambda r: r.position, reverse=True)[:25]
        
        options = [
            discord.SelectOption(
                label=role.name[:100],
                value=str(role.id),
                description=f"Position: {role.position}"
            )
            for role in roles
        ]
        
        select = discord.ui.Select(
            placeholder="Choose a role...",
            options=options,
            min_values=1,
            max_values=1
        )
        select.callback = self.role_selected
        self.add_item(select)
    
    async def role_selected(self, interaction: discord.Interaction):
        role_id = interaction.data['values'][0]
        
        mapping = self.vanity_cog._get_vanity_roles(self.guild_id)
        mapping[self.trigger_text.lower()] = role_id
        self.vanity_cog._save_vanity_roles(self.guild_id, mapping)
        
        role = interaction.guild.get_role(int(role_id))
        await interaction.response.send_message(
            f"✅ Added vanity role mapping:\n**Trigger:** `{self.trigger_text}`\n**Role:** {role.mention}",
            ephemeral=True
        )
        
        await self.vanity_cog.send_webhook_log(
            self.guild_id,
            "role_added",
            f"New vanity role mapping created",
            user=interaction.user,
            additional_data={
                "Trigger": self.trigger_text,
                "Role": role.name,
                "Added By": str(interaction.user)
            }
        )

# ===== VANITY ROLES LIST VIEW =====
class VanityRolesListView(discord.ui.View):
    def __init__(self, vanity_cog, guild_id: str, mappings: dict):
        super().__init__(timeout=180)
        self.vanity_cog = vanity_cog
        self.guild_id = guild_id
        self.mappings = mappings
        self.current_page = 0
        self.items_per_page = 10
        self.update_buttons()
    
    def get_page_items(self):
        items = list(self.mappings.items())
        start = self.current_page * self.items_per_page
        end = start + self.items_per_page
        return items[start:end]
    
    def update_buttons(self):
        self.clear_items()
        
        total_pages = (len(self.mappings) + self.items_per_page - 1) // self.items_per_page
        
        if self.current_page > 0:
            prev_button = Button(label="◀ Previous", style=discord.ButtonStyle.primary)
            prev_button.callback = self.prev_page
            self.add_item(prev_button)
        
        if self.current_page < total_pages - 1:
            next_button = Button(label="Next ▶", style=discord.ButtonStyle.primary)
            next_button.callback = self.next_page
            self.add_item(next_button)
        
        delete_button = Button(label="🗑️ Delete Mapping", style=discord.ButtonStyle.danger)
        delete_button.callback = self.show_delete_select
        self.add_item(delete_button)
    
    async def prev_page(self, interaction: discord.Interaction):
        self.current_page -= 1
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def next_page(self, interaction: discord.Interaction):
        self.current_page += 1
        self.update_buttons()
        embed = self.create_embed()
        await interaction.response.edit_message(embed=embed, view=self)
    
    async def show_delete_select(self, interaction: discord.Interaction):
        options = []
        for trigger, role_id in list(self.mappings.items())[:25]:
            role = interaction.guild.get_role(int(role_id))
            role_name = role.name if role else "Unknown Role"
            options.append(
                discord.SelectOption(
                    label=trigger[:100],
                    value=trigger,
                    description=f"Role: {role_name}"[:100]
                )
            )
        
        select = Select(placeholder="Select mapping to delete", options=options)
        
        async def delete_callback(select_interaction: discord.Interaction):
            trigger_to_delete = select_interaction.data['values'][0]
            del self.mappings[trigger_to_delete]
            self.vanity_cog._save_vanity_roles(self.guild_id, self.mappings)
            
            await select_interaction.response.send_message(
                f"✅ Deleted vanity role mapping for trigger: `{trigger_to_delete}`",
                ephemeral=True
            )
            
            if len(self.mappings) == 0:
                await interaction.edit_original_response(
                    content="No vanity roles configured.",
                    embed=None,
                    view=None
                )
            else:
                self.update_buttons()
                embed = self.create_embed()
                await interaction.edit_original_response(embed=embed, view=self)
        
        select.callback = delete_callback
        view = View(timeout=60)
        view.add_item(select)
        
        await interaction.response.send_message("Select a mapping to delete:", view=view, ephemeral=True)
    
    def create_embed(self):
        guild = self.vanity_cog.bot.get_guild(int(self.guild_id))
        embed = discord.Embed(
            title="🎭 Vanity Role Mappings",
            description="Roles assigned based on custom status",
            color=discord.Color.purple()
        )
        
        page_items = self.get_page_items()
        for trigger, role_id in page_items:
            role = guild.get_role(int(role_id)) if guild else None
            role_mention = role.mention if role else f"Role ID: {role_id}"
            embed.add_field(
                name=f"Trigger: {trigger}",
                value=f"Role: {role_mention}",
                inline=False
            )
        
        total_pages = (len(self.mappings) + self.items_per_page - 1) // self.items_per_page
        embed.set_footer(text=f"Page {self.current_page + 1}/{total_pages} • Total: {len(self.mappings)} mappings")
        
        return embed

# ===== MAIN VANITY COG =====
class Vanity(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.vanity_settings = VanitySettings(self)
        self.vanity_settings.load_from_file()
        
        # Initialize rate limiters to prevent 429 errors
        self.rate_limiter = RateLimiter(max_requests=45, time_window=1)
        self.webhook_rate_limiter = RateLimiter(max_requests=5, time_window=1)
        self._webhook_cache = {}
        
        self._setup_premium_fallbacks()
        
        if not self.check_vanity_roles_task.is_running():
            self.check_vanity_roles_task.start()
    
    def _setup_premium_fallbacks(self):
        """Setup fallback methods if premium system is not available"""
        if not hasattr(self.bot, 'is_premium_guild'):
            self.bot.is_premium_guild = lambda guild_id: True
            logger.warning("Premium system not found, treating all guilds as premium")
    
    def get_data_path(self, filename: str) -> str:
        """Get path for data file"""
        data_dir = os.path.join(os.getcwd(), "data", "vanity")
        os.makedirs(data_dir, exist_ok=True)
        return os.path.join(data_dir, filename)
    
    def _get_vanity_roles(self, guild_id: str) -> dict:
        """Load vanity roles from file"""
        try:
            file_path = self.get_data_path(f"vanity_roles_{guild_id}.json")
            if os.path.exists(file_path):
                with open(file_path, "r", encoding="utf-8") as f:
                    return json.load(f)
        except Exception as e:
            logger.error(f"Error loading vanity roles for guild {guild_id}: {e}")
        return {}
    
    def _save_vanity_roles(self, guild_id: str, mapping: dict):
        """Save vanity roles to file"""
        try:
            file_path = self.get_data_path(f"vanity_roles_{guild_id}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(mapping, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved vanity roles for guild {guild_id}")
        except Exception as e:
            logger.error(f"Error saving vanity roles for guild {guild_id}: {e}")
    
    async def send_webhook_log(self, guild_id: str, event_type: str, message: str, user=None, additional_data=None):
        """Send logs via webhook with rate limiting and caching"""
        try:
            # Add cooldown check to prevent spam
            cache_key = f"{guild_id}:{event_type}"
            if cache_key in self._webhook_cache:
                last_sent = self._webhook_cache[cache_key]
                if (datetime.utcnow() - last_sent).total_seconds() < 10:
                    return  # Skip if sent within last 10 seconds
            
            settings = self.vanity_settings.get_guild_settings(guild_id)
            webhook_url = settings.get('log_webhook', '').strip()
            
            if not webhook_url:
                return
            
            guild = self.bot.get_guild(int(guild_id))
            if not guild:
                return
            
            # Wait for webhook rate limiter
            await self.webhook_rate_limiter.wait_if_needed()
            
            embed = discord.Embed(
                title=f"🎭 Vanity {event_type.replace('_', ' ').title()}",
                description=message,
                color=discord.Color.purple(),
                timestamp=datetime.utcnow()
            )
            
            if user:
                embed.set_author(name=str(user), icon_url=user.display_avatar.url)
            
            if additional_data:
                for key, value in additional_data.items():
                    embed.add_field(name=key, value=str(value)[:1024], inline=False)
            
            embed.set_footer(text=f"Guild: {guild.name}")
            
            async with aiohttp.ClientSession() as session:
                webhook = discord.Webhook.from_url(webhook_url, session=session)
                await webhook.send(embed=embed, username="Vanity Logger")
                logger.info(f"Sent webhook log for event '{event_type}' in guild {guild_id}")
                
            # Update cache
            self._webhook_cache[cache_key] = datetime.utcnow()
                
        except Exception as e:
            logger.error(f"Error sending webhook log: {e}")
    
    async def check_member_bio_and_status(self, member: discord.Member, guild_id: str) -> tuple:
        """Check member's bio and status, returns (combined_text, has_server_invite)"""
        settings = self.vanity_settings.get_guild_settings(guild_id)
        
        combined_text = ""
        has_server_invite = False
        
        # Check custom status
        if settings.get("check_bio", True):
            for activity in member.activities:
                if isinstance(activity, discord.CustomActivity):
                    if activity.name:
                        combined_text += f" {activity.name}"
        
        # Check if bio contains server invite
        if settings.get("check_server_invite", True):
            invite_pattern = r'discord\.gg/[\w-]+|discordapp\.com/invite/[\w-]+'
            if re.search(invite_pattern, combined_text, re.IGNORECASE):
                has_server_invite = True
        
        return combined_text.strip(), has_server_invite
    
    def apply_vanity_settings(self, guild_id: str, status_text: str, role_objects: dict, has_server_invite: bool) -> dict:
        """Apply vanity settings filters and return matching roles"""
        settings = self.vanity_settings.get_guild_settings(guild_id)
        
        # Check server invite requirement
        if settings.get("require_server_invite_match", False) and not has_server_invite:
            return {}
        
        # Filter enabled triggers
        enabled_triggers = settings.get("enabled_triggers", [])
        if enabled_triggers:
            role_objects = {k: v for k, v in role_objects.items() if k in enabled_triggers}
        
        # Apply case sensitivity
        case_sensitive = settings.get("case_sensitive", False)
        if not case_sensitive:
            status_text = status_text.lower()
        
        # Match mode
        match_mode = settings.get("match_mode", "substring")
        matching_roles = {}
        
        for trigger, role in role_objects.items():
            trigger_check = trigger if case_sensitive else trigger.lower()
            
            if match_mode == "exact":
                if status_text == trigger_check:
                    matching_roles[role] = trigger
            elif match_mode == "word_boundary":
                pattern = r'\b' + re.escape(trigger_check) + r'\b'
                if re.search(pattern, status_text):
                    matching_roles[role] = trigger
            else:  # substring (default)
                if trigger_check in status_text:
                    matching_roles[role] = trigger
        
        # Apply priority mode
        priority_mode = settings.get("priority_mode", "longest_first")
        if priority_mode == "longest_first" and len(matching_roles) > 1:
            sorted_roles = sorted(matching_roles.items(), key=lambda x: len(x[1]), reverse=True)
            matching_roles = {sorted_roles[0][0]: sorted_roles[0][1]}
        elif priority_mode == "shortest_first" and len(matching_roles) > 1:
            sorted_roles = sorted(matching_roles.items(), key=lambda x: len(x[1]))
            matching_roles = {sorted_roles[0][0]: sorted_roles[0][1]}
        
        return matching_roles
    
    async def log_role_change(self, guild_id: str, member: discord.Member, role: discord.Role, action: str, reason: str, trigger_text: str):
        """Log role changes to configured channel"""
        settings = self.vanity_settings.get_guild_settings(guild_id)
        
        if not settings.get("role_log_enabled", False):
            return
        
        channel_id = settings.get("role_log_channel_id")
        if not channel_id:
            return
        
        channel = self.bot.get_channel(int(channel_id))
        if not channel:
            return
        
        color = discord.Color.green() if action == "added" else discord.Color.red()
        embed = discord.Embed(
            title=f"🎭 Vanity Role {action.title()}",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(name="Member", value=f"{member.mention} ({member})", inline=False)
        embed.add_field(name="Role", value=role.mention, inline=True)
        embed.add_field(name="Action", value=action.title(), inline=True)
        embed.add_field(name="Trigger", value=f"`{trigger_text}`", inline=False)
        embed.add_field(name="Reason", value=reason, inline=False)
        embed.set_thumbnail(url=member.display_avatar.url)
        
        try:
            await channel.send(embed=embed)
        except Exception as e:
            logger.error(f"Error sending role log: {e}")
    
    async def _safe_add_role(self, member: discord.Member, role: discord.Role, reason: str, guild_id: str, trigger_text: str = "Unknown"):
        """Safely add role with rate limiting and retry logic"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Wait for rate limiter
                await self.rate_limiter.wait_if_needed()
                
                if role.position >= member.guild.me.top_role.position:
                    logger.warning(f"Cannot add role {role.name} to {member.id}: role hierarchy")
                    return

                if role not in member.roles:
                    await member.add_roles(role, reason=reason)
                    logger.info(f"Added role {role.name} to {member.display_name} ({member.id}) in guild {guild_id}")

                    # Log to channel if enabled
                    await self.log_role_change(
                        guild_id,
                        member,
                        role,
                        "added",
                        reason,
                        trigger_text
                    )
                return

            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    retry_after = float(e.response.headers.get('Retry-After', 5))
                    logger.warning(f"Rate limited, waiting {retry_after}s (attempt {retry_count + 1}/{max_retries})")
                    await asyncio.sleep(retry_after)
                    retry_count += 1
                else:
                    logger.error(f"HTTP error adding role: {e}")
                    break
            except discord.Forbidden:
                logger.error(f"Missing permissions to add role {role.name} to {member.id}")
                break
            except Exception as e:
                logger.error(f"Error adding role: {e}", exc_info=True)
                break
        
        if retry_count >= max_retries:
            logger.error(f"Failed to add role {role.name} to {member.id} after {max_retries} attempts")
    
    async def _safe_remove_role(self, member: discord.Member, role: discord.Role, reason: str, guild_id: str, trigger_text: str = "Unknown"):
        """Safely remove role with rate limiting and retry logic"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Wait for rate limiter
                await self.rate_limiter.wait_if_needed()
                
                if role.position >= member.guild.me.top_role.position:
                    logger.warning(f"Cannot remove role {role.name} from {member.id}: role hierarchy")
                    return

                if role in member.roles:
                    await member.remove_roles(role, reason=reason)
                    logger.info(f"Removed role {role.name} from {member.display_name} ({member.id}) in guild {guild_id}")

                    # Log to channel if enabled
                    await self.log_role_change(
                        guild_id,
                        member,
                        role,
                        "removed",
                        reason,
                        trigger_text
                    )
                return

            except discord.HTTPException as e:
                if e.status == 429:  # Rate limited
                    retry_after = float(e.response.headers.get('Retry-After', 5))
                    logger.warning(f"Rate limited, waiting {retry_after}s (attempt {retry_count + 1}/{max_retries})")
                    await asyncio.sleep(retry_after)
                    retry_count += 1
                else:
                    logger.error(f"HTTP error removing role: {e}")
                    break
            except discord.Forbidden:
                logger.error(f"Missing permissions to remove role {role.name} from {member.id}")
                break
            except Exception as e:
                logger.error(f"Error removing role: {e}", exc_info=True)
                break
        
        if retry_count >= max_retries:
            logger.error(f"Failed to remove role {role.name} from {member.id} after {max_retries} attempts")
    
    @tasks.loop(minutes=5)
    async def check_vanity_roles_task(self):
        """Main task to check and assign/remove vanity roles"""
        try:
            processed_guilds = 0
            role_changes = 0
            start_time = datetime.utcnow()

            for guild in self.bot.guilds:
                try:
                    if not self.bot.is_premium_guild(guild.id):
                        continue
                except Exception as e:
                    logger.error(f"Error checking premium for guild {guild.id}: {e}")
                    continue

                mapping = self._get_vanity_roles(str(guild.id))
                if not mapping:
                    continue

                # Build role objects map
                role_objects = {}
                vanity_role_ids = set()

                for text, role_id in mapping.items():
                    role = guild.get_role(int(role_id))
                    if role:
                        role_objects[text.lower()] = role
                        vanity_role_ids.add(role.id)

                if not role_objects:
                    continue

                guild_role_changes = 0
                batch_size = 10  # Reduced from 50 to 10 to prevent rate limits
                members = [m for m in guild.members if not m.bot and m.status != discord.Status.offline]
                
                for i in range(0, len(members), batch_size):
                    member_batch = members[i:i + batch_size]
                    
                    for member in member_batch:
                        try:
                            # Get combined status and bio
                            combined_status, has_server_invite = await self.check_member_bio_and_status(member, str(guild.id))
                            
                            current_vanity_roles = {role for role in member.roles if role.id in vanity_role_ids}

                            # Get roles that should be assigned
                            should_have_roles_dict = self.apply_vanity_settings(
                                str(guild.id), combined_status, role_objects, has_server_invite
                            )
                            should_have_roles = set(should_have_roles_dict.keys())

                            # Determine changes needed
                            roles_to_add = should_have_roles - current_vanity_roles
                            roles_to_remove = current_vanity_roles - should_have_roles

                            # Process role additions
                            for role in roles_to_add:
                                trigger_text = should_have_roles_dict.get(role, "Unknown")
                                await self._safe_add_role(
                                    member, role, 
                                    f"Vanity trigger matched: {trigger_text}", 
                                    str(guild.id), trigger_text
                                )
                                guild_role_changes += 1
                                role_changes += 1
                                await asyncio.sleep(0.5)  # Delay between operations

                            # Process role removals
                            for role in roles_to_remove:
                                # Try to find which trigger it was
                                trigger_text = "Status changed"
                                for text, r in role_objects.items():
                                    if r == role:
                                        trigger_text = text
                                        break
                                await self._safe_remove_role(
                                    member, role, 
                                    "Vanity trigger no longer matched", 
                                    str(guild.id), trigger_text
                                )
                                guild_role_changes += 1
                                role_changes += 1
                                await asyncio.sleep(0.5)  # Delay between operations
                        
                        except Exception as e:
                            logger.error(f"Error processing member {member.id}: {e}")
                            continue
                    
                    # Delay between batches
                    await asyncio.sleep(2)

                logger.info(f"Processed guild {guild.id}: {guild_role_changes} role changes")
                processed_guilds += 1
                
                # Longer delay between guilds
                await asyncio.sleep(5)

            if role_changes > 0:
                duration = (datetime.utcnow() - start_time).total_seconds()
                logger.info(f"Vanity check completed: {processed_guilds} guilds, {role_changes} role changes in {duration:.1f}s")

        except Exception as e:
            logger.error(f"Vanity role task error: {e}", exc_info=True)
    
    @check_vanity_roles_task.before_loop
    async def before_check_vanity_roles_task(self):
        await self.bot.wait_until_ready()
    
    # ===== SLASH COMMANDS =====
    
    @app_commands.command(name="vanity_add", description="Add a vanity role mapping")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def vanity_add(self, interaction: discord.Interaction):
        """Add a new vanity role mapping"""
        try:
            if not self.bot.is_premium_guild(interaction.guild.id):
                await interaction.response.send_message(
                    "❌ This feature requires a premium subscription.",
                    ephemeral=True
                )
                return
        except:
            pass
        
        modal = AddVanityRoleModal(self, str(interaction.guild.id))
        await interaction.response.send_modal(modal)
    
    @app_commands.command(name="vanity_list", description="List all vanity role mappings")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def vanity_list(self, interaction: discord.Interaction):
        """List all vanity role mappings"""
        await interaction.response.defer(ephemeral=True)
        
        mapping = self._get_vanity_roles(str(interaction.guild.id))
        
        if not mapping:
            await interaction.followup.send("No vanity roles configured.", ephemeral=True)
            return
        
        view = VanityRolesListView(self, str(interaction.guild.id), mapping)
        embed = view.create_embed()
        await interaction.followup.send(embed=embed, view=view, ephemeral=True)
    
    @app_commands.command(name="vanity_configure", description="Configure vanity role settings")
    @app_commands.checks.has_permissions(manage_roles=True)
    async def vanity_configure(self, interaction: discord.Interaction):
        """Configure advanced vanity role settings"""
        await interaction.response.defer(ephemeral=True)
        
        settings = self.vanity_settings.get_guild_settings(str(interaction.guild.id))
        
        embed = discord.Embed(
            title="⚙️ Vanity Role Settings",
            description="Current configuration for this server",
            color=discord.Color.blue()
        )
        
        mode_descriptions = {
            "substring": "Substring - triggers anywhere in status",
            "exact": "Exact Match - status must exactly match trigger",
            "word_boundary": "Word Boundary - trigger matches as complete words"
        }
        
        priority_descriptions = {
            "longest_first": "Longest First - prioritize longer trigger texts",
            "shortest_first": "Shortest First - prioritize shorter trigger texts",
            "all": "All - assign all matching roles"
        }
        
        embed.add_field(
            name="Match Mode",
            value=mode_descriptions.get(settings["match_mode"], settings["match_mode"]),
            inline=False
        )
        
        embed.add_field(
            name="Priority Mode",
            value=priority_descriptions.get(settings["priority_mode"], settings["priority_mode"]),
            inline=False
        )
        
        embed.add_field(
            name="Case Sensitive",
            value="✅ Yes" if settings["case_sensitive"] else "❌ No",
            inline=True
        )
        
        embed.add_field(
            name="Check Bio",
            value="✅ Yes" if settings["check_bio"] else "❌ No",
            inline=True
        )
        
        embed.add_field(
            name="Check Server Invite",
            value="✅ Yes" if settings["check_server_invite"] else "❌ No",
            inline=True
        )
        
        embed.add_field(
            name="Role Logging",
            value="✅ Enabled" if settings["role_log_enabled"] else "❌ Disabled",
            inline=True
        )
        
        if settings["role_log_channel_id"]:
            channel = interaction.guild.get_channel(int(settings["role_log_channel_id"]))
            embed.add_field(
                name="Log Channel",
                value=channel.mention if channel else "Not Set",
                inline=True
            )
        
        await interaction.followup.send(embed=embed, ephemeral=True)
    
    @app_commands.command(name="vanity_check", description="Manually trigger vanity role check for yourself")
    async def vanity_check(self, interaction: discord.Interaction):
        """Manually check and update vanity roles for the user"""
        await interaction.response.defer(ephemeral=True)
        
        mapping = self._get_vanity_roles(str(interaction.guild.id))
        if not mapping:
            await interaction.followup.send("No vanity roles configured.", ephemeral=True)
            return
        
        role_objects = {}
        vanity_role_ids = set()
        
        for text, role_id in mapping.items():
            role = interaction.guild.get_role(int(role_id))
            if role:
                role_objects[text.lower()] = role
                vanity_role_ids.add(role.id)
        
        combined_status, has_server_invite = await self.check_member_bio_and_status(interaction.user, str(interaction.guild.id))
        current_vanity_roles = {role for role in interaction.user.roles if role.id in vanity_role_ids}
        
        should_have_roles_dict = self.apply_vanity_settings(
            str(interaction.guild.id), combined_status, role_objects, has_server_invite
        )
        should_have_roles = set(should_have_roles_dict.keys())
        
        roles_to_add = should_have_roles - current_vanity_roles
        roles_to_remove = current_vanity_roles - should_have_roles
        
        changes_made = []
        
        for role in roles_to_add:
            trigger_text = should_have_roles_dict.get(role, "Unknown")
            await self._safe_add_role(
                interaction.user, role,
                f"Manual check - trigger: {trigger_text}",
                str(interaction.guild.id), trigger_text
            )
            changes_made.append(f"✅ Added: {role.mention}")
        
        for role in roles_to_remove:
            await self._safe_remove_role(
                interaction.user, role,
                "Manual check - no longer matches",
                str(interaction.guild.id), "Manual removal"
            )
            changes_made.append(f"❌ Removed: {role.mention}")
        
        if changes_made:
            await interaction.followup.send(
                "**Vanity roles updated:**\n" + "\n".join(changes_made),
                ephemeral=True
            )
        else:
            await interaction.followup.send("✅ Your vanity roles are already up to date.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(Vanity(bot))

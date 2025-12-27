import discord
from discord.ext import commands
from discord import app_commands
import logging
import inspect

logger = logging.getLogger(__name__)


# --- Helper Functions ---

def get_config_color(bot, key: str, fallback: int = 0x5865F2) -> int:
    """Safely retrieves a color from the bot config."""
    try:
        return int(bot.bot_config['ui_settings'][key], 16)
    except (AttributeError, KeyError, ValueError):
        return fallback


def parse_command_parameters(command: app_commands.Command) -> list:
    """Analyzes a command's parameters for display in the help embed."""
    params = []
    
    if hasattr(command, '__discord_app_commands_group__') and command.parameters:
        param_list = command.parameters
    elif hasattr(command.callback, '__signature__'):
        sig = inspect.signature(command.callback)
        param_list = list(sig.parameters.values())[2:]
    else:
        return []

    for param in param_list:
        param_name = param.name
        param_type = "str"
        param_description = ""
        
        if hasattr(command, '__discord_app_commands_group__'):
            app_param = next((p for p in command.parameters if p.name == param_name), None)
            if app_param:
                param_type = app_param.type.name.lower().replace("subcommand", "group")
                param_description = app_param.description
        
        is_required = param.default is inspect.Parameter.empty
        
        if param_type == "str" and param.annotation != inspect.Parameter.empty:
            if hasattr(param.annotation, '__name__'):
                param_type = param.annotation.__name__.lower()
            elif isinstance(param.annotation, str):
                param_type = param.annotation
        
        display_name = f"`{param_name}`"
        
        if is_required:
            param_str = f"**<{display_name}: {param_type}>** - {param_description if param_description else 'Required'}"
        else:
            default_value = f"={param.default}" if param.default not in (None, False, True, inspect.Parameter.empty) else ""
            param_str = f"**[{display_name}{default_value}: {param_type}]** - {param_description if param_description else 'Optional'}"
            
        params.append(param_str)
            
    return params


# --- Views, Modals, and Cogs ---

class HelpView(discord.ui.View):
    def __init__(self, bot, user: discord.User, is_owner: bool = False):
        super().__init__(timeout=300)
        self.bot = bot
        self.user = user
        self.is_owner = is_owner
        self.current_page = "main"
        
        self.add_item(CategorySelect(bot, is_owner))
        self.add_item(CommandSearchButton())

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.user.id:
            await interaction.response.send_message(
                "❌ This help interface is not for you! Use `/help` to get your own.",
                ephemeral=True
            )
            return False
        return True

    async def on_timeout(self):
        for item in self.children:
            item.disabled = True
        try:
            await self.message.edit(view=None)
        except:
            pass
        
    def create_main_embed(self) -> discord.Embed:
        """Create the main help overview embed"""
        embed_color = get_config_color(self.bot, 'embed_color')
        prefix = self.bot.command_prefix
        
        embed = discord.Embed(
            title="🛠️ **Nexora Bot - Help Center**",
            description=f"**Your modular utility bot for comprehensive server management and fun!**\n\n"
                        f"**Prefix:** `{prefix}` | **Slash Commands:** Use `/`",
            color=embed_color
        )
        
        embed.add_field(
            name="🚀 Quick Start Guide",
            value="1️⃣ Use `/serverinfo` for a server health check\n"
                  "2️⃣ Use `/userinfo @member` to inspect a user's details\n"
                  "3️⃣ Use `/analytics` for interactive server stats\n"
                  "4️⃣ Use the dropdown below to explore all commands!",
            inline=False
        )
        
        total_commands = sum(len(cog.get_commands()) + len(cog.get_app_commands()) for cog in self.bot.cogs.values())
        embed.add_field(
            name="📊 Bot Statistics",
            value=f"• **Commands:** {total_commands}\n"
                  f"• **Servers:** {len(self.bot.guilds):,}\n"
                  f"• **Latency:** {round(self.bot.latency * 1000)}ms\n"
                  f"• **Categories:** {len(self.bot.cogs)}",
            inline=True
        )
        
        if self.is_owner:
            embed.description += "\n\n👑 **Owner Mode Active** - All administrative commands visible."
        
        embed.set_footer(text=f"💡 Use the dropdown or the Search button for full command details.")
        
        return embed

    async def create_category_embed(self, category: str) -> discord.Embed:
        """Create category-specific help embed - FIXED VERSION"""
        category_data = {
            "core": {
                "title": "🛠️ Core Utility",
                "description": "Status, ping, and foundational bot commands",
                "cogs": ["status", "help"],
                "color_key": "embed_color"
            },
            "analytics": {
                "title": "📊 Analytics & Info",
                "description": "Server stats, user info, and network health checks",
                "cogs": ["botinfo", "serverinfo", "userinfo", "avatar", "invite", "randomavatar", "analytics", "roleinfo", "channelinfo"],
                "color_key": "success_color"
            },
            "games": {
                "title": "🎮 Games & Fun",
                "description": "Entertainment and interactive commands",
                "cogs": ["gamesstats", "guess", "say", "ship"],
                "color_key": "warning_color"
            },
            "premium": {
                "title": "💎 Premium Features",
                "description": "Premium commands and vanity roles",
                "cogs": ["premium", "vanity"],
                "color_key": "success_color"
            },
            "owner": {
                "title": "👑 Owner Commands",
                "description": "Administrative and owner-only commands",
                "cogs": ["owner"],
                "color_key": "error_color"
            }
        }
        
        data = category_data.get(category, {})
        color = get_config_color(self.bot, data.get("color_key", 'embed_color'))
        
        embed = discord.Embed(
            title=data.get("title", f"📦 {category.title()} Commands"),
            description=data.get("description", f"Commands for {category}"),
            color=color
        )
        
        # FIXED: Better cog matching
        matching_cogs = []
        target_cogs = [c.lower() for c in data.get("cogs", [])]
        
        for cog_name, cog_obj in self.bot.cogs.items():
            normalized_name = cog_name.lower().replace("cog", "").replace("info", "").strip()
            
            if normalized_name in target_cogs or cog_name.lower() in target_cogs:
                matching_cogs.append((cog_name, cog_obj))
        
        command_count = 0
        
        for cog_name, cog_obj in matching_cogs:
            commands_list = []
            
            # Get ALL commands
            all_commands = []
            
            # Hybrid commands
            for cmd in cog_obj.get_commands():
                if isinstance(cmd, commands.HybridCommand) and cmd.parent is None:
                    all_commands.append(cmd)
            
            # App commands (slash only)
            for cmd in cog_obj.get_app_commands():
                if not any(c.name == cmd.name for c in all_commands):
                    all_commands.append(cmd)
            
            for cmd in all_commands:
                # Skip owner commands if not owner
                if not self.is_owner and (hasattr(cmd, 'is_owner') and cmd.is_owner):
                    continue
                
                cmd_desc = cmd.description or "No description available"
                if len(cmd_desc) > 50:
                    cmd_desc = cmd_desc[:47] + "..."
                
                prefix = self.bot.command_prefix
                alias_str = ""
                if hasattr(cmd, 'aliases') and cmd.aliases:
                    alias_str = f" (Aliases: {', '.join(f'{prefix}{a}' for a in cmd.aliases)})"
                
                commands_list.append(f"`/{cmd.name}`{alias_str} - {cmd_desc}")
                command_count += 1
            
            if commands_list:
                display_cog_name = cog_name.replace("Cog", "").replace("Info", "").strip()
                
                max_per_field = 10
                for i in range(0, len(commands_list), max_per_field):
                    chunk = commands_list[i:i + max_per_field]
                    field_name = f"📦 {display_cog_name}" if i == 0 else f"📦 {display_cog_name} (cont.)"
                    embed.add_field(
                        name=field_name,
                        value="\n".join(chunk),
                        inline=False
                    )
        
        if command_count == 0:
            embed.add_field(
                name="No Commands Found",
                value="No accessible commands found in this category.",
                inline=False
            )
        
        embed.set_footer(text=f"Found {command_count} commands. Use the Search button for full details.")
        return embed


class CategorySelect(discord.ui.Select):
    def __init__(self, bot, is_owner: bool = False):
        self.bot = bot
        self.is_owner = is_owner
        
        options = [
            discord.SelectOption(label="🏠 Main Overview", value="main", description="Return to main help page", emoji="🏠"),
            discord.SelectOption(label="🛠️ Core Utility", value="core", description="Status, ping, and foundational commands", emoji="🛠️"),
            discord.SelectOption(label="📊 Analytics & Info", value="analytics", description="Server stats, user info, and network health checks", emoji="📊"),
            discord.SelectOption(label="💎 Premium Features", value="premium", description="Premium commands and vanity roles", emoji="💎"),
            discord.SelectOption(label="🎮 Games & Fun", value="games", description="Entertainment and interactive commands", emoji="🎮"),
        ]
        
        if is_owner:
            options.append(discord.SelectOption(label="👑 Owner Commands", value="owner", description="Owner-only administrative commands", emoji="👑"))
        
        super().__init__(
            placeholder="📋 Choose a category to explore...",
            options=options,
            min_values=1,
            max_values=1
        )

    async def callback(self, interaction: discord.Interaction):
        category = self.values[0]
        await interaction.response.defer()
        
        help_view = self.view
        
        if category == "main":
            embed = help_view.create_main_embed()
        else:
            embed = await help_view.create_category_embed(category)
        
        await interaction.followup.edit_message(interaction.message.id, embed=embed, view=help_view)


class CommandSearchButton(discord.ui.Button):
    def __init__(self):
        super().__init__(
            label="Search Commands",
            style=discord.ButtonStyle.secondary,
            emoji="🔍"
        )

    async def callback(self, interaction: discord.Interaction):
        modal = CommandSearchModal(self.view.bot, self.view.is_owner)
        await interaction.response.send_modal(modal)


class CommandSearchModal(discord.ui.Modal):
    def __init__(self, bot, is_owner: bool):
        super().__init__(title="🔍 Search Commands")
        self.bot = bot
        self.is_owner = is_owner
        
        self.command_input = discord.ui.TextInput(
            label="Command Name",
            placeholder="Type a command name (without /)",
            required=True,
            max_length=100
        )
        self.add_item(self.command_input)

    async def on_submit(self, interaction: discord.Interaction):
        command_name = self.command_input.value.lower().strip()
        
        found_command = None
        matches = []
        
        for cog in self.bot.cogs.values():
            for cmd in cog.get_commands() + cog.get_app_commands():
                if isinstance(cmd, (commands.HybridCommand, app_commands.Command)):
                    if not self.is_owner and (hasattr(cmd, 'is_owner') and cmd.is_owner):
                        continue
                        
                    if cmd.name.lower() == command_name:
                        found_command = cmd
                        break
                    if command_name in cmd.name.lower():
                        matches.append(cmd)
            if found_command:
                break
        
        if found_command:
            embed = await self.create_command_embed(found_command)
        elif matches:
            match_list = ", ".join([f"`/{cmd.name}`" for cmd in matches[:5]])
            if len(matches) > 5:
                match_list += f" and {len(matches)-5} more..."
            
            embed_color = get_config_color(self.bot, 'warning_color', 0xf39c12)
            embed = discord.Embed(
                title="🔍 Command Search Results",
                description=f"Command `/{command_name}` not found.\n\n"
                            f"**Similar commands:** {match_list}",
                color=embed_color
            )
        else:
            embed_color = get_config_color(self.bot, 'error_color', 0xe74c3c)
            embed = discord.Embed(
                title="❌ Command Not Found",
                description=f"No command found matching `/{command_name}`.",
                color=embed_color
            )
            
        await interaction.response.send_message(embed=embed, ephemeral=True)

    async def create_command_embed(self, command) -> discord.Embed:
        """Create detailed command information embed"""
        embed_color = get_config_color(self.bot, 'success_color', 0x00ff00)

        embed = discord.Embed(
            title=f"📖 Command: /{command.name}",
            description=command.description or "No description available",
            color=embed_color
        )
        
        if command.cog:
            embed.add_field(name="📦 Category", value=command.cog.qualified_name.replace("Cog", "").replace("Info", ""), inline=True)
            
        if hasattr(command, 'aliases') and command.aliases:
            prefix = self.bot.command_prefix
            alias_list = ", ".join(f"`{prefix}{a}`" for a in command.aliases)
            embed.add_field(name="🏷️ Aliases", value=alias_list, inline=True)

        params = parse_command_parameters(command)
        
        if params:
            embed.add_field(
                name="📝 Parameters",
                value="\n".join(params),
                inline=False
            )
            
        usage_examples = {
            "avatar": "• `/avatar` - View your own avatar\n• `/avatar @user` - View someone else's avatar",
            "serverinfo": "• `/serverinfo` - Get general server statistics",
            "botinfo": "• `/botinfo` - Check bot's internal status",
            "ping": "• `/ping` - Check bot latency",
            "vanity_test": "• `/vanity_test` - Check your status for vanity roles",
            "guess": "• `/guess number` - Start a guessing game",
            "ship": "• `/ship @user1 @user2` - Ship two users together"
        }
        
        if command.name in usage_examples:
            embed.add_field(
                name="💡 Usage Examples",
                value=usage_examples[command.name],
                inline=False
            )
        
        embed.set_footer(text="💡 Parameters in **<bold brackets>** are required, **[bold brackets]** are optional.")
        return embed


class Help(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def is_bot_owner_check(self, user: discord.User) -> bool:
        """Centralized owner check"""
        try:
            return await self.bot.is_owner(user)
        except Exception:
            return False

    @commands.hybrid_command(name="help", description="Interactive help system with categories and search")
    @app_commands.describe(command="Get detailed help for a specific command")
    async def help(self, ctx: commands.Context, command: str = None):
        """Enhanced interactive help command"""
        
        is_owner = await self.is_bot_owner_check(ctx.author)

        if command:
            modal_search = CommandSearchModal(self.bot, is_owner)
            
            found_command = None
            for cog in self.bot.cogs.values():
                for cmd in cog.get_commands() + cog.get_app_commands():
                    if isinstance(cmd, (commands.HybridCommand, app_commands.Command)) and cmd.name.lower() == command.lower():
                        found_command = cmd
                        break
                if found_command:
                    break
            
            if found_command:
                embed = await modal_search.create_command_embed(found_command)
                await ctx.send(embed=embed, ephemeral=True)
            else:
                embed_color = get_config_color(self.bot, 'error_color', 0xe74c3c)
                embed = discord.Embed(
                    title="❌ Command Not Found",
                    description=f"Command `/{command}` was not found. Try `/help` for the full list.",
                    color=embed_color
                )
                await ctx.send(embed=embed, ephemeral=True)
            return
        
        view = HelpView(self.bot, ctx.author, is_owner)
        embed = view.create_main_embed()
        message = await ctx.send(embed=embed, view=view)
        view.message = message


async def setup(bot):
    await bot.add_cog(Help(bot))

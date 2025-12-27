import discord
from discord.ext import commands
import traceback
import sys
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ErrorHandler(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        bot.tree.on_error = self.on_app_command_error
    
    def create_error_embed(self, title: str, description: str, error_type: str = None) -> discord.Embed:
        """Create a standardized error embed"""
        embed = discord.Embed(
            title=f"❌ {title}",
            description=description,
            color=discord.Color.red(),
            timestamp=datetime.now()
        )
        if error_type:
            embed.set_footer(text=f"Error Type: {error_type}")
        return embed
    
    async def send_error(self, ctx_or_interaction, embed: discord.Embed):
        """Send error message to user"""
        try:
            if isinstance(ctx_or_interaction, commands.Context):
                await ctx_or_interaction.send(embed=embed, ephemeral=True)
            elif isinstance(ctx_or_interaction, discord.Interaction):
                if ctx_or_interaction.response.is_done():
                    await ctx_or_interaction.followup.send(embed=embed, ephemeral=True)
                else:
                    await ctx_or_interaction.response.send_message(embed=embed, ephemeral=True)
        except:
            pass
    
    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Handle errors for prefix commands"""
        
        # Ignore if command has local error handler
        if hasattr(ctx.command, 'on_error'):
            return
        
        # Get the original error
        error = getattr(error, 'original', error)
        
        # Command not found - ignore silently
        if isinstance(error, commands.CommandNotFound):
            return
        
        # Missing permissions
        elif isinstance(error, commands.MissingPermissions):
            missing_perms = ", ".join([f"`{perm}`" for perm in error.missing_permissions])
            embed = self.create_error_embed(
                "Missing Permissions",
                f"You need the following permissions to use this command:\n{missing_perms}",
                "MissingPermissions"
            )
            await self.send_error(ctx, embed)
        
        # Bot missing permissions
        elif isinstance(error, commands.BotMissingPermissions):
            missing_perms = ", ".join([f"`{perm}`" for perm in error.missing_permissions])
            embed = self.create_error_embed(
                "Bot Missing Permissions",
                f"I need the following permissions to execute this command:\n{missing_perms}\n\nPlease ask a server administrator to grant these permissions.",
                "BotMissingPermissions"
            )
            await self.send_error(ctx, embed)
        
        # Missing required argument
        elif isinstance(error, commands.MissingRequiredArgument):
            embed = self.create_error_embed(
                "Missing Argument",
                f"You're missing the required argument: `{error.param.name}`\n\nUsage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
                "MissingRequiredArgument"
            )
            await self.send_error(ctx, embed)
        
        # Bad argument
        elif isinstance(error, commands.BadArgument):
            embed = self.create_error_embed(
                "Invalid Argument",
                f"Invalid argument provided: {str(error)}\n\nUsage: `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
                "BadArgument"
            )
            await self.send_error(ctx, embed)
        
        # Command on cooldown
        elif isinstance(error, commands.CommandOnCooldown):
            embed = self.create_error_embed(
                "Command On Cooldown",
                f"This command is on cooldown. Try again in **{error.retry_after:.1f}** seconds.",
                "CommandOnCooldown"
            )
            await self.send_error(ctx, embed)
        
        # Not owner
        elif isinstance(error, commands.NotOwner):
            embed = self.create_error_embed(
                "Owner Only",
                "This command can only be used by the bot owner.",
                "NotOwner"
            )
            await self.send_error(ctx, embed)
        
        # Check failure
        elif isinstance(error, commands.CheckFailure):
            embed = self.create_error_embed(
                "Check Failed",
                "You don't have permission to use this command.",
                "CheckFailure"
            )
            await self.send_error(ctx, embed)
        
        # Disabled command
        elif isinstance(error, commands.DisabledCommand):
            embed = self.create_error_embed(
                "Command Disabled",
                f"The command `{ctx.command}` is currently disabled.",
                "DisabledCommand"
            )
            await self.send_error(ctx, embed)
        
        # Discord HTTP exception
        elif isinstance(error, discord.HTTPException):
            embed = self.create_error_embed(
                "Discord API Error",
                f"An error occurred while communicating with Discord: {str(error)}",
                "HTTPException"
            )
            await self.send_error(ctx, embed)
        
        # Forbidden (403)
        elif isinstance(error, discord.Forbidden):
            embed = self.create_error_embed(
                "Permission Denied",
                "I don't have permission to perform this action. Please check my role permissions and position in the role hierarchy.",
                "Forbidden"
            )
            await self.send_error(ctx, embed)
        
        # Not found (404)
        elif isinstance(error, discord.NotFound):
            embed = self.create_error_embed(
                "Not Found",
                "The requested resource was not found. It may have been deleted.",
                "NotFound"
            )
            await self.send_error(ctx, embed)
        
        # Generic error
        else:
            embed = self.create_error_embed(
                "Unexpected Error",
                f"An unexpected error occurred while executing the command.\n\n``````",
                type(error).__name__
            )
            await self.send_error(ctx, embed)
            
            # Log full traceback
            logger.error(f"Unhandled error in command {ctx.command}:")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    
    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Handle errors for slash commands"""
        
        # Get the original error
        error = getattr(error, 'original', error)
        
        # Missing permissions
        if isinstance(error, discord.app_commands.MissingPermissions):
            missing_perms = ", ".join([f"`{perm}`" for perm in error.missing_permissions])
            embed = self.create_error_embed(
                "Missing Permissions",
                f"You need the following permissions to use this command:\n{missing_perms}",
                "MissingPermissions"
            )
            await self.send_error(interaction, embed)
        
        # Bot missing permissions
        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            missing_perms = ", ".join([f"`{perm}`" for perm in error.missing_permissions])
            embed = self.create_error_embed(
                "Bot Missing Permissions",
                f"I need the following permissions to execute this command:\n{missing_perms}\n\nPlease ask a server administrator to grant these permissions.",
                "BotMissingPermissions"
            )
            await self.send_error(interaction, embed)
        
        # Command on cooldown
        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            embed = self.create_error_embed(
                "Command On Cooldown",
                f"This command is on cooldown. Try again in **{error.retry_after:.1f}** seconds.",
                "CommandOnCooldown"
            )
            await self.send_error(interaction, embed)
        
        # Check failure
        elif isinstance(error, discord.app_commands.CheckFailure):
            embed = self.create_error_embed(
                "Check Failed",
                "You don't have permission to use this command.",
                "CheckFailure"
            )
            await self.send_error(interaction, embed)
        
        # Discord HTTP exception
        elif isinstance(error, discord.HTTPException):
            embed = self.create_error_embed(
                "Discord API Error",
                f"An error occurred while communicating with Discord: {str(error)}",
                "HTTPException"
            )
            await self.send_error(interaction, embed)
        
        # Forbidden (403)
        elif isinstance(error, discord.Forbidden):
            embed = self.create_error_embed(
                "Permission Denied",
                "I don't have permission to perform this action. Please check my role permissions and position in the role hierarchy.",
                "Forbidden"
            )
            await self.send_error(interaction, embed)
        
        # Not found (404)
        elif isinstance(error, discord.NotFound):
            embed = self.create_error_embed(
                "Not Found",
                "The requested resource was not found. It may have been deleted.",
                "NotFound"
            )
            await self.send_error(interaction, embed)
        
        # Attribute Error (like the one you had)
        elif isinstance(error, AttributeError):
            embed = self.create_error_embed(
                "Internal Error",
                f"An internal error occurred. Please try again or contact support.\n\n``````",
                "AttributeError"
            )
            await self.send_error(interaction, embed)
            logger.error(f"AttributeError in command {interaction.command.name}:")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
        
        # Generic error
        else:
            embed = self.create_error_embed(
                "Unexpected Error",
                f"An unexpected error occurred while executing the command.\n\n``````",
                type(error).__name__
            )
            await self.send_error(interaction, embed)
            
            # Log full traceback
            logger.error(f"Unhandled error in slash command {interaction.command.name}:")
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)
    
    @commands.Cog.listener()
    async def on_error(self, event, *args, **kwargs):
        """Handle errors in events"""
        logger.error(f"Error in event {event}:")
        traceback.print_exc()


async def setup(bot):
    await bot.add_cog(ErrorHandler(bot))

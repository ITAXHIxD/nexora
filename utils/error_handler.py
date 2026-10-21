"""
utils/error_handler.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Error Handler for Prefix & Slash Commands
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import sys
import traceback
from datetime import datetime
from typing import Optional, Union

import discord
from discord.ext import commands

from utils.ui import (
    ERROR_COLOR,
    WARNING_COLOR,
    NexoraView,
    DismissButton,
    send_view,
)

logger = logging.getLogger(__name__)


class ErrorCardView(NexoraView):
    """Sleek Components V2 card for command errors, cooldowns, and permission notices."""

    def __init__(
        self,
        title: str,
        description: str,
        error_type: Optional[str] = None,
        color: int = ERROR_COLOR,
        timeout: float = 60.0,
    ):
        super().__init__(color=color, timeout=timeout)
        self.title = title
        self.description = description
        self.error_type = error_type
        self._build()

    def _build(self):
        self.clear_container()
        header = f"# ❌ {self.title}"
        self.add_text(header)
        self.add_separator(discord.SeparatorSpacing.small)

        body = f"{self.description}"
        if self.error_type:
            body += f"\n\n-# Error Category: `{self.error_type}`"
        self.add_text(body)

        dismiss = DismissButton()
        self.add_row(dismiss)


class ErrorHandler(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        bot.tree.on_error = self.on_app_command_error

    def create_error_view(
        self,
        title: str,
        description: str,
        error_type: Optional[str] = None,
        color: int = ERROR_COLOR,
    ) -> ErrorCardView:
        return ErrorCardView(title=title, description=description, error_type=error_type, color=color)

    async def send_error(
        self,
        target: Union[commands.Context, discord.Interaction],
        view: ErrorCardView,
    ):
        try:
            await send_view(target, view, ephemeral=True)
        except Exception as exc:
            logger.error("Failed to send error view: %s", exc)

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        """Handle errors for prefix commands."""
        if hasattr(ctx.command, "on_error"):
            return

        error = getattr(error, "original", error)

        if isinstance(error, commands.CommandNotFound):
            return

        elif isinstance(error, commands.MissingPermissions):
            missing_perms = " · ".join([f"`{perm}`" for perm in error.missing_permissions])
            view = self.create_error_view(
                "Missing Permissions",
                f"> You lack required permissions to execute `{ctx.command}`.\n\n"
                f"**Required:** {missing_perms}",
                "MissingPermissions",
            )
            await self.send_error(ctx, view)

        elif isinstance(error, commands.BotMissingPermissions):
            missing_perms = " · ".join([f"`{perm}`" for perm in error.missing_permissions])
            view = self.create_error_view(
                "Bot Missing Permissions",
                f"> Nexora lacks permissions to complete this action.\n\n"
                f"**Please grant:** {missing_perms}",
                "BotMissingPermissions",
            )
            await self.send_error(ctx, view)

        elif isinstance(error, commands.MissingRequiredArgument):
            view = self.create_error_view(
                "Missing Argument",
                f"> Missing required parameter: `{error.param.name}`\n\n"
                f"**Usage:** `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
                "MissingRequiredArgument",
            )
            await self.send_error(ctx, view)

        elif isinstance(error, commands.BadArgument):
            view = self.create_error_view(
                "Invalid Argument",
                f"> {str(error)}\n\n"
                f"**Usage:** `{ctx.prefix}{ctx.command.qualified_name} {ctx.command.signature}`",
                "BadArgument",
            )
            await self.send_error(ctx, view)

        elif isinstance(error, commands.CommandOnCooldown):
            view = self.create_error_view(
                "Command On Cooldown",
                f"> Please slow down! You can use `{ctx.command}` again in **{error.retry_after:.1f}s**.",
                "CommandOnCooldown",
                color=WARNING_COLOR,
            )
            await self.send_error(ctx, view)

        elif isinstance(error, commands.NotOwner):
            view = self.create_error_view(
                "Owner Restricted",
                "> This command is restricted to the bot owner.",
                "NotOwner",
            )
            await self.send_error(ctx, view)

        elif isinstance(error, commands.CheckFailure):
            view = self.create_error_view(
                "Access Denied",
                "> You do not meet the criteria or permissions to run this command.",
                "CheckFailure",
            )
            await self.send_error(ctx, view)

        elif isinstance(error, discord.Forbidden):
            view = self.create_error_view(
                "Permission Denied by Discord",
                "> I do not have permission to perform this action. Check role hierarchy and channel permissions.",
                "Forbidden",
            )
            await self.send_error(ctx, view)

        else:
            view = self.create_error_view(
                "Unexpected Error",
                f"> An unexpected error occurred while running `{ctx.command}`.\n"
                f"```py\n{str(error)[:300]}\n```",
                type(error).__name__,
            )
            await self.send_error(ctx, view)
            logger.error("Unhandled error in command %s:", ctx.command)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

            if hasattr(self.bot, "send_support_log"):
                try:
                    await self.bot.send_support_log(
                        title="⚠️ Unhandled Prefix Command Error",
                        description=f"Command `{ctx.command}` failed during execution.",
                        color=ERROR_COLOR,
                        fields=[
                            {"name": "Command", "value": f"`{ctx.command}`", "inline": True},
                            {"name": "Author", "value": f"{ctx.author} (`{ctx.author.id}`)", "inline": True},
                            {"name": "Server", "value": f"{ctx.guild.name if ctx.guild else 'DMs'} (`{ctx.guild.id if ctx.guild else 'N/A'}`)", "inline": True},
                            {"name": "Exception", "value": f"```{type(error).__name__}: {str(error)[:250]}```", "inline": False},
                        ],
                    )
                except Exception as exc:
                    logger.debug("Error sending support log: %s", exc)

    async def on_app_command_error(self, interaction: discord.Interaction, error: discord.app_commands.AppCommandError):
        """Handle errors for slash commands."""
        error = getattr(error, "original", error)

        if isinstance(error, discord.app_commands.MissingPermissions):
            missing_perms = " · ".join([f"`{perm}`" for perm in error.missing_permissions])
            view = self.create_error_view(
                "Missing Permissions",
                f"> You lack required permissions to run this command.\n\n"
                f"**Required:** {missing_perms}",
                "MissingPermissions",
            )
            await self.send_error(interaction, view)

        elif isinstance(error, discord.app_commands.BotMissingPermissions):
            missing_perms = " · ".join([f"`{perm}`" for perm in error.missing_permissions])
            view = self.create_error_view(
                "Bot Missing Permissions",
                f"> Nexora lacks required permissions in this server/channel.\n\n"
                f"**Please grant:** {missing_perms}",
                "BotMissingPermissions",
            )
            await self.send_error(interaction, view)

        elif isinstance(error, discord.app_commands.CommandOnCooldown):
            view = self.create_error_view(
                "Command On Cooldown",
                f"> Please wait **{error.retry_after:.1f}s** before using this command again.",
                "CommandOnCooldown",
                color=WARNING_COLOR,
            )
            await self.send_error(interaction, view)

        elif isinstance(error, discord.app_commands.CheckFailure):
            view = self.create_error_view(
                "Access Denied",
                "> You do not meet the permission criteria to execute this command.",
                "CheckFailure",
            )
            await self.send_error(interaction, view)

        elif isinstance(error, discord.Forbidden):
            view = self.create_error_view(
                "Permission Denied",
                "> Discord rejected this action due to missing permissions or role hierarchy constraints.",
                "Forbidden",
            )
            await self.send_error(interaction, view)

        elif isinstance(error, discord.NotFound) and getattr(error, "code", None) == 10062:
            logger.warning("Interaction expired or was handled by another instance (code 10062: Unknown interaction).")
            return

        else:
            cmd_name = interaction.command.name if interaction.command else "Unknown"
            view = self.create_error_view(
                "Command Execution Error",
                f"> An error occurred while executing `/{cmd_name}`.\n"
                f"```py\n{str(error)[:300]}\n```",
                type(error).__name__,
            )
            await self.send_error(interaction, view)
            logger.error("Unhandled error in slash command %s:", cmd_name)
            traceback.print_exception(type(error), error, error.__traceback__, file=sys.stderr)

            if hasattr(self.bot, "send_support_log"):
                try:
                    await self.bot.send_support_log(
                        title="⚠️ Unhandled Slash Command Error",
                        description=f"Slash command `/{cmd_name}` failed during execution.",
                        color=ERROR_COLOR,
                        fields=[
                            {"name": "Command", "value": f"`/{cmd_name}`", "inline": True},
                            {"name": "Author", "value": f"{interaction.user} (`{interaction.user.id}`)", "inline": True},
                            {"name": "Server", "value": f"{interaction.guild.name if interaction.guild else 'DMs'} (`{interaction.guild.id if interaction.guild else 'N/A'}`)", "inline": True},
                            {"name": "Exception", "value": f"```{type(error).__name__}: {str(error)[:250]}```", "inline": False},
                        ],
                    )
                except Exception as exc:
                    logger.debug("Error sending support log: %s", exc)


async def setup(bot: commands.Bot):
    await bot.add_cog(ErrorHandler(bot))

"""
scratch/test_logging_and_activities.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Verification suite for logging cleanup, webhook support, server audit
engine, expanded dynamic activities, and terminal ASCII dashboard.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import os
import sys
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

# Ensure project root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import bot as bot_module
from cogs.moderation.mod_utils import log_mod_action
from cogs.moderation.server_logs import ServerLogs, AUTO_DETECT_LOG_NAMES


class TestLoggingAndActivities(unittest.IsolatedAsyncioTestCase):

    def test_creative_activities_pool(self):
        """Verify activity pool size, valid types, and formatting."""
        activities = bot_module.CREATIVE_ACTIVITIES
        self.assertGreaterEqual(len(activities), 50, f"Expected at least 50 activities, found {len(activities)}")

        # Verify all activities format cleanly with placeholders
        for idx, act in enumerate(activities):
            self.assertIn("type", act)
            self.assertIn("name", act)
            self.assertIsInstance(act["type"], discord.ActivityType)
            
            # Format test
            try:
                formatted = act["name"].format(
                    server_count=42,
                    user_count=1337,
                    channel_count=100,
                    random_ep=1050,
                )
                self.assertIsInstance(formatted, str)
                self.assertGreater(len(formatted), 0)
            except Exception as e:
                self.fail(f"Activity #{idx} ('{act['name']}') failed placeholder formatting: {e}")

    async def test_get_dynamic_activity(self):
        """Verify get_dynamic_activity generates valid Discord activity objects."""
        mock_bot = bot_module.CharacterBot()
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.member_count = 500
        mock_bot._guilds = {1: mock_guild}
        
        # Test 20 random generations
        for _ in range(20):
            activity = await mock_bot.get_dynamic_activity()
            self.assertIsNotNone(activity)
            self.assertIsNotNone(activity.name)
            self.assertTrue(len(activity.name) > 0)

    async def test_server_logs_storage_and_resolver(self):
        """Verify server log configuration, caching, and auto-detection."""
        mock_bot = MagicMock()
        mock_bot.mongo_db = None  # test local JSON fallback
        cog = ServerLogs(mock_bot)

        test_guild_id = 9999988888
        test_channel_id = 1234567890

        # Set configured channel
        await cog.set_configured_channel_id(test_guild_id, test_channel_id)
        fetched = await cog.get_configured_channel_id(test_guild_id)
        self.assertEqual(fetched, test_channel_id)

        # Build mock guild
        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.id = test_guild_id
        mock_channel = MagicMock(spec=discord.TextChannel)
        mock_channel.id = test_channel_id
        mock_perms = MagicMock()
        mock_perms.send_messages = True
        mock_perms.embed_links = True
        mock_channel.permissions_for.return_value = mock_perms
        mock_guild.get_channel.return_value = mock_channel
        mock_guild.text_channels = [mock_channel]

        # Resolve explicit channel
        resolved = await cog.get_log_channel(mock_guild)
        self.assertEqual(resolved, mock_channel)

        # Clear configured channel & test auto-detection by name
        await cog.set_configured_channel_id(test_guild_id, None)
        auto_channel = MagicMock(spec=discord.TextChannel)
        auto_channel.name = "mod-logs"
        auto_channel.permissions_for.return_value = mock_perms
        mock_guild.get_channel.return_value = None
        mock_guild.text_channels = [auto_channel]

        resolved_auto = await cog.get_log_channel(mock_guild)
        self.assertEqual(resolved_auto, auto_channel)

    async def test_log_mod_action_dispatch(self):
        """Verify log_mod_action builds embed and delivers to guild log channel."""
        mock_bot = MagicMock()
        mock_cog = MagicMock()
        mock_log_channel = AsyncMock(spec=discord.TextChannel)
        mock_cog.get_log_channel = AsyncMock(return_value=mock_log_channel)
        mock_bot.get_cog.return_value = mock_cog

        mock_guild = MagicMock(spec=discord.Guild)
        mock_guild.name = "Nexora Realm"
        mock_target = MagicMock(spec=discord.Member)
        mock_target.name = "Troublemaker"
        mock_target.id = 111222333
        mock_target.mention = "<@111222333>"
        mock_target.display_avatar.url = "https://example.com/avatar.png"

        mock_mod = MagicMock(spec=discord.Member)
        mock_mod.name = "Admin"
        mock_mod.mention = "<@444555666>"

        # Dispatch ban audit
        await log_mod_action(
            guild=mock_guild,
            action="ban",
            target=mock_target,
            moderator=mock_mod,
            reason="Violation of Rule 1",
            bot=mock_bot,
        )

        mock_log_channel.send.assert_called_once()
        call_args = mock_log_channel.send.call_args
        embed = call_args.kwargs.get("embed")
        self.assertIsNotNone(embed)
        self.assertIn("Ban", embed.title)
        self.assertEqual(embed.fields[0].name, "👤 Target")

    async def test_send_support_log(self):
        """Verify bot.send_support_log sends without throwing."""
        mock_bot = bot_module.CharacterBot()
        mock_bot.session = MagicMock()
        mock_bot.session.closed = False
        mock_bot.log_channel = AsyncMock(spec=discord.TextChannel)

        await mock_bot.send_support_log(
            title="Test Event",
            description="System operational",
            fields=[{"name": "Status", "value": "OK"}],
        )

        mock_bot.log_channel.send.assert_called_once()


if __name__ == "__main__":
    unittest.main()

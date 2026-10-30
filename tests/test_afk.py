"""
tests/test_afk.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unit test suite for Nexora AFK System.
Tests mention alerts in message form, reply references, grace period,
and caching resilience.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import datetime
import os
import shutil
import tempfile
import time
import unittest
from unittest.mock import AsyncMock, MagicMock, patch

import discord

from cogs.utility.afk import AFK, _load_afk_local, _save_afk_local


class TestAFKSystem(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "afk_test.json")
        self.file_patcher = patch("cogs.utility.afk.AFK_DATA_FILE", self.test_file)
        self.file_patcher.start()

        self.bot = MagicMock()
        self.bot.user = MagicMock(id=999999999)
        self.bot.mongo_db = None

        self.afk_cog = AFK(self.bot)
        await self.afk_cog.cog_load()

    async def asyncTearDown(self):
        self.file_patcher.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    async def test_set_and_get_afk_default_global(self):
        """Verify setting AFK defaults to global and saves to cache."""
        member = MagicMock(spec=discord.Member)
        member.id = 123456789
        member.name = "testuser"
        member.display_name = "TestUser"
        member.nick = None
        member.edit = AsyncMock()

        guild = MagicMock(spec=discord.Guild)
        guild.id = 987654321
        guild.name = "Test Server"

        send_fn = AsyncMock()

        ctx = MagicMock()
        ctx.author = member
        ctx.guild = guild
        ctx.send = AsyncMock()

        # Invoke afk_prefix with reason
        await self.afk_cog.afk_prefix.callback(self.afk_cog, ctx, reason="eating lunch")

        # Check in memory and local
        data = await self.afk_cog.get_afk(member.id)
        self.assertIsNotNone(data)
        self.assertEqual(data["reason"], "eating lunch")
        self.assertTrue(data["global"])
        self.assertIn(member.id, self.afk_cog.active_afk_cache)

    async def test_grace_period_prevents_afk_removal(self):
        """Verify author speaking within 10s grace period does NOT clear AFK."""
        member = MagicMock(spec=discord.Member)
        member.id = 111222333
        member.name = "busybee"
        member.display_name = "BusyBee"
        member.nick = None
        member.bot = False
        member.edit = AsyncMock()

        guild = MagicMock(spec=discord.Guild)
        guild.id = 555
        guild.name = "Hive"

        # Set AFK now
        await self.afk_cog.set_afk(member.id, {
            "reason": "stepping away",
            "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "name": "BusyBee",
            "global": True,
            "guild_id": None,
            "mentions": [],
        })

        # Send a message 2 seconds later (within 10s grace period)
        msg = MagicMock(spec=discord.Message)
        msg.author = member
        msg.guild = guild
        msg.content = "bye everyone!"
        msg.channel = MagicMock()
        msg.channel.send = AsyncMock()
        msg.mentions = []
        msg.reference = None

        await self.afk_cog.on_message(msg)

        # Still AFK!
        self.assertIn(member.id, self.afk_cog.active_afk_cache)
        self.assertIsNotNone(await self.afk_cog.get_afk(member.id))
        msg.channel.send.assert_not_called()

    async def test_speaking_after_grace_period_removes_afk(self):
        """Verify author speaking after grace period clears AFK and welcomes back."""
        member = MagicMock(spec=discord.Member)
        member.id = 222333444
        member.name = "returnee"
        member.display_name = "Returnee"
        member.nick = None
        member.bot = False
        member.edit = AsyncMock()

        guild = MagicMock(spec=discord.Guild)
        guild.id = 777
        guild.name = "Return Guild"

        # Set AFK timestamp 30 seconds ago
        past_time = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
        await self.afk_cog.set_afk(member.id, {
            "reason": "afk test",
            "time": past_time.isoformat(),
            "name": "Returnee",
            "global": True,
            "guild_id": None,
            "mentions": [],
        })
        self.afk_cog._set_timestamps[member.id] = time.time() - 30.0

        msg = MagicMock(spec=discord.Message)
        msg.author = member
        msg.guild = guild
        msg.content = "I am back now"
        msg.channel = MagicMock()
        msg.channel.send = AsyncMock()
        msg.mentions = []
        msg.reference = None

        await self.afk_cog.on_message(msg)

        # Removed from AFK!
        self.assertNotIn(member.id, self.afk_cog.active_afk_cache)
        msg.channel.send.assert_called_once()

    async def test_ping_afk_member_replies_in_message_form(self):
        """Verify pinging an AFK user triggers a reply in clean message form."""
        afk_user = MagicMock(spec=discord.Member)
        afk_user.id = 333444555
        afk_user.name = "sleepy"
        afk_user.display_name = "SleepyHead"
        afk_user.bot = False
        afk_user.send = AsyncMock()

        pinger = MagicMock(spec=discord.Member)
        pinger.id = 999888777
        pinger.name = "curious"
        pinger.display_name = "CuriousUser"
        pinger.bot = False

        guild = MagicMock(spec=discord.Guild)
        guild.id = 888
        guild.name = "Community"
        guild.get_member = MagicMock(return_value=afk_user)

        # Seed AFK user
        past_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(minutes=15)
        await self.afk_cog.set_afk(afk_user.id, {
            "reason": "taking a nap",
            "time": past_dt.isoformat(),
            "name": "SleepyHead",
            "global": True,
            "guild_id": None,
            "mentions": [],
            "dm_notifications": True,
        })

        # Pinger sends a message mentioning the AFK user
        msg = MagicMock(spec=discord.Message)
        msg.author = pinger
        msg.guild = guild
        msg.content = f"Hey <@{afk_user.id}> are you awake?"
        msg.mentions = [afk_user]
        msg.reference = None
        msg.channel = MagicMock()
        msg.channel.name = "general"
        msg.jump_url = "https://discord.com/channels/888/111/222"
        msg.reply = AsyncMock()

        await self.afk_cog.on_message(msg)

        # Must reply to pinger in message form with mention_author=False
        msg.reply.assert_called_once()
        call_args, call_kwargs = msg.reply.call_args
        reply_text = call_args[0]

        # Validate message form content
        self.assertIn("💤 **SleepyHead** is AFK: taking a nap", reply_text)
        self.assertIn("<t:", reply_text)
        self.assertEqual(call_kwargs.get("mention_author"), False)

    async def test_reply_to_afk_member_triggers_reply(self):
        """Verify replying to an AFK user's message (even without ping) alerts pinger."""
        afk_user = MagicMock(spec=discord.Member)
        afk_user.id = 444555666
        afk_user.name = "studying"
        afk_user.display_name = "StudyMode"
        afk_user.bot = False
        afk_user.send = AsyncMock()

        pinger = MagicMock(spec=discord.Member)
        pinger.id = 111999888
        pinger.name = "friend"
        pinger.display_name = "Friend"
        pinger.bot = False

        guild = MagicMock(spec=discord.Guild)
        guild.id = 999
        guild.name = "Study Hall"
        guild.get_member = MagicMock(return_value=afk_user)

        past_dt = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=1)
        await self.afk_cog.set_afk(afk_user.id, {
            "reason": "exam prep",
            "time": past_dt.isoformat(),
            "name": "StudyMode",
            "global": True,
            "guild_id": None,
            "mentions": [],
            "dm_notifications": False,
        })

        # Referenced message authored by afk_user
        ref_message = MagicMock(spec=discord.Message)
        ref_message.author = afk_user
        ref_message.id = 12345

        # Pinger replies without mention
        msg = MagicMock(spec=discord.Message)
        msg.author = pinger
        msg.guild = guild
        msg.content = "Can you send the notes?"
        msg.mentions = []  # No ping in mentions!
        msg.reference = MagicMock()
        msg.reference.resolved = ref_message
        msg.channel = MagicMock()
        msg.channel.name = "classroom"
        msg.jump_url = "https://discord.com/channels/999/222/333"
        msg.reply = AsyncMock()

        await self.afk_cog.on_message(msg)

        msg.reply.assert_called_once()
        call_args, call_kwargs = msg.reply.call_args
        reply_text = call_args[0]
        self.assertIn("💤 **StudyMode** is AFK: exam prep", reply_text)

    async def test_reply_fallback_to_channel_send(self):
        """Verify if message.reply fails, fallback to message.channel.send occurs."""
        afk_user = MagicMock(spec=discord.Member)
        afk_user.id = 555666777
        afk_user.name = "coder"
        afk_user.display_name = "CodeNinja"
        afk_user.bot = False
        afk_user.send = AsyncMock()

        pinger = MagicMock(spec=discord.Member)
        pinger.id = 888777666
        pinger.name = "reviewer"
        pinger.display_name = "Reviewer"
        pinger.bot = False

        guild = MagicMock(spec=discord.Guild)
        guild.id = 123
        guild.name = "Dev Hub"
        guild.get_member = MagicMock(return_value=afk_user)

        await self.afk_cog.set_afk(afk_user.id, {
            "reason": "coding",
            "time": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "name": "CodeNinja",
            "global": True,
            "guild_id": None,
            "mentions": [],
        })

        msg = MagicMock(spec=discord.Message)
        msg.author = pinger
        msg.guild = guild
        msg.content = "ping <@555666777>"
        msg.mentions = [afk_user]
        msg.reference = None
        msg.channel = MagicMock()
        msg.channel.name = "dev"
        msg.jump_url = "https://discord.com/channels/123/456/789"
        msg.reply = AsyncMock(side_effect=discord.Forbidden(MagicMock(), "Missing Permissions"))
        msg.channel.send = AsyncMock()

        await self.afk_cog.on_message(msg)

        # Fallback channel.send must be called
        msg.channel.send.assert_called_once()
        call_args, _ = msg.channel.send.call_args
        self.assertIn("💤 **CodeNinja** is AFK: coding", call_args[0])


if __name__ == "__main__":
    unittest.main()

"""
Comprehensive test suite for NEXORA Premium and User VIP systems.
Tests entitlement checking, persistence, local fallback, tier limits,
expiry, owner grants, revocations, and slash command registration.
"""

import asyncio
import os
import shutil
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

import bot as bot_module
import utils.premium_storage as prem_storage
from cogs.premium_main import (
    PAID_SERVER_TIERS,
    PAID_USER_TIERS,
    SERVER_TIERS,
    USER_TIERS,
    Premium,
    _is_expired,
    utcnow,
)


class TestPremiumStorage(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_premium_path = prem_storage.PREMIUM_DATA_PATH
        prem_storage.PREMIUM_DATA_PATH = os.path.join(self.test_dir, "premium.json")

    def tearDown(self):
        prem_storage.PREMIUM_DATA_PATH = self.orig_premium_path
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_default_premium_data(self):
        data = prem_storage.default_premium_data()
        self.assertIn("subscriptions", data)
        self.assertIn("user_subscriptions", data)
        self.assertIn("vanity", data)
        self.assertIn("grandfathered", data)

    def test_save_and_load_user_subscriptions(self):
        data = prem_storage.default_premium_data()
        data["user_subscriptions"]["12345"] = {
            "tier": "VIP_PLUS",
            "expires_at": (utcnow() + timedelta(days=30)).isoformat(),
            "server_passes": 1,
            "custom_color": 0x5865F2,
            "badge": "star",
        }
        prem_storage.save_premium_data(data)

        loaded = prem_storage.load_premium_data()
        self.assertIn("12345", loaded["user_subscriptions"])
        self.assertEqual(loaded["user_subscriptions"]["12345"]["tier"], "VIP_PLUS")
        self.assertEqual(loaded["user_subscriptions"]["12345"]["badge"], "star")


class TestPremiumEntitlements(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_premium_path = prem_storage.PREMIUM_DATA_PATH
        prem_storage.PREMIUM_DATA_PATH = os.path.join(self.test_dir, "premium.json")

    def tearDown(self):
        prem_storage.PREMIUM_DATA_PATH = self.orig_premium_path
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_is_expired(self):
        now = utcnow()
        past = now - timedelta(days=1)
        future = now + timedelta(days=1)

        self.assertTrue(_is_expired({"expires_at": past.isoformat()}))
        self.assertFalse(_is_expired({"expires_at": future.isoformat()}))
        self.assertFalse(_is_expired({"expires_at": None}))
        self.assertFalse(_is_expired({}))

    def test_local_fallback_server_and_user_vip(self):
        bot = bot_module.CharacterBot()
        bot.mongo_db = None

        # Initially not premium
        self.assertFalse(bot.is_premium_guild(999999))
        self.assertEqual(bot.get_premium_tier(999999), "FREE")
        self.assertFalse(bot.is_premium_user(888888))
        self.assertEqual(bot.get_user_vip_tier(888888), "FREE")

        # Save server grant to local storage
        data = prem_storage.default_premium_data()
        data["subscriptions"]["999999"] = {
            "tier": "PRO",
            "expires_at": (utcnow() + timedelta(days=30)).isoformat(),
        }
        data["user_subscriptions"]["888888"] = {
            "tier": "VIP_PLUS",
            "expires_at": (utcnow() + timedelta(days=30)).isoformat(),
            "custom_color": 0x00D2FF,
        }
        prem_storage.save_premium_data(data)

        bot.load_premium_guilds()
        self.assertTrue(bot.is_premium_guild(999999))
        self.assertEqual(bot.get_premium_tier(999999), "PRO")
        self.assertTrue(bot.is_premium_user(888888))
        self.assertEqual(bot.get_user_vip_tier(888888), "VIP_PLUS")
        self.assertEqual(bot.get_user_custom_color(888888), 0x00D2FF)


class TestPremiumCogAsync(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.orig_premium_path = prem_storage.PREMIUM_DATA_PATH
        prem_storage.PREMIUM_DATA_PATH = os.path.join(self.test_dir, "premium.json")

        self.bot = bot_module.CharacterBot()
        self.bot.mongo_db = None  # test local fallback
        self.cog = Premium(self.bot)
        await self.cog.cog_load()

    async def asyncTearDown(self):
        self.cog.cog_unload()
        prem_storage.PREMIUM_DATA_PATH = self.orig_premium_path
        shutil.rmtree(self.test_dir, ignore_errors=True)

    async def test_server_grant_and_revoke_local(self):
        ctx = MagicMock()
        ctx.author = SimpleNamespace(id=1013851779886231685, name="Owner")
        ctx.send = AsyncMock()

        # Grant server PRO
        await self.cog.set_premium.callback(self.cog, ctx, guild_id="11223344", tier="PRO", days=30)
        ctx.send.assert_called()
        self.assertTrue(await self.bot.is_premium_guild(11223344))
        self.assertEqual(await self.bot.get_premium_tier(11223344), "PRO")

        # Verify persisted in local storage
        loaded = prem_storage.load_premium_data()
        self.assertEqual(loaded["subscriptions"]["11223344"]["tier"], "PRO")

        # Revoke server PRO
        ctx.send.reset_mock()
        await self.cog.revoke_premium.callback(self.cog, ctx, guild_id="11223344")
        ctx.send.assert_called()
        self.assertFalse(await self.bot.is_premium_guild(11223344))
        self.assertEqual(await self.bot.get_premium_tier(11223344), "FREE")

    async def test_user_vip_grant_and_revoke_local(self):
        ctx = MagicMock()
        ctx.author = SimpleNamespace(id=1013851779886231685, name="Owner")
        ctx.send = AsyncMock()
        target_user = SimpleNamespace(id=556677, mention="<@556677>")

        # Grant user VIP_PLUS
        await self.cog.set_user_vip.callback(self.cog, ctx, user=target_user, tier="VIP_PLUS", days=30)
        ctx.send.assert_called()
        self.assertTrue(await self.bot.is_premium_user(556677))
        self.assertEqual(await self.bot.get_user_vip_tier(556677), "VIP_PLUS")

        # Verify local storage
        loaded = prem_storage.load_premium_data()
        self.assertEqual(loaded["user_subscriptions"]["556677"]["tier"], "VIP_PLUS")
        self.assertEqual(loaded["user_subscriptions"]["556677"]["server_passes"], 1)

        # Revoke user VIP
        ctx.send.reset_mock()
        await self.cog.revoke_user_vip.callback(self.cog, ctx, user=target_user)
        ctx.send.assert_called()
        self.assertFalse(await self.bot.is_premium_user(556677))
        self.assertEqual(await self.bot.get_user_vip_tier(556677), "FREE")

    async def test_slash_command_registration(self):
        # Verify app commands are registered in Premium cog
        app_cmds = {cmd.name: cmd for cmd in self.cog.get_app_commands()}
        self.assertIn("premium", app_cmds)
        self.assertIn("premium_grant", app_cmds)
        self.assertIn("premium_revoke", app_cmds)

        # Verify UserVIP cog registers /vip with grant and revoke subcommands
        from cogs.premium.user_vip import UserVIP
        user_vip_cog = UserVIP(self.bot)
        vip_subcommands = [cmd.name for cmd in user_vip_cog.vip.commands]
        self.assertIn("grant", vip_subcommands)
        self.assertIn("revoke", vip_subcommands)
        self.assertIn("color", vip_subcommands)
        self.assertIn("badge", vip_subcommands)
        self.assertIn("pass", vip_subcommands)


if __name__ == "__main__":
    unittest.main()

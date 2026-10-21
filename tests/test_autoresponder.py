"""
tests/test_autoresponder.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unit and integration test suite for Nexora Autoresponder System.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import os
import shutil
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from utils.autoresponder_engine import (
    AutoResponderEngine,
    AutoResponderItem,
    GuildAutoResponderSettings,
    sanitize_regex,
)
from utils.autoresponder_storage import (
    AutoResponderStorage,
    load_local_autoresponder_data,
    save_local_autoresponder_data,
)


class TestAutoresponderMatching(unittest.TestCase):
    """Test every match mode and trigger matching nuances."""

    def setUp(self):
        self.engine = AutoResponderEngine()

    def test_exact_match(self):
        self.assertTrue(self.engine.match_trigger("ping", "ping", "exact", False))
        self.assertTrue(self.engine.match_trigger("Ping", "PING", "exact", False))
        self.assertFalse(self.engine.match_trigger("ping", "ping pong", "exact", False))
        # Case sensitive
        self.assertTrue(self.engine.match_trigger("Ping", "Ping", "exact", True))
        self.assertFalse(self.engine.match_trigger("Ping", "ping", "exact", True))

    def test_contains_match(self):
        self.assertTrue(self.engine.match_trigger("apple", "I like apples", "contains", False))
        self.assertTrue(self.engine.match_trigger("APPLE", "fresh apple juice", "contains", False))
        self.assertFalse(self.engine.match_trigger("banana", "I like apples", "contains", False))
        # Case sensitive
        self.assertTrue(self.engine.match_trigger("Apple", "Golden Apple", "contains", True))
        self.assertFalse(self.engine.match_trigger("Apple", "golden apple", "contains", True))

    def test_startswith_match(self):
        self.assertTrue(self.engine.match_trigger("!help", "!help me", "startswith", False))
        self.assertFalse(self.engine.match_trigger("!help", "can someone !help me", "startswith", False))

    def test_endswith_match(self):
        self.assertTrue(self.engine.match_trigger("thanks", "Many thanks", "endswith", False))
        self.assertFalse(self.engine.match_trigger("thanks", "thanks a lot", "endswith", False))

    def test_whole_word_match(self):
        self.assertTrue(self.engine.match_trigger("hi", "hi there", "whole_word", False))
        self.assertTrue(self.engine.match_trigger("hi", "say hi", "whole_word", False))
        self.assertTrue(self.engine.match_trigger("hi", "hi", "whole_word", False))
        # 'this' contains 'hi' as substring, but is NOT whole-word 'hi'
        self.assertFalse(self.engine.match_trigger("hi", "this is cool", "whole_word", False))
        self.assertFalse(self.engine.match_trigger("cat", "category", "whole_word", False))
        self.assertFalse(self.engine.match_trigger("cat", "scat", "whole_word", False))

    def test_regex_match(self):
        self.assertTrue(self.engine.match_trigger(r"^order-\d+$", "order-12345", "regex", False))
        self.assertFalse(self.engine.match_trigger(r"^order-\d+$", "order-abc", "regex", False))

    def test_regex_safety_and_redos_prevention(self):
        # Valid pattern
        valid, err = sanitize_regex(r"^hello\s+world$")
        self.assertTrue(valid)
        self.assertIsNone(err)

        # Invalid syntax
        valid, err = sanitize_regex(r"[unclosed bracket")
        self.assertFalse(valid)
        self.assertIn("Invalid regex pattern", err)

        # Catastrophic backtracking: (a+)+
        valid, err = sanitize_regex(r"^(a+)+$")
        self.assertFalse(valid)
        self.assertIn("Dangerous regular expression", err)

        # Excessively long regex
        long_pattern = "a" * 250
        valid, err = sanitize_regex(long_pattern)
        self.assertFalse(valid)
        self.assertIn("exceeds maximum length", err)


class TestAutoresponderVariablesAndEmbeds(unittest.TestCase):
    """Test variable substitution and embed generation."""

    def test_safe_variable_rendering(self):
        msg = SimpleNamespace(
            guild=SimpleNamespace(id=111, name="Nexora Lounge", member_count=42, icon=None),
            author=SimpleNamespace(id=222, display_name="Alice", name="alice_dev", mention="<@222>"),
            channel=SimpleNamespace(id=333, name="general", mention="<#333>"),
            created_at=None,
        )

        template = "Hello {user} ({user.mention})! Welcome to {server} (ID: {server.id}) in {channel}!"
        rendered = AutoResponderEngine.render_variables(template, msg)

        self.assertIn("Hello Alice (<@222>)!", rendered)
        self.assertIn("Welcome to Nexora Lounge (ID: 111)", rendered)
        self.assertIn("in <#333>!", rendered)

    def test_random_variable(self):
        msg = SimpleNamespace(guild=None, author=None, channel=None, created_at=None)
        rendered = AutoResponderEngine.render_variables("Roll: {random:1-6}", msg)
        self.assertTrue(rendered.startswith("Roll: "))
        num = int(rendered.split(": ")[1])
        self.assertTrue(1 <= num <= 6)

    def test_build_embeds(self):
        msg = SimpleNamespace(
            guild=SimpleNamespace(id=111, name="Test Guild", member_count=10, icon=None),
            author=SimpleNamespace(id=222, display_name="Bob", name="bob", mention="<@222>"),
            channel=SimpleNamespace(id=333, name="bot-spam", mention="<#333>"),
            created_at=None,
        )

        raw_embeds = [
            {
                "title": "Welcome {user}",
                "description": "Glad to have you in {server}!",
                "color": "#00FF00",
                "fields": [{"name": "Server ID", "value": "{server.id}", "inline": True}],
            }
        ]

        embeds = AutoResponderEngine.build_embeds(raw_embeds, msg)
        self.assertEqual(len(embeds), 1)
        self.assertEqual(embeds[0].title, "Welcome Bob")
        self.assertEqual(embeds[0].description, "Glad to have you in Test Guild!")
        self.assertEqual(embeds[0].color.value, 0x00FF00)
        self.assertEqual(embeds[0].fields[0].value, "111")


class TestAutoresponderEvaluation(unittest.TestCase):
    """Test exclusions, restrictions, cooldowns, and priority conflict modes."""

    def setUp(self):
        self.engine = AutoResponderEngine()
        self.settings = GuildAutoResponderSettings(enabled=True, conflict_mode="first_match")

    def test_channel_and_role_eligibility(self):
        item = AutoResponderItem(
            id="test1",
            triggers=["hello"],
            channels=[101, 102],
            roles=[201],
            excluded_channels=[102],
            excluded_roles=[202],
        )

        # In excluded channel
        eligible, reason = self.engine.is_eligible(item, self.settings, 102, {201})
        self.assertFalse(eligible)
        self.assertIn("Channel is excluded", reason)

        # In non-allowed channel
        eligible, reason = self.engine.is_eligible(item, self.settings, 103, {201})
        self.assertFalse(eligible)
        self.assertIn("allowed channel list", reason)

        # Has excluded role
        eligible, reason = self.engine.is_eligible(item, self.settings, 101, {201, 202})
        self.assertFalse(eligible)
        self.assertIn("excluded role", reason)

        # Missing required role
        eligible, reason = self.engine.is_eligible(item, self.settings, 101, {999})
        self.assertFalse(eligible)
        self.assertIn("required roles", reason)

        # Fully eligible
        eligible, reason = self.engine.is_eligible(item, self.settings, 101, {201})
        self.assertTrue(eligible)

    def test_priority_and_first_match_conflict_mode(self):
        low_priority = AutoResponderItem(
            id="low",
            name="General Help",
            triggers=["help"],
            match_mode="contains",
            priority=1,
            replies=["General help"],
        )
        high_priority = AutoResponderItem(
            id="high",
            name="Specific Help",
            triggers=["help"],
            match_mode="exact",
            priority=10,
            replies=["Specific help"],
        )

        responders = [low_priority, high_priority]
        matches = self.engine.evaluate_message(
            message_content="help",
            responders=responders,
            settings=self.settings,
            channel_id=1,
            member_role_ids=set(),
            user_id=123,
            guild_id=999,
            dry_run=True,
        )

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0][0].id, "high")

    def test_cooldown_enforcement(self):
        item = AutoResponderItem(
            id="cd_test",
            triggers=["spam"],
            match_mode="exact",
            cooldown_user=5.0,
        )

        # First trigger: OK
        on_cd, _ = self.engine.check_and_apply_cooldown(1, item, 444, 1, dry_run=False)
        self.assertFalse(on_cd)

        # Immediate second trigger: On cooldown
        on_cd, remaining = self.engine.check_and_apply_cooldown(1, item, 444, 1, dry_run=True)
        self.assertTrue(on_cd)
        self.assertGreater(remaining, 0.0)

        # Different user: Not on cooldown
        on_cd, _ = self.engine.check_and_apply_cooldown(1, item, 555, 1, dry_run=True)
        self.assertFalse(on_cd)


class TestAutoresponderStorageAndPersistence(unittest.IsolatedAsyncioTestCase):
    """Test MongoDB and local JSON fallback storage, serialization, and migration."""

    def setUp(self):
        self.tmp_dir = tempfile.mkdtemp()
        self.patcher = patch(
            "utils.autoresponder_storage.AUTORESPONDER_FILE",
            os.path.join(self.tmp_dir, "autoresponders.json"),
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()
        shutil.rmtree(self.tmp_dir, ignore_errors=True)

    async def test_save_and_load_local_storage(self):
        bot = MagicMock()
        bot.mongo_db = None  # Force local fallback

        storage = AutoResponderStorage(bot)
        settings = GuildAutoResponderSettings(enabled=True, conflict_mode="all_matches")
        items = [
            AutoResponderItem(
                id="r1",
                name="Socials",
                triggers=["twitter", "x"],
                match_mode="contains",
                replies=["Follow us @NexoraBot!"],
            )
        ]

        await storage.save_guild_data(12345, settings, items)

        # Reload
        loaded_settings, loaded_items = await storage.get_guild_data(12345)
        self.assertTrue(loaded_settings.enabled)
        self.assertEqual(loaded_settings.conflict_mode, "all_matches")
        self.assertEqual(len(loaded_items), 1)
        self.assertEqual(loaded_items[0].name, "Socials")
        self.assertEqual(loaded_items[0].triggers, ["twitter", "x"])
        self.assertEqual(loaded_items[0].replies, ["Follow us @NexoraBot!"])

    async def test_record_hit(self):
        bot = MagicMock()
        bot.mongo_db = None

        storage = AutoResponderStorage(bot)
        settings = GuildAutoResponderSettings()
        items = [AutoResponderItem(id="r1", triggers=["test"], replies=["reply"])]
        await storage.save_guild_data(12345, settings, items)

        await storage.record_hit(12345, "r1")
        _, loaded_items = await storage.get_guild_data(12345)
        self.assertEqual(loaded_items[0].hits, 1)
        self.assertIsNotNone(loaded_items[0].last_triggered_at)


if __name__ == "__main__":
    unittest.main()

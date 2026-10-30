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

import discord

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


class TestAutoresponderMentionsAndReactions(unittest.IsolatedAsyncioTestCase):
    """Test ping mention logic, AllowedMentions security, and trigger reaction mechanics."""

    def setUp(self):
        import discord
        from cogs.premium.autoreply import AutoResponder
        self.bot = MagicMock()
        self.bot.mongo_db = None
        self.cog = AutoResponder(self.bot)

    def _create_mock_message(self, content="hello", author_id=123456):
        import discord
        author = MagicMock(spec=discord.Member)
        author.id = author_id
        author.mention = f"<@{author_id}>"
        author.display_name = "Alice"
        author.name = "alice"
        author.bot = False
        author.roles = []

        guild = MagicMock(spec=discord.Guild)
        guild.id = 999
        guild.name = "Test Guild"
        guild.member_count = 50
        guild.icon = None

        channel = MagicMock(spec=discord.TextChannel)
        channel.id = 888
        channel.name = "general"
        channel.mention = "<#888>"
        channel.send = AsyncMock()

        msg = MagicMock(spec=discord.Message)
        msg.id = 777
        msg.author = author
        msg.guild = guild
        msg.channel = channel
        msg.content = content
        msg.webhook_id = None
        msg.created_at = None
        msg.reply = AsyncMock()
        msg.add_reaction = AsyncMock()
        msg.delete = AsyncMock()
        return msg

    async def test_ping_on_without_explicit_mention_replies_with_ping(self):
        msg = self._create_mock_message("hello")
        item = AutoResponderItem(
            id="p1",
            triggers=["hello"],
            replies=["Welcome!"],
            reply_to_message=True,
            ping_user=True,
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog._dispatch_response(msg, item)

        msg.reply.assert_called_once()
        call_kwargs = msg.reply.call_args[1]
        allowed = call_kwargs["allowed_mentions"]
        self.assertFalse(allowed.everyone)
        self.assertFalse(allowed.roles)
        self.assertTrue(allowed.replied_user)
        self.assertEqual(allowed.users, [msg.author])

    async def test_ping_off_without_explicit_mention_silent_reply(self):
        msg = self._create_mock_message("hello")
        item = AutoResponderItem(
            id="p2",
            triggers=["hello"],
            replies=["Welcome!"],
            reply_to_message=True,
            ping_user=False,
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog._dispatch_response(msg, item)

        msg.reply.assert_called_once()
        call_kwargs = msg.reply.call_args[1]
        allowed = call_kwargs["allowed_mentions"]
        self.assertFalse(allowed.everyone)
        self.assertFalse(allowed.roles)
        self.assertFalse(allowed.replied_user)
        self.assertFalse(allowed.users)

    async def test_explicit_template_mention_avoids_duplicate_reply_ping(self):
        msg = self._create_mock_message("hello", author_id=123456)
        item = AutoResponderItem(
            id="p3",
            triggers=["hello"],
            replies=["Hi {user.mention}!"],
            reply_to_message=True,
            ping_user=True,
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog._dispatch_response(msg, item)

        msg.reply.assert_called_once()
        call_kwargs = msg.reply.call_args[1]
        allowed = call_kwargs["allowed_mentions"]
        # Explicit mention in content body, so replied_user must be False to avoid double ping
        self.assertFalse(allowed.replied_user)
        self.assertEqual(allowed.users, [msg.author])
        self.assertIn("<@123456>", call_kwargs["content"])

    async def test_ping_on_non_reply_prepends_mention_once(self):
        msg = self._create_mock_message("hello", author_id=123456)
        item = AutoResponderItem(
            id="p4",
            triggers=["hello"],
            replies=["Welcome to the server!"],
            reply_to_message=False,
            ping_user=True,
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog._dispatch_response(msg, item)

        msg.channel.send.assert_called_once()
        call_kwargs = msg.channel.send.call_args[1]
        self.assertTrue(call_kwargs["content"].startswith("<@123456>"))
        allowed = call_kwargs["allowed_mentions"]
        self.assertEqual(allowed.users, [msg.author])

    async def test_trigger_reaction_success(self):
        msg = self._create_mock_message("hello")
        item = AutoResponderItem(
            id="r1",
            triggers=["hello"],
            replies=["Greetings!"],
            trigger_reaction="👋",
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog._dispatch_response(msg, item)

        msg.reply.assert_called_once()
        msg.add_reaction.assert_called_once_with("👋")

    async def test_trigger_reaction_disabled_sends_no_reaction(self):
        msg = self._create_mock_message("hello")
        item = AutoResponderItem(
            id="r2",
            triggers=["hello"],
            replies=["Greetings!"],
            trigger_reaction=None,
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog._dispatch_response(msg, item)

        msg.reply.assert_called_once()
        msg.add_reaction.assert_not_called()

    async def test_trigger_reaction_error_does_not_block_text_response(self):
        import discord
        msg = self._create_mock_message("hello")
        msg.add_reaction.side_effect = discord.Forbidden(
            response=MagicMock(status=403, reason="Forbidden"), message="Missing Permissions"
        )
        item = AutoResponderItem(
            id="r3",
            triggers=["hello"],
            replies=["Greetings!"],
            trigger_reaction="🔥",
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            # Must not raise exception
            await self.cog._dispatch_response(msg, item)

        # Message reply was still sent despite reaction Forbidden error!
        msg.reply.assert_called_once()
        self.assertEqual(msg.reply.call_args[1]["content"], "Greetings!")

    def test_item_serialization_and_deserialization(self):
        # Full serialization round-trip
        original = AutoResponderItem(
            id="item123",
            name="Test",
            triggers=["ping"],
            match_mode="exact",
            replies=["pong"],
            ping_user=True,
            trigger_reaction="🏓",
        )
        d = original.to_dict()
        self.assertTrue(d["ping_user"])
        self.assertEqual(d["trigger_reaction"], "🏓")
        self.assertEqual(d["reactions"], ["🏓"])

        reloaded = AutoResponderItem.from_dict(d)
        self.assertTrue(reloaded.ping_user)
        self.assertEqual(reloaded.trigger_reaction, "🏓")
        self.assertEqual(reloaded.reactions, ["🏓"])

        # Backward compatibility with legacy mention_author and reactions
        legacy_data = {
            "id": "legacy1",
            "name": "Legacy",
            "triggers": ["old"],
            "replies": ["hi"],
            "mention_author": True,
            "reactions": ["👋"],
        }
        legacy_item = AutoResponderItem.from_dict(legacy_data)
        self.assertTrue(legacy_item.ping_user)
        self.assertEqual(legacy_item.trigger_reaction, "👋")

    def test_guild_settings_default_ping_serialization(self):
        settings = GuildAutoResponderSettings(enabled=True, default_ping=True)
        d = settings.to_dict()
        self.assertTrue(d["default_ping"])

        reloaded = GuildAutoResponderSettings.from_dict(d)
        self.assertTrue(reloaded.default_ping)

    async def test_inline_react_tag_single_emoji(self):
        msg = self._create_mock_message("hello")
        item = AutoResponderItem(
            id="ir1",
            triggers=["hello"],
            replies=["Welcome {user}! {react: :wave:}"],
            reply_to_message=True,
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog._dispatch_response(msg, item)

        msg.reply.assert_called_once()
        self.assertEqual(msg.reply.call_args[1]["content"], "Welcome Alice!")
        msg.add_reaction.assert_called_once_with("👋")

    async def test_inline_react_tag_multiple_emojis(self):
        msg = self._create_mock_message("great")
        item = AutoResponderItem(
            id="ir2",
            triggers=["great"],
            replies=["{react: :fire:} {react: :heart:} Amazing!"],
            reply_to_message=True,
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog._dispatch_response(msg, item)

        msg.reply.assert_called_once()
        self.assertEqual(msg.reply.call_args[1]["content"], "Amazing!")
        calls = [c[0][0] for c in msg.add_reaction.call_args_list]
        self.assertEqual(calls, ["🔥", "❤️"])

    async def test_inline_react_tag_only_no_text_reply(self):
        msg = self._create_mock_message("agree")
        item = AutoResponderItem(
            id="ir3",
            triggers=["agree"],
            replies=["{react: :thumbsup:}"],
            reply_to_message=True,
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog._dispatch_response(msg, item)

        # No empty text message sent
        msg.reply.assert_not_called()
        msg.channel.send.assert_not_called()
        msg.add_reaction.assert_called_once_with("👍")

    async def test_inline_react_tag_guild_custom_emoji(self):
        import discord
        msg = self._create_mock_message("cool")
        custom_emoji = MagicMock(spec=discord.Emoji)
        custom_emoji.name = "nexora_star"
        custom_emoji.id = 998877
        msg.guild.emojis = [custom_emoji]

        item = AutoResponderItem(
            id="ir4",
            triggers=["cool"],
            replies=["Nice one! {react: :nexora_star:}"],
            reply_to_message=True,
        )

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog._dispatch_response(msg, item)

        msg.reply.assert_called_once()
        self.assertEqual(msg.reply.call_args[1]["content"], "Nice one!")
        msg.add_reaction.assert_called_once_with(custom_emoji)


class TestAutoresponderFreeTier(unittest.IsolatedAsyncioTestCase):
    """Test that autoresponder is free for all guilds with 10 slots and proper tier limits."""

    def setUp(self):
        from cogs.premium.autoreply import AutoResponder
        self.bot = MagicMock()
        self.bot.is_premium_guild = MagicMock(return_value=False)
        self.bot.get_premium_tier = AsyncMock(return_value="FREE")
        self.bot.get_tier_config = MagicMock(return_value={
            "features": {"custom_responses": 10}
        })
        self.cog = AutoResponder(self.bot)

    async def test_free_tier_limit_defaults_to_10(self):
        """Free tier servers get 10 autoresponders by default."""
        limit = await self.cog._get_tier_limit(123456)
        self.assertEqual(limit, 10)

    async def test_paid_tier_limits(self):
        """Higher tiers get higher limits."""
        self.bot.get_premium_tier = AsyncMock(return_value="BASIC")
        self.bot.get_tier_config = MagicMock(return_value={"features": {"custom_responses": 25}})
        self.assertEqual(await self.cog._get_tier_limit(123), 25)

        self.bot.get_premium_tier = AsyncMock(return_value="PRO")
        self.bot.get_tier_config = MagicMock(return_value={"features": {"custom_responses": 50}})
        self.assertEqual(await self.cog._get_tier_limit(123), 50)

        self.bot.get_premium_tier = AsyncMock(return_value="ENTERPRISE")
        self.bot.get_tier_config = MagicMock(return_value={"features": {"custom_responses": -1}})
        self.assertEqual(await self.cog._get_tier_limit(123), -1)

    async def test_on_message_triggers_for_free_server(self):
        """Free server messages trigger autoresponder without needing premium subscription."""
        msg = MagicMock(spec=discord.Message)
        msg.author = MagicMock(spec=discord.Member)
        msg.author.id = 12345
        msg.author.bot = False
        msg.author.roles = []
        msg.author.mention = "<@12345>"
        msg.author.display_name = "User"
        msg.webhook_id = None
        msg.guild = MagicMock(spec=discord.Guild)
        msg.guild.id = 999
        msg.channel = MagicMock(spec=discord.TextChannel)
        msg.channel.id = 888
        msg.content = "ping"
        msg.reply = AsyncMock()

        self.bot.get_context = AsyncMock(return_value=MagicMock(valid=False))

        settings = GuildAutoResponderSettings(enabled=True)
        item = AutoResponderItem(id="test1", triggers=["ping"], replies=["pong"])
        self.cog._guild_cache[999] = (settings, [item])

        with patch.object(self.cog.storage, "record_hit", new=AsyncMock()):
            await self.cog.on_message(msg)
            await asyncio.sleep(0.05)

        msg.reply.assert_called_once()
        self.assertEqual(msg.reply.call_args[1]["content"], "pong")

    async def test_slot_limit_enforced_on_free_server(self):
        """When 10 autoresponders already exist, adding an 11th on Free tier is blocked."""
        ctx = MagicMock()
        ctx.guild.id = 999
        ctx.send = AsyncMock()

        settings = GuildAutoResponderSettings(enabled=True)
        items = [AutoResponderItem(id=f"item_{i}", triggers=[f"trig_{i}"], replies=["hi"]) for i in range(10)]
        self.cog._guild_cache[999] = (settings, items)

        await self.cog.ar_add.callback(self.cog, ctx, trigger="new_trig", reply="hello")
        ctx.send.assert_called_once()
        call_msg = ctx.send.call_args[0][0]
        self.assertIn("Slot Limit Reached", call_msg)
        self.assertIn("10", call_msg)


if __name__ == "__main__":
    unittest.main()

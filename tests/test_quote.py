"""
tests/test_quote.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unit and integration test suite for Nexora Quote System.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import io
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from PIL import Image

from cogs.utility.quote import Quote, parse_message_link
from utils.quote_card import generate_quote_card
from utils.quote_storage import (
    GuildQuoteSettings,
    QuoteRecord,
    QuoteStorage,
    load_local_quotes_data,
    save_local_quotes_data,
)


class TestMessageLinkParsing(unittest.TestCase):
    """Test Discord message link parsing across domains and edge cases."""

    def test_standard_message_link(self):
        url = "https://discord.com/channels/1167464602620145808/123456789012345678/987654321098765432"
        parsed = parse_message_link(url)
        self.assertIsNotNone(parsed)
        guild_id, channel_id, message_id = parsed
        self.assertEqual(guild_id, 1167464602620145808)
        self.assertEqual(channel_id, 123456789012345678)
        self.assertEqual(message_id, 987654321098765432)

    def test_canary_message_link(self):
        url = "https://canary.discord.com/channels/111/222/333"
        parsed = parse_message_link(url)
        self.assertEqual(parsed, (111, 222, 333))

    def test_ptb_message_link(self):
        url = "https://ptb.discord.com/channels/444/555/666"
        parsed = parse_message_link(url)
        self.assertEqual(parsed, (444, 555, 666))

    def test_discordapp_message_link(self):
        url = "https://discordapp.com/channels/777/888/999"
        parsed = parse_message_link(url)
        self.assertEqual(parsed, (777, 888, 999))

    def test_invalid_dm_link(self):
        url = "https://discord.com/channels/@me/123456789/987654321"
        self.assertIsNone(parse_message_link(url))

    def test_invalid_random_strings(self):
        self.assertIsNone(parse_message_link(""))
        self.assertIsNone(parse_message_link("hello world"))
        self.assertIsNone(parse_message_link("https://google.com"))
        self.assertIsNone(parse_message_link("https://discord.com/channels/abc/def/ghi"))


class TestQuoteStorage(unittest.IsolatedAsyncioTestCase):
    """Test quote persistence and settings storage with local JSON fallback."""

    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "quotes_test.json")
        self.patcher = patch("utils.quote_storage.QUOTES_FILE", self.test_file)
        self.patcher.start()

        self.mock_bot = MagicMock()
        self.mock_bot.mongo_db = None  # Force local fallback
        self.storage = QuoteStorage(self.mock_bot)

    async def asyncTearDown(self):
        self.patcher.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    async def test_settings_save_and_retrieve(self):
        guild_id = 123456789
        settings = GuildQuoteSettings(
            guild_id=guild_id,
            destination_channel_id=987654321,
            enabled=True,
            allowed_roles=[111, 222],
            excluded_channels=[333],
            log_channel_id=444,
            render_style="card",
        )
        await self.storage.save_settings(guild_id, settings)

        loaded = await self.storage.get_settings(guild_id)
        self.assertEqual(loaded.guild_id, guild_id)
        self.assertEqual(loaded.destination_channel_id, 987654321)
        self.assertTrue(loaded.enabled)
        self.assertEqual(loaded.allowed_roles, [111, 222])
        self.assertEqual(loaded.excluded_channels, [333])
        self.assertEqual(loaded.log_channel_id, 444)
        self.assertEqual(loaded.render_style, "card")

    async def test_quote_record_add_get_and_delete(self):
        guild_id = 99999
        record = QuoteRecord(
            quote_id="abc12345",
            guild_id=guild_id,
            source_channel_id=101,
            source_message_id=202,
            quote_channel_id=303,
            quote_message_id=404,
            quoter_id=505,
            author_id=606,
            jump_url="https://discord.com/channels/99999/101/202",
            content_preview="This is a memorable quote!",
            has_image=False,
        )

        await self.storage.add_quote(record)

        # Get by quote_id
        fetched = await self.storage.get_quote("abc12345")
        self.assertIsNotNone(fetched)
        self.assertEqual(fetched.quote_id, "abc12345")
        self.assertEqual(fetched.quoter_id, 505)
        self.assertEqual(fetched.content_preview, "This is a memorable quote!")

        # Get by message_id
        fetched_by_msg = await self.storage.get_quote_by_message(guild_id, 404)
        self.assertIsNotNone(fetched_by_msg)
        self.assertEqual(fetched_by_msg.quote_id, "abc12345")

        # Total count
        count = await self.storage.get_guild_quotes_count(guild_id)
        self.assertEqual(count, 1)

        # Delete
        deleted = await self.storage.delete_quote("abc12345")
        self.assertTrue(deleted)
        self.assertIsNone(await self.storage.get_quote("abc12345"))
        self.assertEqual(await self.storage.get_guild_quotes_count(guild_id), 0)


class TestQuoteCardGeneration(unittest.TestCase):
    """Test PIL image rendering, typography wrapping, and visual attachments."""

    def test_basic_quote_card_generation(self):
        buf = generate_quote_card(
            author_name="URMILA",
            author_handle="ishani_dagger",
            text="Gaareb hai replace him hanu",
            channel_name="general",
            timestamp_str="Oct 21, 2026",
        )
        self.assertIsNotNone(buf)
        img = Image.open(buf)
        self.assertEqual(img.format, "PNG")
        self.assertGreaterEqual(img.width, 1000)
        self.assertGreaterEqual(img.height, 400)

    def test_quote_card_with_avatar(self):
        dummy_avatar = Image.new("RGBA", (256, 256), (88, 101, 242, 255))
        av_io = io.BytesIO()
        dummy_avatar.save(av_io, format="PNG")

        buf = generate_quote_card(
            author_name="Makima",
            author_handle="makima_official",
            text="A quiet evening in Tokyo.",
            avatar_bytes=av_io.getvalue(),
            channel_name="lounge",
        )
        self.assertIsNotNone(buf)
        img = Image.open(buf)
        self.assertEqual(img.format, "PNG")

    def test_quote_card_with_image_attachment(self):
        dummy_attachment = Image.new("RGBA", (400, 300), (255, 80, 80, 255))
        att_io = io.BytesIO()
        dummy_attachment.save(att_io, format="PNG")

        buf = generate_quote_card(
            author_name="Artist",
            author_handle="sketcher",
            text="Look at my new drawing!",
            image_bytes=att_io.getvalue(),
            channel_name="art",
        )
        self.assertIsNotNone(buf)
        img = Image.open(buf)
        self.assertEqual(img.format, "PNG")

    def test_quote_card_empty_text_fallback(self):
        buf = generate_quote_card(
            author_name="SilentUser",
            author_handle="silent",
            text="",
        )
        self.assertIsNotNone(buf)
        img = Image.open(buf)
        self.assertEqual(img.format, "PNG")

    def test_quote_card_multiline_long_text(self):
        long_text = "This is a very long quote designed to test automatic line wrapping, text boundary calculations, and adaptive card height adjustment. " * 5
        buf = generate_quote_card(
            author_name="Philosopher",
            author_handle="deep_thinker",
            text=long_text,
        )
        self.assertIsNotNone(buf)
        img = Image.open(buf)
        self.assertEqual(img.format, "PNG")
        self.assertGreaterEqual(img.height, 440)


class TestQuotePermissionsAndRemoval(unittest.IsolatedAsyncioTestCase):
    """Test permission validation, unauthorized removal denials, and privacy checks."""

    async def asyncSetUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.test_file = os.path.join(self.test_dir, "quotes_test.json")
        self.patcher = patch("utils.quote_storage.QUOTES_FILE", self.test_file)
        self.patcher.start()

        self.mock_bot = MagicMock()
        self.mock_bot.mongo_db = None
        self.mock_bot.owner_id = 999999999
        self.mock_bot.tree = MagicMock()

        self.cog = Quote(self.mock_bot)

    async def asyncTearDown(self):
        self.patcher.stop()
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    async def test_owner_removal_authorized(self):
        guild_id = 1000
        quote_msg_id = 2000
        quoter_id = 5000

        record = QuoteRecord(
            quote_id="test0001",
            guild_id=guild_id,
            quote_message_id=quote_msg_id,
            quoter_id=quoter_id,
            source_channel_id=10,
            source_message_id=20,
        )
        await self.cog.storage.add_quote(record)

        # Mock interaction by the quote owner
        mock_interaction = MagicMock()
        mock_interaction.guild = MagicMock(id=guild_id)
        mock_interaction.message = MagicMock(id=quote_msg_id, delete=AsyncMock())
        mock_interaction.user = MagicMock(id=quoter_id)
        mock_interaction.user.guild_permissions = SimpleNamespace(manage_messages=False, administrator=False)
        mock_interaction.response = MagicMock(send_message=AsyncMock())

        await self.cog.handle_quote_removal(mock_interaction)

        # Verify message deleted and response is success
        mock_interaction.message.delete.assert_called_once()
        mock_interaction.response.send_message.assert_called_once()
        self.assertIn("Quote successfully removed", mock_interaction.response.send_message.call_args[0][0])
        # Verify deleted from storage
        self.assertIsNone(await self.cog.storage.get_quote("test0001"))

    async def test_moderator_removal_authorized(self):
        guild_id = 1000
        quote_msg_id = 2001
        quoter_id = 5000
        mod_id = 9000

        record = QuoteRecord(
            quote_id="test0002",
            guild_id=guild_id,
            quote_message_id=quote_msg_id,
            quoter_id=quoter_id,
        )
        await self.cog.storage.add_quote(record)

        # Mock interaction by a moderator
        mock_interaction = MagicMock()
        mock_interaction.guild = MagicMock(id=guild_id)
        mock_interaction.message = MagicMock(id=quote_msg_id, delete=AsyncMock())
        mock_interaction.user = MagicMock(id=mod_id)
        mock_interaction.user.guild_permissions = SimpleNamespace(manage_messages=True, administrator=False)
        mock_interaction.response = MagicMock(send_message=AsyncMock())

        await self.cog.handle_quote_removal(mock_interaction)

        # Verify message deleted
        mock_interaction.message.delete.assert_called_once()
        self.assertIn("Quote successfully removed", mock_interaction.response.send_message.call_args[0][0])
        self.assertIsNone(await self.cog.storage.get_quote("test0002"))

    async def test_unauthorized_user_removal_denied(self):
        guild_id = 1000
        quote_msg_id = 2002
        quoter_id = 5000
        random_user_id = 7777

        record = QuoteRecord(
            quote_id="test0003",
            guild_id=guild_id,
            quote_message_id=quote_msg_id,
            quoter_id=quoter_id,
        )
        await self.cog.storage.add_quote(record)

        # Mock interaction by unrelated user
        mock_interaction = MagicMock()
        mock_interaction.guild = MagicMock(id=guild_id)
        mock_interaction.message = MagicMock(id=quote_msg_id, delete=AsyncMock())
        mock_interaction.user = MagicMock(id=random_user_id)
        mock_interaction.user.guild_permissions = SimpleNamespace(manage_messages=False, administrator=False)
        mock_interaction.response = MagicMock(send_message=AsyncMock())

        await self.cog.handle_quote_removal(mock_interaction)

        # Verify message was NOT deleted
        mock_interaction.message.delete.assert_not_called()
        # Verify ephemeral denial
        mock_interaction.response.send_message.assert_called_once()
        sent_text = mock_interaction.response.send_message.call_args[0][0]
        self.assertIn("Only the member who created this quote or a server moderator", sent_text)
        # Verify quote record still exists
        self.assertIsNotNone(await self.cog.storage.get_quote("test0003"))

    async def test_channel_privacy_check_blocks_inaccessible_messages(self):
        """User cannot quote from a channel they cannot read."""
        guild_id = 1000
        mock_guild = MagicMock(id=guild_id)
        mock_user = MagicMock(id=123)

        # Channel where user has no read_messages permission
        mock_source_channel = MagicMock(id=555)
        mock_source_channel.permissions_for.return_value = SimpleNamespace(
            read_messages=False,
            read_message_history=False,
        )

        mock_source_msg = MagicMock(
            channel=mock_source_channel,
            author=MagicMock(display_name="SecretAgent"),
            clean_content="Top secret staff chat",
            attachments=[],
        )

        respond_mock = AsyncMock()

        await self.cog._execute_quote(
            user=mock_user,
            guild=mock_guild,
            source_message=mock_source_msg,
            respond_func=respond_mock,
            is_interaction=True,
        )

        # Verify request was blocked
        respond_mock.assert_called_once()
        self.assertIn("permission to view or quote", respond_mock.call_args[0][0])


if __name__ == "__main__":
    unittest.main()

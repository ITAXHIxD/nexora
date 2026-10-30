import asyncio
import io
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import discord
from discord.ext import commands

from cogs.games.say import Say, check_owner, parse_prefix_args
from utils.config import OWNER_ID


class TestSayCommand(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = MagicMock(spec=commands.Bot)
        self.bot.owner_id = OWNER_ID
        self.bot.owner_ids = set()
        self.bot.active_saying = {}
        self.bot.is_owner = AsyncMock(return_value=False)
        self.cog = Say(self.bot)

    async def test_check_owner_with_configured_owner_id(self):
        """Configured OWNER_ID is recognized as owner."""
        is_owner = await check_owner(OWNER_ID, self.bot)
        self.assertTrue(is_owner)

    async def test_check_owner_blocks_non_owner(self):
        """Random user ID is not recognized as owner."""
        is_owner = await check_owner(123456789, self.bot)
        self.assertFalse(is_owner)

    def test_parse_prefix_args(self):
        """Test parsing leading channel mentions, message links, and message IDs."""
        # 1. Plain text
        cid, reply, text = parse_prefix_args("Hello world")
        self.assertIsNone(cid)
        self.assertIsNone(reply)
        self.assertEqual(text, "Hello world")

        # 2. Channel mention
        cid, reply, text = parse_prefix_args("<#987654321012345678> Hello there")
        self.assertEqual(cid, "987654321012345678")
        self.assertIsNone(reply)
        self.assertEqual(text, "Hello there")

        # 3. Message Link
        link = "https://discord.com/channels/111/222/333"
        cid, reply, text = parse_prefix_args(f"{link} Replying here")
        self.assertIsNone(cid)
        self.assertEqual(reply, link)
        self.assertEqual(text, "Replying here")

        # 4. Message ID
        msg_id = "123456789012345678"
        cid, reply, text = parse_prefix_args(f"{msg_id} Replying by ID")
        self.assertIsNone(cid)
        self.assertEqual(reply, msg_id)
        self.assertEqual(text, "Replying by ID")

        # 5. Channel mention + Message link
        cid, reply, text = parse_prefix_args(f"<#987654321012345678> {link} Replying in channel")
        self.assertEqual(cid, "987654321012345678")
        self.assertEqual(reply, link)
        self.assertEqual(text, "Replying in channel")

    async def test_say_sends_plain_message(self):
        """Test sending a standard text message."""
        channel = AsyncMock()
        author = MagicMock(id=OWNER_ID)

        success, msg = await self.cog._execute_say(
            bot=self.bot,
            author=author,
            current_channel=channel,
            current_guild=None,
            raw_text="Hello from Nexora!",
        )

        self.assertTrue(success)
        channel.send.assert_called_once()
        call_kwargs = channel.send.call_args[1]
        self.assertEqual(call_kwargs["content"], "Hello from Nexora!")
        self.assertIsNone(call_kwargs["reference"])

    async def test_say_replies_to_native_reference(self):
        """Test that replying to a message in Discord sends the bot message as a reply."""
        channel = AsyncMock(id=999)
        mock_target_msg = MagicMock(id=555555555555555555)
        channel.fetch_message = AsyncMock(return_value=mock_target_msg)
        self.bot.get_channel = MagicMock(return_value=channel)

        ref = MagicMock(spec=discord.MessageReference)
        ref.message_id = 555555555555555555
        ref.channel_id = 999

        author = MagicMock(id=OWNER_ID)

        success, msg = await self.cog._execute_say(
            bot=self.bot,
            author=author,
            current_channel=channel,
            current_guild=None,
            raw_text="Replying to your message!",
            reply_message_ref=ref,
        )

        self.assertTrue(success)
        channel.send.assert_called_once()
        call_kwargs = channel.send.call_args[1]
        self.assertEqual(call_kwargs["content"], "Replying to your message!")
        self.assertEqual(call_kwargs["reference"], mock_target_msg)

    async def test_say_replies_to_message_link(self):
        """Test replying to a message via explicit message link."""
        channel = AsyncMock(id=222)
        target_msg = MagicMock(id=333)
        channel.fetch_message = AsyncMock(return_value=target_msg)
        self.bot.get_channel = MagicMock(return_value=channel)

        author = MagicMock(id=OWNER_ID)
        link = "https://discord.com/channels/111/222/333"

        success, msg = await self.cog._execute_say(
            bot=self.bot,
            author=author,
            current_channel=channel,
            current_guild=None,
            raw_text="Replying via link",
            reply_to=link,
        )

        self.assertTrue(success)
        channel.send.assert_called_once()
        call_kwargs = channel.send.call_args[1]
        self.assertEqual(call_kwargs["reference"], target_msg)

    async def test_say_forwards_attachments(self):
        """Test forwarding attachments with the say command."""
        channel = AsyncMock()
        dummy_file = discord.File(io.BytesIO(b"test"), filename="test.png")
        author = MagicMock(id=OWNER_ID)

        success, msg = await self.cog._execute_say(
            bot=self.bot,
            author=author,
            current_channel=channel,
            current_guild=None,
            raw_text="Check this image!",
            files=[dummy_file],
        )

        self.assertTrue(success)
        channel.send.assert_called_once()
        call_kwargs = channel.send.call_args[1]
        self.assertEqual(len(call_kwargs["files"]), 1)
        self.assertEqual(call_kwargs["files"][0].filename, "test.png")

    async def test_say_empty_content_rejected(self):
        """Test that calling say with no message and no files returns an error."""
        channel = AsyncMock()
        author = MagicMock(id=OWNER_ID)

        success, msg = await self.cog._execute_say(
            bot=self.bot,
            author=author,
            current_channel=channel,
            current_guild=None,
            raw_text="",
            files=[],
        )

        self.assertFalse(success)
        self.assertIn("Please provide a message", msg)
        channel.send.assert_not_called()

    async def test_say_ping_toggle(self):
        """Test that -ping toggles replied_user to True in AllowedMentions."""
        channel = AsyncMock()
        author = MagicMock(id=OWNER_ID)

        success, msg = await self.cog._execute_say(
            bot=self.bot,
            author=author,
            current_channel=channel,
            current_guild=None,
            raw_text="Hello -ping",
        )

        self.assertTrue(success)
        channel.send.assert_called_once()
        call_kwargs = channel.send.call_args[1]
        self.assertEqual(call_kwargs["content"], "Hello")
        self.assertTrue(call_kwargs["allowed_mentions"].replied_user)

    async def test_say_active_saying_recorded(self):
        """Test that active_saying dictionary is updated on successful send."""
        channel = AsyncMock(id=777)
        author = MagicMock(id=OWNER_ID)

        success, msg = await self.cog._execute_say(
            bot=self.bot,
            author=author,
            current_channel=channel,
            current_guild=None,
            raw_text="Testing active_saying",
        )

        self.assertTrue(success)
        key = f"777_{OWNER_ID}"
        self.assertIn(key, self.bot.active_saying)
        self.assertEqual(self.bot.active_saying[key]["message"], "Testing active_saying")

    async def test_say_chunks_long_messages(self):
        """Test that messages longer than 2000 chars are chunked and sent sequentially."""
        channel = AsyncMock()
        author = MagicMock(id=OWNER_ID)
        long_message = "A" * 3500

        success, msg = await self.cog._execute_say(
            bot=self.bot,
            author=author,
            current_channel=channel,
            current_guild=None,
            raw_text=long_message,
        )

        self.assertTrue(success)
        self.assertEqual(channel.send.call_count, 2)
        first_call = channel.send.call_args_list[0][1]
        second_call = channel.send.call_args_list[1][1]
        self.assertEqual(len(first_call["content"]), 2000)
        self.assertEqual(len(second_call["content"]), 1500)


if __name__ == "__main__":
    unittest.main()

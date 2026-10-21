"""
tests/test_quote.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unit and integration test suite for Nexora Quote System.
Tests rendering, layout routing, TrueType typography, stateless controls,
and error fallback resilience.
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
from utils.quote_card import compose_image_quote, generate_quote_card
from utils.quote_storage import (
    GuildQuoteSettings,
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
    """Test quote settings persistence with local JSON fallback."""

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

    async def test_quote_counter_increment(self):
        guild_id = 99999
        await self.storage.increment_quote_count(guild_id)
        await self.storage.increment_quote_count(guild_id)

        loaded = await self.storage.get_settings(guild_id)
        self.assertEqual(loaded.quotes_count, 2)


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
        self.assertEqual(img.width, 960)
        self.assertGreaterEqual(img.height, 340)

    def test_quote_card_with_square_avatar(self):
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

    def test_quote_card_with_portrait_avatar(self):
        """Test avatar taller than wide (portrait)."""
        dummy_avatar = Image.new("RGBA", (200, 450), (45, 55, 75, 255))
        av_io = io.BytesIO()
        dummy_avatar.save(av_io, format="PNG")

        buf = generate_quote_card(
            author_name="PortraitUser",
            author_handle="portrait",
            text="Testing portrait aspect ratio.",
            avatar_bytes=av_io.getvalue(),
        )
        self.assertIsNotNone(buf)
        img = Image.open(buf)
        self.assertEqual(img.format, "PNG")

    def test_quote_card_with_landscape_avatar(self):
        """Test avatar wider than tall (landscape)."""
        dummy_avatar = Image.new("RGBA", (500, 250), (60, 45, 80, 255))
        av_io = io.BytesIO()
        dummy_avatar.save(av_io, format="PNG")

        buf = generate_quote_card(
            author_name="LandscapeUser",
            author_handle="landscape",
            text="Testing landscape aspect ratio.",
            avatar_bytes=av_io.getvalue(),
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
        self.assertGreaterEqual(img.height, 340)

    def test_quote_card_unicode_and_emojis(self):
        text = "Hello world! ✨ This contains Unicode chars: 日本語 and emojis 🌟"
        buf = generate_quote_card(
            author_name="Global Traveler 🌍",
            author_handle="traveler",
            text=text,
        )
        self.assertIsNotNone(buf)
        img = Image.open(buf)
        self.assertEqual(img.format, "PNG")


    def test_compose_image_quote_square(self):
        """Square images render at exact 1:1 aspect ratio with rounded corners."""
        img = Image.new("RGBA", (500, 500), (40, 60, 100, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        res = compose_image_quote(buf.getvalue())
        self.assertIsNotNone(res)
        out = Image.open(res)
        self.assertEqual(out.width, out.height)

    def test_compose_image_quote_landscape(self):
        """Landscape images fill full width naturally."""
        img = Image.new("RGBA", (1280, 720), (50, 40, 80, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        res = compose_image_quote(buf.getvalue())
        self.assertIsNotNone(res)
        out = Image.open(res)
        self.assertGreater(out.width, out.height)

    def test_compose_image_quote_portrait(self):
        """Portrait images are centered on an ambient dark canvas."""
        img = Image.new("RGBA", (300, 700), (30, 80, 50, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        res = compose_image_quote(buf.getvalue())
        self.assertIsNotNone(res)
        out = Image.open(res)
        self.assertGreater(out.width, 300)

    def test_compose_image_quote_ultrawide(self):
        """Ultra-wide banners preserve banner proportions without vertical black bars."""
        img = Image.new("RGBA", (1600, 320), (90, 40, 30, 255))
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        res = compose_image_quote(buf.getvalue())
        self.assertIsNotNone(res)
        out = Image.open(res)
        self.assertEqual(round(out.width / out.height, 1), 5.0)

    def test_compose_image_quote_animated_gif_returns_none(self):
        """Animated GIFs return None so Discord plays the animation natively."""
        frames = [Image.new("RGB", (100, 100), (255, 0, 0)), Image.new("RGB", (100, 100), (0, 255, 0))]
        buf = io.BytesIO()
        frames[0].save(buf, format="GIF", save_all=True, append_images=[frames[1]], duration=100, loop=0)
        res = compose_image_quote(buf.getvalue())
        self.assertIsNone(res)

    def test_compose_image_quote_invalid_bytes(self):
        self.assertIsNone(compose_image_quote(b""))
        self.assertIsNone(compose_image_quote(b"not an image"))


class TestQuoteExecutionLayouts(unittest.IsolatedAsyncioTestCase):
    """Test layout routing: Image preservation vs Text-only card vs Fallback."""

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

    async def test_case_a_card_style_renders_composed_image_file(self):
        """When render_style == 'card', image attachment is composed with Pillow and attached as quote.png."""
        guild = MagicMock(id=111, me=MagicMock())
        dest_channel = MagicMock(id=222, send=AsyncMock())
        dest_channel.permissions_for.return_value = SimpleNamespace(
            send_messages=True, embed_links=True
        )
        guild.get_channel.return_value = dest_channel

        user = MagicMock(id=333, display_name="QuoterUser", roles=[])
        user.display_avatar.url = "https://cdn.discordapp.com/avatars/quoter.png"

        source_channel = MagicMock(
            id=444, send=AsyncMock(return_value=MagicMock(id=888))
        )
        source_channel.name = "art-showcase"
        source_channel.permissions_for.return_value = SimpleNamespace(
            read_messages=True, read_message_history=True, send_messages=True, embed_links=True
        )

        # Create valid PNG bytes
        test_img = Image.new("RGBA", (400, 300), (50, 100, 150, 255))
        img_buf = io.BytesIO()
        test_img.save(img_buf, format="PNG")
        mock_att = MagicMock(
            content_type="image/png",
            filename="artwork.png",
            url="https://cdn.discordapp.com/attachments/1/2/artwork.png",
            read=AsyncMock(return_value=img_buf.getvalue()),
        )
        mock_author = MagicMock(display_name="Artist")
        mock_author.name = "artist"
        mock_author.display_avatar.url = "https://cdn.discordapp.com/avatars/artist.png"

        source_msg = MagicMock(
            id=555,
            channel=source_channel,
            author=mock_author,
            clean_content="My new digital painting!",
            attachments=[mock_att],
            created_at=MagicMock(strftime=lambda fmt: "Oct 21, 2026"),
        )

        respond_mock = AsyncMock()

        await self.cog._execute_quote(
            user=user,
            guild=guild,
            source_message=source_msg,
            respond_func=respond_mock,
            is_interaction=True,
        )

        source_channel.send.assert_called_once()
        call_kwargs = source_channel.send.call_args[1]
        sent_embed = call_kwargs["embed"]
        # In card mode, a file was attached and embed points to attachment://quote.png
        self.assertIn("file", call_kwargs)
        self.assertEqual(call_kwargs["file"].filename, "quote.png")
        self.assertEqual(sent_embed.image.url, "attachment://quote.png")
        self.assertIn("https://discord.com/channels/111/444/555", sent_embed.description)
        self.assertIn("My new digital painting!", sent_embed.description)
        # Original author attribution
        self.assertEqual(sent_embed.author.name, "Artist (@artist)")
        # Quoter attribution footer
        self.assertIn("Quoted by QuoterUser • #art-showcase", sent_embed.footer.text)

    async def test_case_a_embed_style_uses_raw_attachment_url(self):
        """When render_style == 'embed', image attachment uses raw URL directly without Pillow file attachment."""
        guild = MagicMock(id=111, me=MagicMock())
        dest_channel = MagicMock(id=222, send=AsyncMock())
        dest_channel.permissions_for.return_value = SimpleNamespace(
            send_messages=True, embed_links=True
        )
        guild.get_channel.return_value = dest_channel

        # Set render_style to embed
        settings = GuildQuoteSettings(guild_id=111, render_style="embed")
        await self.cog.storage.save_settings(111, settings)

        user = MagicMock(id=333, display_name="QuoterUser", roles=[])
        user.display_avatar.url = "https://cdn.discordapp.com/avatars/quoter.png"

        source_channel = MagicMock(
            id=444, name="general", send=AsyncMock(return_value=MagicMock(id=888))
        )
        source_channel.permissions_for.return_value = SimpleNamespace(
            read_messages=True, read_message_history=True, send_messages=True, embed_links=True
        )

        mock_att = MagicMock(
            content_type="image/png",
            filename="photo.png",
            url="https://cdn.discordapp.com/attachments/1/2/photo.png",
        )
        source_msg = MagicMock(
            id=556,
            channel=source_channel,
            author=MagicMock(display_name="Photographer", name="photo_guy"),
            clean_content="Nice shot",
            attachments=[mock_att],
            created_at=MagicMock(strftime=lambda fmt: "Oct 21, 2026"),
        )

        respond_mock = AsyncMock()

        await self.cog._execute_quote(
            user=user,
            guild=guild,
            source_message=source_msg,
            respond_func=respond_mock,
            is_interaction=True,
        )

        source_channel.send.assert_called_once()
        call_kwargs = source_channel.send.call_args[1]
        sent_embed = call_kwargs["embed"]
        # Raw URL used, no file attached
        self.assertNotIn("file", call_kwargs)
        self.assertEqual(sent_embed.image.url, "https://cdn.discordapp.com/attachments/1/2/photo.png")

    async def test_case_a_multiple_attachments_links_preserved(self):
        """Multiple attachments have extra files listed with clickable links."""
        guild = MagicMock(id=111, me=MagicMock())
        dest_channel = MagicMock(id=222, send=AsyncMock())
        dest_channel.permissions_for.return_value = SimpleNamespace(
            send_messages=True, embed_links=True
        )
        guild.get_channel.return_value = dest_channel

        # Set render_style to embed for simplicity
        settings = GuildQuoteSettings(guild_id=111, render_style="embed")
        await self.cog.storage.save_settings(111, settings)

        user = MagicMock(id=333, display_name="QuoterUser", roles=[])
        user.display_avatar.url = "https://cdn.discordapp.com/avatars/quoter.png"

        source_channel = MagicMock(
            id=444, name="general", send=AsyncMock(return_value=MagicMock(id=888))
        )
        source_channel.permissions_for.return_value = SimpleNamespace(
            read_messages=True, read_message_history=True, send_messages=True, embed_links=True
        )

        att1 = MagicMock(
            content_type="image/png",
            filename="first.png",
            url="https://cdn.discordapp.com/attachments/1/first.png",
        )
        att2 = MagicMock(
            content_type="image/png",
            filename="second.png",
            url="https://cdn.discordapp.com/attachments/1/second.png",
        )
        att3 = MagicMock(
            content_type="application/pdf",
            filename="document.pdf",
            url="https://cdn.discordapp.com/attachments/1/document.pdf",
        )
        source_msg = MagicMock(
            id=557,
            channel=source_channel,
            author=MagicMock(display_name="MultiUser", name="multi"),
            clean_content="Check all these files",
            attachments=[att1, att2, att3],
            created_at=MagicMock(strftime=lambda fmt: "Oct 21, 2026"),
        )

        respond_mock = AsyncMock()

        await self.cog._execute_quote(
            user=user,
            guild=guild,
            source_message=source_msg,
            respond_func=respond_mock,
            is_interaction=True,
        )

        call_kwargs = source_channel.send.call_args[1]
        sent_embed = call_kwargs["embed"]
        self.assertIn("🖼️ [second.png](https://cdn.discordapp.com/attachments/1/second.png)", sent_embed.description)
        self.assertIn("📎 [document.pdf](https://cdn.discordapp.com/attachments/1/document.pdf)", sent_embed.description)

    async def test_case_b_text_only_uses_pil_quote_card(self):
        """When source message has only text, a custom PIL quote card is rendered and attached."""
        guild = MagicMock(id=111, me=MagicMock())

        user = MagicMock(id=333, display_name="QuoterUser", roles=[])
        user.display_avatar.url = "https://cdn.discordapp.com/avatars/quoter.png"

        source_channel = MagicMock(id=444, name="general", send=AsyncMock())
        source_channel.permissions_for.return_value = SimpleNamespace(
            read_messages=True, read_message_history=True, send_messages=True, embed_links=True
        )

        source_author = MagicMock(display_name="Speaker", name="speaker")
        source_author.display_avatar.read = AsyncMock(return_value=None)

        source_msg = MagicMock(
            id=777,
            channel=source_channel,
            author=source_author,
            clean_content="This is pure wisdom spoken aloud.",
            attachments=[],
            created_at=MagicMock(strftime=lambda fmt: "Oct 21, 2026"),
        )

        respond_mock = AsyncMock()

        await self.cog._execute_quote(
            user=user,
            guild=guild,
            source_message=source_msg,
            respond_func=respond_mock,
            is_interaction=True,
        )

        source_channel.send.assert_called_once()
        call_kwargs = source_channel.send.call_args[1]
        sent_embed = call_kwargs["embed"]
        # File was attached
        self.assertIn("file", call_kwargs)
        self.assertEqual(call_kwargs["file"].filename, "quote.png")
        # Embed points to attachment
        self.assertEqual(sent_embed.image.url, "attachment://quote.png")
        # Embed description contains Jump link and NOT duplicate text
        self.assertIn("https://discord.com/channels/111/444/777", sent_embed.description)
        self.assertNotIn("This is pure wisdom", sent_embed.description)


class TestQuotePermissionsAndRemoval(unittest.IsolatedAsyncioTestCase):
    """Test permission validation, stateless removal denials, and privacy checks."""

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

        mock_interaction = MagicMock()
        mock_interaction.guild = MagicMock(id=guild_id)
        mock_interaction.message = MagicMock(id=quote_msg_id, delete=AsyncMock())
        mock_interaction.user = MagicMock(id=quoter_id)
        mock_interaction.user.guild_permissions = SimpleNamespace(manage_messages=False, administrator=False)
        mock_interaction.response = MagicMock(send_message=AsyncMock())

        custom_id = f"quote:delete:{quoter_id}"
        await self.cog.handle_quote_removal(mock_interaction, custom_id)

        mock_interaction.message.delete.assert_called_once()
        mock_interaction.response.send_message.assert_called_once()
        self.assertIn("Quote successfully removed", mock_interaction.response.send_message.call_args[0][0])

    async def test_moderator_removal_authorized(self):
        guild_id = 1000
        quote_msg_id = 2001
        quoter_id = 5000
        mod_id = 9000

        mock_interaction = MagicMock()
        mock_interaction.guild = MagicMock(id=guild_id)
        mock_interaction.message = MagicMock(id=quote_msg_id, delete=AsyncMock())
        mock_interaction.user = MagicMock(id=mod_id)
        mock_interaction.user.guild_permissions = SimpleNamespace(manage_messages=True, administrator=False)
        mock_interaction.response = MagicMock(send_message=AsyncMock())

        custom_id = f"quote:delete:{quoter_id}"
        await self.cog.handle_quote_removal(mock_interaction, custom_id)

        mock_interaction.message.delete.assert_called_once()
        self.assertIn("Quote successfully removed", mock_interaction.response.send_message.call_args[0][0])

    async def test_unauthorized_user_removal_denied(self):
        guild_id = 1000
        quote_msg_id = 2002
        quoter_id = 5000
        random_user_id = 7777

        mock_interaction = MagicMock()
        mock_interaction.guild = MagicMock(id=guild_id)
        mock_interaction.message = MagicMock(id=quote_msg_id, delete=AsyncMock(), embeds=[])
        mock_interaction.user = MagicMock(id=random_user_id)
        mock_interaction.user.guild_permissions = SimpleNamespace(manage_messages=False, administrator=False)
        mock_interaction.response = MagicMock(send_message=AsyncMock())

        custom_id = f"quote:delete:{quoter_id}"
        await self.cog.handle_quote_removal(mock_interaction, custom_id)

        mock_interaction.message.delete.assert_not_called()
        mock_interaction.response.send_message.assert_called_once()
        sent_text = mock_interaction.response.send_message.call_args[0][0]
        self.assertIn("Only the member who created this quote or a server moderator", sent_text)

    async def test_channel_privacy_check_blocks_inaccessible_messages(self):
        """User cannot quote from a channel they cannot read."""
        guild_id = 1000
        mock_guild = MagicMock(id=guild_id)
        mock_user = MagicMock(id=123)

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

        respond_mock.assert_called_once()
        self.assertIn("permission to view or quote", respond_mock.call_args[0][0])


if __name__ == "__main__":
    unittest.main()

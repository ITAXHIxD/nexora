"""
tests/test_embed_studio.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unit tests for Embed Studio, Discohook JSON parsing, permissions,
and server-scoped channel selection.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import unittest
from unittest.mock import MagicMock, AsyncMock
import discord
from discord.ext import commands

from cogs.premium.embed_studio import (
    parse_discohook_json,
    GuildChannelSelect,
    EmbedStudio,
)


class TestEmbedStudio(unittest.TestCase):
    def test_parse_standard_discohook(self):
        payload = """
        {
            "content": "Official Server Announcement @everyone",
            "embeds": [
                {
                    "title": "Guidelines Update",
                    "description": "Please review the updated guidelines below.",
                    "color": 5793266,
                    "fields": [
                        {"name": "Rule 1", "value": "Be respectful", "inline": true},
                        {"name": "Rule 2", "value": "No spamming", "inline": true}
                    ],
                    "author": {"name": "Nexora Staff", "icon_url": "https://example.com/icon.png"},
                    "footer": {"text": "Nexora Community · 2026"},
                    "image": {"url": "https://example.com/banner.png"},
                    "thumbnail": {"url": "https://example.com/thumb.png"}
                }
            ]
        }
        """
        content, embeds = parse_discohook_json(payload)
        self.assertEqual(content, "Official Server Announcement @everyone")
        self.assertEqual(len(embeds), 1)
        emb = embeds[0]
        self.assertEqual(emb.title, "Guidelines Update")
        self.assertEqual(emb.description, "Please review the updated guidelines below.")
        self.assertEqual(emb.color.value, 5793266)
        self.assertEqual(len(emb.fields), 2)
        self.assertEqual(emb.fields[0].name, "Rule 1")
        self.assertEqual(emb.fields[0].value, "Be respectful")
        self.assertTrue(emb.fields[0].inline)
        self.assertEqual(emb.author.name, "Nexora Staff")
        self.assertEqual(emb.footer.text, "Nexora Community · 2026")
        self.assertEqual(emb.image.url, "https://example.com/banner.png")
        self.assertEqual(emb.thumbnail.url, "https://example.com/thumb.png")

    def test_parse_markdown_codeblock_and_hex_color(self):
        payload = """
        ```json
        {
            "content": "Markdown wrapped test",
            "embeds": [
                {
                    "title": "Hex Color Embed",
                    "description": "Color is hex #5865F2",
                    "color": "#5865F2"
                }
            ]
        }
        ```
        """
        content, embeds = parse_discohook_json(payload)
        self.assertEqual(content, "Markdown wrapped test")
        self.assertEqual(len(embeds), 1)
        self.assertEqual(embeds[0].color.value, 0x5865F2)

    def test_parse_single_embed_dict(self):
        payload = '{"title": "Standalone Embed", "description": "Single dict", "color": "0x00D2FF"}'
        content, embeds = parse_discohook_json(payload)
        self.assertIsNone(content)
        self.assertEqual(len(embeds), 1)
        self.assertEqual(embeds[0].title, "Standalone Embed")
        self.assertEqual(embeds[0].color.value, 0x00D2FF)

    def test_parse_list_of_embeds(self):
        payload = '[{"title": "Embed 1"}, {"title": "Embed 2", "description": "Two"}]'
        content, embeds = parse_discohook_json(payload)
        self.assertIsNone(content)
        self.assertEqual(len(embeds), 2)
        self.assertEqual(embeds[0].title, "Embed 1")
        self.assertEqual(embeds[1].title, "Embed 2")

    def test_parse_leading_json_keyword(self):
        payload = 'json {"title": "Prefixed Embed", "description": "Works with n!embed_studio json {...}"}'
        content, embeds = parse_discohook_json(payload)
        self.assertIsNone(content)
        self.assertEqual(len(embeds), 1)
        self.assertEqual(embeds[0].title, "Prefixed Embed")

    def test_parse_invalid_json(self):
        with self.assertRaises(ValueError) as ctx:
            parse_discohook_json("this is not json {")
        self.assertIn("Invalid JSON syntax", str(ctx.exception))

    def test_parse_empty_json(self):
        with self.assertRaises(ValueError) as ctx:
            parse_discohook_json("{}")
        self.assertIn("does not contain", str(ctx.exception))

    def test_parse_content_over_limit(self):
        oversized = "a" * 2005
        payload = f'{{"content": "{oversized}"}}'
        with self.assertRaises(ValueError) as ctx:
            parse_discohook_json(payload)
        self.assertIn("exceeds Discord's 2,000 character limit", str(ctx.exception))

    def test_guild_channel_select_strictly_server_scoped(self):
        # Create mock guild with channels
        mock_guild = MagicMock(spec=discord.Guild)
        mock_me = MagicMock(spec=discord.Member)
        mock_guild.me = mock_me

        # Channel 1: accessible text channel
        ch1 = MagicMock(spec=discord.TextChannel)
        ch1.id = 111
        ch1.name = "announcements"
        ch1.category = None
        ch1.is_news = MagicMock(return_value=True)
        ch1.position = 0
        perms1 = MagicMock()
        perms1.send_messages = True
        perms1.embed_links = True
        ch1.permissions_for = MagicMock(return_value=perms1)

        # Channel 2: inaccessible channel (no perms)
        ch2 = MagicMock(spec=discord.TextChannel)
        ch2.id = 222
        ch2.name = "private-staff"
        ch2.category = None
        ch2.is_news = MagicMock(return_value=False)
        ch2.position = 1
        perms2 = MagicMock()
        perms2.send_messages = False
        perms2.embed_links = False
        ch2.permissions_for = MagicMock(return_value=perms2)

        # Channel 3: normal chat channel
        ch3 = MagicMock(spec=discord.TextChannel)
        ch3.id = 333
        ch3.name = "general"
        cat = MagicMock()
        cat.name = "Public"
        ch3.category = cat
        ch3.is_news = MagicMock(return_value=False)
        ch3.position = 2
        perms3 = MagicMock()
        perms3.send_messages = True
        perms3.embed_links = True
        ch3.permissions_for = MagicMock(return_value=perms3)

        mock_guild.channels = [ch1, ch2, ch3]

        callback_mock = AsyncMock()
        select = GuildChannelSelect(guild=mock_guild, on_select_callback=callback_mock)

        # Options must only contain ch1 and ch3; ch2 must be excluded!
        option_values = [opt.value for opt in select.options]
        self.assertIn("111", option_values)
        self.assertIn("333", option_values)
        self.assertNotIn("222", option_values)

        # Announcement channel must be prioritized first
        self.assertEqual(select.options[0].value, "111")
        self.assertEqual(select.options[0].label, "#announcements")
        self.assertEqual(select.options[0].emoji.name, "📢")

    def test_permission_unlocked_from_premium(self):
        mock_bot = MagicMock(spec=commands.Bot)
        cog = EmbedStudio(mock_bot)
        # EmbedStudio must have no _is_premium requirement blocking execution
        self.assertFalse(hasattr(cog, "_is_premium"))


if __name__ == "__main__":
    unittest.main()

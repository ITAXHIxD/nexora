"""
tests/test_birthday.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unit tests for BirthdayIntro:
  • 00:00 Midnight UTC & Server-Timezone scheduling
  • Embed, message, and mention formatting
  • 24/7 persistent wish buttons (timeout=None)
  • O(1) in-memory settings cache in on_message
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import datetime
import os
import shutil
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import discord

from cogs.utility.birthday_intro import (
    BirthdayAnnouncementView,
    BirthdayIntro,
    ServerBirthdaySetupView,
    build_birthday_announcement_payload,
    format_utc_offset,
    parse_flexible_date_input,
    safe_format_birthday_text,
)


class TestBirthdaySystem(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.mock_bot = MagicMock()
        self.mock_bot.mongo_db = None
        self.mock_bot.is_ready.return_value = False
        self.mock_bot.is_premium_guild.return_value = False

        self.cog = BirthdayIntro(self.mock_bot)
        self.cog.user_store_path = os.path.join(self.temp_dir, "birthday_data.json")
        self.cog.settings_store_path = os.path.join(self.temp_dir, "birthday_settings.json")
        self.cog.birthday_sent_path = os.path.join(self.temp_dir, "birthday_sent.json")

    async def asyncTearDown(self):
        if os.path.exists(self.temp_dir):
            shutil.rmtree(self.temp_dir)

    def test_midnight_00_00_utc_schedule_configured(self):
        """Verify daily_check is scheduled at 00:00 Midnight UTC (not 09:00 AM)."""
        loop_times = self.cog.daily_check.time
        self.assertIsNotNone(loop_times)
        first_time = loop_times[0] if isinstance(loop_times, list) else loop_times
        self.assertEqual(first_time.hour, 0)
        self.assertEqual(first_time.minute, 0)
        self.assertEqual(first_time.tzinfo, datetime.timezone.utc)

    def test_flexible_date_parsing(self):
        res1 = parse_flexible_date_input("April 15", 2002)
        self.assertIsNotNone(res1)
        self.assertEqual(res1[:3], (4, 15, 2002))

        res2 = parse_flexible_date_input("15th August 2004")
        self.assertIsNotNone(res2)
        self.assertEqual(res2[:3], (8, 15, 2004))

        res3 = parse_flexible_date_input("25/12/2001")
        self.assertIsNotNone(res3)
        self.assertEqual(res3[:3], (12, 25, 2001))

    def test_safe_format_birthday_text_placeholders(self):
        tpl = "Happy {age} Birthday {mention} ({user}) aka {name} in {server}! {unknown_brace}"
        out = safe_format_birthday_text(
            tpl,
            mention="<@123>",
            name="Surya",
            server="Nexora HQ",
            age=21,
        )
        self.assertIn("21st", out)
        self.assertIn("<@123>", out)
        self.assertIn("Surya", out)
        self.assertIn("Nexora HQ", out)
        self.assertIn("{unknown_brace}", out)

    def test_announcement_payload_mentions_and_styles(self):
        member = MagicMock(spec=discord.Member)
        member.id = 123456789
        member.mention = "<@123456789>"
        member.display_name = "Surya"
        member.display_avatar.url = "https://cdn.discordapp.com/avatars/1.png"

        guild = MagicMock(spec=discord.Guild)
        guild.id = 987654321
        guild.name = "Nexora Community"
        guild.icon = None

        ping_role = MagicMock(spec=discord.Role)
        ping_role.id = 555555
        ping_role.mention = "<@&555555>"

        now = datetime.datetime(2026, 4, 15, 0, 0, tzinfo=datetime.timezone.utc)
        doc = {
            "month": 4,
            "day": 15,
            "year": 2005,
            "name": "Surya",
            "pronouns": "he/him",
            "announcement_style": "both",
        }
        settings = {"utc_offset_minutes": 330}

        content, embed, allowed = build_birthday_announcement_payload(
            member=member,
            guild=guild,
            doc=doc,
            settings=settings,
            now=now,
            is_prem=False,
            ping_role=ping_role,
        )

        # Both member mention and ping_role mention must be in content
        self.assertIn("<@123456789>", content)
        self.assertIn("<@&555555>", content)
        self.assertIsNotNone(embed)
        self.assertIn("Happy Birthday, Surya!", embed.title)
        self.assertIn("21st", embed.description)
        self.assertIn("UTC+05:30", embed.footer.text)
        self.assertFalse(allowed.everyone)

        # Embed-only style still pings user and role in content
        doc_embed_only = {**doc, "announcement_style": "embed"}
        c_emb, e_emb, _ = build_birthday_announcement_payload(
            member=member,
            guild=guild,
            doc=doc_embed_only,
            settings=settings,
            now=now,
            ping_role=ping_role,
        )
        self.assertIn("<@123456789>", c_emb)
        self.assertIn("<@&555555>", c_emb)
        self.assertIsNotNone(e_emb)

    async def test_persistent_announcement_view_never_expires(self):
        view = BirthdayAnnouncementView(self.cog, uid=12345, guild_id=67890)
        self.assertIsNone(view.timeout)
        custom_ids = [c.custom_id for c in view.children]
        self.assertIn("bday:wish:67890:12345", custom_ids)
        self.assertIn("bday:wishers:67890:12345", custom_ids)

    async def test_on_message_uses_in_memory_cache_zero_io(self):
        # Populate in-memory cache for guild 111
        self.cog._settings_cache[111] = {"intro_channel_id": 999}
        self.cog._load_store = MagicMock(side_effect=AssertionError("Should not touch disk on non-intro message!"))

        msg = MagicMock(spec=discord.Message)
        msg.author.bot = False
        msg.guild = SimpleNamespace(id=111)
        msg.channel = SimpleNamespace(id=222)  # Not the intro channel (999)

        await self.cog.on_message(msg)
        self.cog._load_store.assert_not_called()

    def test_format_utc_offset(self):
        self.assertEqual(format_utc_offset(0), "UTC+00:00")
        self.assertEqual(format_utc_offset(330), "UTC+05:30")
        self.assertEqual(format_utc_offset(-300), "UTC-05:00")


if __name__ == "__main__":
    unittest.main()

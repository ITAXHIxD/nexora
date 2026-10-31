"""
tests/test_terminal_logger.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unit tests for TerminalLogger buffer, stream interception, ANSI
terminal formatting, online/offline/change logging, and verifying
that user commands are NOT logged.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import unittest
from unittest.mock import AsyncMock, MagicMock

from cogs.system.terminal_logger import (
    ANSI_ESCAPE,
    DiscordLoggingHandler,
    TerminalBuffer,
    TerminalLogger,
    format_ansi_terminal_line,
)


class TestTerminalLogger(unittest.IsolatedAsyncioTestCase):
    def test_buffer_push_pop(self):
        buf = TerminalBuffer(maxlen=10)
        buf.push("Line 1\n")
        buf.push("Line 2\r\n")
        self.assertEqual(len(buf), 2)

        batch = buf.pop_batch(max_lines=5)
        self.assertEqual(batch, ["Line 1", "Line 2"])
        self.assertEqual(len(buf), 0)

    def test_buffer_maxlen(self):
        buf = TerminalBuffer(maxlen=3)
        buf.push("A")
        buf.push("B")
        buf.push("C")
        buf.push("D")
        self.assertEqual(len(buf), 3)
        self.assertEqual(buf.pop_batch(), ["B", "C", "D"])

    def test_ansi_escape_cleaning_and_formatting(self):
        colored = "\033[96m\033[1mNEXORA SYSTEM\033[0m"
        clean = ANSI_ESCAPE.sub("", colored)
        self.assertEqual(clean, "NEXORA SYSTEM")

        err_line = format_ansi_terminal_line("[12:00:00] [ERROR] bot: Failed to connect")
        self.assertIn("\u001b[1;31m", err_line)

        online_line = format_ansi_terminal_line("[12:00:00] [ONLINE] 🟢 Bot is ONLINE")
        self.assertIn("\u001b[1;32m", online_line)

        offline_line = format_ansi_terminal_line("[12:00:00] [OFFLINE] 🔴 Bot shutting down")
        self.assertIn("\u001b[1;31m", offline_line)

    def test_logging_handler_emit(self):
        buf = TerminalBuffer(maxlen=10)
        handler = DiscordLoggingHandler(buf)
        test_logger = logging.getLogger("unit_test_terminal")
        test_logger.addHandler(handler)
        test_logger.setLevel(logging.INFO)

        test_logger.info("Hello Terminal Stream")
        self.assertEqual(len(buf), 1)
        line = buf.pop_batch()[0]
        self.assertIn("Hello Terminal Stream", line)
        self.assertIn("[INFO]", line)

    def test_ignored_loggers_not_emitted(self):
        buf = TerminalBuffer(maxlen=10)
        handler = DiscordLoggingHandler(buf)
        discord_logger = logging.getLogger("discord.http")
        discord_logger.addHandler(handler)
        discord_logger.setLevel(logging.INFO)

        discord_logger.info("Should be ignored")
        self.assertEqual(len(buf), 0)

    async def test_no_command_usage_listeners_and_lifecycle_events_logged(self):
        mock_bot = MagicMock()
        mock_bot.user = "Nexora#0001"
        mock_bot.guilds = [MagicMock(), MagicMock()]
        mock_bot.latency = 0.042
        cog = TerminalLogger(mock_bot)
        cog.buffer.pop_batch(100)  # Clear buffer

        # Must NOT have command usage listeners
        self.assertFalse(hasattr(cog, "on_command_completion"))
        self.assertFalse(hasattr(cog, "on_app_command_completion"))

        # Must log ONLINE, CHANGE, and OFFLINE events
        await cog.on_ready()
        lines = cog.buffer.pop_batch(10)
        self.assertTrue(any("[ONLINE]" in l for l in lines))

        mock_guild = MagicMock()
        mock_guild.name = "Owner Server"
        mock_guild.id = 12345
        mock_guild.member_count = 50
        await cog.on_guild_join(mock_guild)
        lines = cog.buffer.pop_batch(10)
        self.assertTrue(any("[CHANGE]" in l for l in lines))

        cog._flush_buffer_now = AsyncMock()
        await cog.close()
        lines = cog.buffer.pop_batch(10)
        self.assertTrue(any("[OFFLINE]" in l for l in lines))
        cog._flush_buffer_now.assert_called_once()


if __name__ == "__main__":
    unittest.main()

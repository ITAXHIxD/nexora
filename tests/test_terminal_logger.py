"""
tests/test_terminal_logger.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Unit tests for TerminalLogger buffer, stream interception, and
rate-limit batching.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import unittest
from unittest.mock import MagicMock, AsyncMock
from cogs.system.terminal_logger import (
    TerminalBuffer,
    DiscordLoggingHandler,
    ANSI_ESCAPE,
    TerminalLogger,
)
import logging


class TestTerminalLogger(unittest.TestCase):
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

    def test_ansi_escape_cleaning(self):
        colored = "\033[96m\033[1mNEXORA SYSTEM\033[0m"
        clean = ANSI_ESCAPE.sub("", colored)
        self.assertEqual(clean, "NEXORA SYSTEM")

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


if __name__ == "__main__":
    unittest.main()

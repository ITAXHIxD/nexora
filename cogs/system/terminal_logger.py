"""
cogs/system/terminal_logger.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Live Terminal & Console Output Streamer for Discord.

Intercepts Python logging and terminal stdout/stderr, streaming live
console logs directly into a dedicated Discord channel with batching,
rate-limit protection, and ANSI/syntax highlighting.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import collections
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    SUCCESS_COLOR,
    ERROR_COLOR,
    WARNING_COLOR,
    CYAN_COLOR,
)

logger = logging.getLogger(__name__)

# Pattern to strip ANSI escape codes if sending to non-ansi blocks or clean text
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Ignored loggers to prevent recursive loops and network noise
IGNORED_LOGGERS = {
    "discord",
    "discord.http",
    "discord.gateway",
    "discord.client",
    "discord.webhook",
    "aiohttp",
    "aiohttp.access",
    "aiohttp.client",
    "urllib3",
    "cogs.system.terminal_logger",
}


class TerminalBuffer:
    """Thread-safe ring buffer for terminal lines."""

    def __init__(self, maxlen: int = 500):
        self._deque = collections.deque(maxlen=maxlen)
        try:
            asyncio.get_running_loop()
            self._lock = asyncio.Lock()
        except RuntimeError:
            self._lock = None

    def push(self, line: str):
        clean = line.rstrip("\r\n")
        if clean:
            self._deque.append(clean)

    def pop_batch(self, max_lines: int = 40) -> list[str]:
        batch = []
        while self._deque and len(batch) < max_lines:
            batch.append(self._deque.popleft())
        return batch

    def __len__(self):
        return len(self._deque)


_GLOBAL_TERMINAL_BUFFER = TerminalBuffer(maxlen=600)


class DiscordLoggingHandler(logging.Handler):
    """Custom logging handler forwarding log records to the Discord buffer."""

    def __init__(self, buffer: TerminalBuffer):
        super().__init__()
        self.buffer = buffer
        self.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord):
        # Prevent recursion or spam from network / http libraries
        for ign in IGNORED_LOGGERS:
            if record.name == ign or record.name.startswith(f"{ign}."):
                return

        try:
            msg = self.format(record)
            self.buffer.push(msg)
        except Exception:
            self.handleError(record)


class StdoutInterceptor:
    """Tee wrapper for sys.stdout to capture raw print() and stdout lines."""

    def __init__(self, original_stream, buffer: TerminalBuffer):
        self.original_stream = original_stream
        self.buffer = buffer
        self._line_buffer = ""

    def write(self, data: str):
        # Write to original console first
        self.original_stream.write(data)
        try:
            self._line_buffer += data
            if "\n" in self._line_buffer:
                lines = self._line_buffer.split("\n")
                for line in lines[:-1]:
                    # Ignore empty whitespace or raw escape strings
                    stripped = ANSI_ESCAPE.sub("", line).strip()
                    if stripped and not any(ign in line for ign in ("GET /api/v", "POST /api/v")):
                        self.buffer.push(line)
                self._line_buffer = lines[-1]
        except Exception:
            pass

    def flush(self):
        self.original_stream.flush()

    def isatty(self):
        return getattr(self.original_stream, "isatty", lambda: False)()


class TerminalLogger(commands.Cog):
    """Streams live console output and terminal logs to a Discord channel."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.buffer = _GLOBAL_TERMINAL_BUFFER
        self.is_enabled = True
        self.target_channel_id: Optional[int] = None
        self._dispatch_task: Optional[asyncio.Task] = None
        self._is_sending = False
        self._setup_interception()

    def _setup_interception(self):
        # 1. Attach logging handler if not already attached
        root_logger = logging.getLogger()
        has_handler = any(isinstance(h, DiscordLoggingHandler) for h in root_logger.handlers)
        if not has_handler:
            self._log_handler = DiscordLoggingHandler(self.buffer)
            root_logger.addHandler(self._log_handler)

        # 2. Wrap sys.stdout
        if not isinstance(sys.stdout, StdoutInterceptor):
            self._stdout_wrapper = StdoutInterceptor(sys.stdout, self.buffer)
            sys.stdout = self._stdout_wrapper

    async def cog_load(self):
        self._dispatch_task = asyncio.create_task(self._log_dispatch_loop())

    async def cog_unload(self):
        if self._dispatch_task:
            self._dispatch_task.cancel()
        # Restore sys.stdout if we wrapped it
        if isinstance(sys.stdout, StdoutInterceptor):
            sys.stdout = sys.stdout.original_stream
        root_logger = logging.getLogger()
        root_logger.handlers = [h for h in root_logger.handlers if not isinstance(h, DiscordLoggingHandler)]

    def get_log_channel_id(self) -> Optional[int]:
        if self.target_channel_id:
            return self.target_channel_id
        env_val = os.getenv("TERMINAL_LOG_CHANNEL_ID") or os.getenv("CMD_LOG_CHANNEL_ID") or os.getenv("LOG_CHANNEL_ID")
        if env_val and env_val.strip().isdigit():
            return int(env_val.strip())
        return None

    async def get_log_channel(self) -> Optional[discord.TextChannel]:
        cid = self.get_log_channel_id()
        if not cid:
            return None
        channel = self.bot.get_channel(cid)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(cid)
            except Exception:
                return None
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _log_dispatch_loop(self):
        """Dispatches batched log lines every 2 seconds to avoid rate limits."""
        await self.bot.wait_until_ready()
        await asyncio.sleep(3.0)  # Allow ready tasks to settle

        while not self.bot.is_closed():
            try:
                await asyncio.sleep(2.0)
                if not self.is_enabled or len(self.buffer) == 0 or self._is_sending:
                    continue

                channel = await self.get_log_channel()
                if not channel:
                    continue

                lines = self.buffer.pop_batch(max_lines=35)
                if not lines:
                    continue

                # Group lines into chunks <= 1850 chars
                chunks = []
                current_chunk = []
                current_len = 0

                for line in lines:
                    # Strip ANSI codes for clear Discord code block rendering
                    clean_line = ANSI_ESCAPE.sub("", line).strip()
                    if not clean_line:
                        continue
                    line_len = len(clean_line) + 1
                    if current_len + line_len > 1850:
                        chunks.append("\n".join(current_chunk))
                        current_chunk = [clean_line]
                        current_len = line_len
                    else:
                        current_chunk.append(clean_line)
                        current_len += line_len

                if current_chunk:
                    chunks.append("\n".join(current_chunk))

                self._is_sending = True
                try:
                    for chunk in chunks[:3]:  # max 3 messages per interval
                        await channel.send(f"```ansi\n{chunk}\n```")
                        await asyncio.sleep(0.4)
                finally:
                    self._is_sending = False

            except asyncio.CancelledError:
                break
            except Exception as e:
                self._is_sending = False
                logger.debug("Terminal logger dispatch error: %s", e)
                await asyncio.sleep(5.0)

    # ── Control Commands ──────────────────────────────────────────────────────

    @commands.hybrid_group(name="terminal_logs", description="Manage live terminal and console logging to Discord", aliases=["cmdlogs", "consolelogs", "terminallog"])
    @commands.is_owner()
    async def terminal_logs(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await self.cmd_status(ctx)

    @terminal_logs.command(name="status", description="Check current terminal streaming status and target channel")
    @commands.is_owner()
    async def cmd_status(self, ctx: commands.Context):
        channel = await self.get_log_channel()
        channel_str = channel.mention if channel else f"`{self.get_log_channel_id() or 'Not configured'}`"
        status_str = "🟢 **Active & Streaming**" if self.is_enabled and channel else ("🟡 **Enabled (Waiting for Channel)**" if self.is_enabled else "🔴 **Disabled**")

        embed = discord.Embed(
            title="🖥️ Live Terminal Log Streamer",
            color=BRAND_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Stream Status", value=status_str, inline=True)
        embed.add_field(name="Target Channel", value=channel_str, inline=True)
        embed.add_field(name="Buffered Lines", value=f"`{len(self.buffer)}` queued", inline=True)
        embed.add_field(
            name="Configuration Guide",
            value=(
                "• Set channel: `n!terminal_logs set #channel` or in `.env` (`LOG_CHANNEL_ID` / `TERMINAL_LOG_CHANNEL_ID`)\n"
                "• Toggle stream: `n!terminal_logs toggle`\n"
                "• Force flush: `n!terminal_logs flush`\n"
                "• Send test log: `n!terminal_logs test`"
            ),
            inline=False,
        )
        embed.set_footer(text="Nexora Core System · Terminal Feed")
        await ctx.send(embed=embed, ephemeral=True)

    @terminal_logs.command(name="set", description="Set the target channel for live terminal logs")
    @commands.is_owner()
    async def cmd_set(self, ctx: commands.Context, channel: discord.TextChannel):
        perms = channel.permissions_for(channel.guild.me)
        if not perms.send_messages:
            return await ctx.send(f"❌ I don't have permission to send messages in {channel.mention}!", ephemeral=True)

        self.target_channel_id = channel.id
        self.is_enabled = True

        test_msg = (
            "```ansi\n"
            "\u001b[32m✔ [TERMINAL LOGS] Connected successfully to Nexora Core System.\u001b[0m\n"
            "Live console output will stream to this channel.\n"
            "```"
        )
        await channel.send(test_msg)
        await ctx.send(f"✅ **Terminal Log Channel Set**: Live terminal feed routed to {channel.mention}.", ephemeral=True)

    @terminal_logs.command(name="toggle", description="Toggle live terminal stream on or off")
    @commands.is_owner()
    async def cmd_toggle(self, ctx: commands.Context):
        self.is_enabled = not self.is_enabled
        status = "🟢 Enabled" if self.is_enabled else "🔴 Disabled"
        await ctx.send(f"**Terminal Stream Status**: {status}", ephemeral=True)

    @terminal_logs.command(name="flush", description="Manually flush all pending terminal lines to the log channel")
    @commands.is_owner()
    async def cmd_flush(self, ctx: commands.Context):
        channel = await self.get_log_channel()
        if not channel:
            return await ctx.send("❌ No terminal log channel configured.", ephemeral=True)

        count = len(self.buffer)
        lines = self.buffer.pop_batch(max_lines=50)
        if not lines:
            return await ctx.send("ℹ️ Terminal buffer is already empty.", ephemeral=True)

        clean_text = "\n".join(ANSI_ESCAPE.sub("", l) for l in lines)[:1850]
        await channel.send(f"```ansi\n{clean_text}\n```")
        await ctx.send(f"✅ Flushed {len(lines)} lines (was {count} pending) to {channel.mention}.", ephemeral=True)

    @terminal_logs.command(name="test", description="Send a test log message through the logger")
    @commands.is_owner()
    async def cmd_test(self, ctx: commands.Context):
        test_line = f"[{datetime.now().strftime('%H:%M:%S')}] [INFO] test_logger: Sample terminal log test line from {ctx.author}"
        self.buffer.push(test_line)
        await ctx.send(f"✅ Pushed test log line to buffer (`{len(self.buffer)}` in queue). It will dispatch within 2 seconds.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TerminalLogger(bot))
    logger.debug("Loaded TerminalLogger Cog")

"""
cogs/system/terminal_logger.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Bot Owner Terminal & Console Logger for Nexora.

Streams live terminal output (startup, online/offline status, errors,
warnings, tracebacks, and system/guild changes) strictly to a single
channel in the Bot Owner's server. Does NOT log user command usage.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import collections
import json
import logging
import os
import re
import sys
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands

from utils.config import LOG_CHANNEL_ID, OWNER_ID
from utils.ui import BRAND_COLOR

logger = logging.getLogger(__name__)

CONFIG_PATH = os.path.join("data", "terminal_logs_config.json")

# Pattern to strip existing ANSI escape codes before re-applying clean Discord ANSI colors
ANSI_ESCAPE = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")

# Ignored loggers to prevent recursive loops and low-level HTTP noise
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


def format_ansi_terminal_line(raw_line: str) -> str:
    """
    Formats a clean terminal line with Discord-compatible ANSI colors
    for errors, warnings, online/offline states, and system changes.
    """
    clean = ANSI_ESCAPE.sub("", raw_line).rstrip("\r\n")
    if not clean.strip():
        return ""

    upper = clean.upper()
    if any(k in upper for k in ("[ERROR]", "[CRITICAL]", "[OFFLINE]", "TRACEBACK", "EXCEPTION:", "ERROR:")):
        return f"\u001b[1;31m{clean}\u001b[0m"
    if any(k in upper for k in ("[WARNING]", "[WARN]", "[DISCONNECT]", "WARNING:")):
        return f"\u001b[1;33m{clean}\u001b[0m"
    if any(k in upper for k in ("[ONLINE]", "CONNECTED TO MONGODB", "LOADED ALL", "INITIALIZED AND AWAITING")):
        return f"\u001b[1;32m{clean}\u001b[0m"
    if any(k in upper for k in ("[CHANGE]", "[GUILD]", "[SYNC]", "APP COMMANDS SYNCED")):
        return f"\u001b[1;36m{clean}\u001b[0m"
    if "[INFO]" in upper:
        return re.sub(r"\[INFO\]", "\u001b[32m[INFO]\u001b[0m", clean, count=1)
    return clean


class TerminalBuffer:
    """Thread-safe ring buffer for terminal lines."""

    def __init__(self, maxlen: int = 600):
        self._deque = collections.deque(maxlen=maxlen)
        try:
            asyncio.get_running_loop()
            self._lock = asyncio.Lock()
        except RuntimeError:
            self._lock = None

    def push(self, line: str):
        clean = line.rstrip("\r\n")
        if not clean:
            return
        # Never buffer Discord internal HTTP/rate-limit/gateway warnings to prevent feedback loops
        if any(
            ign in clean
            for ign in (
                "discord.http",
                "We are being rate limited",
                "discord.gateway",
                "discord.client",
                "discord.webhook",
            )
        ):
            return
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
    """Custom logging handler forwarding Python log records to the terminal buffer."""

    def __init__(self, buffer: TerminalBuffer):
        super().__init__(level=logging.INFO)
        self.buffer = buffer
        self.setFormatter(
            logging.Formatter("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s", datefmt="%H:%M:%S")
        )

    def emit(self, record: logging.LogRecord):
        for ign in IGNORED_LOGGERS:
            if record.name == ign or record.name.startswith(f"{ign}."):
                return

        try:
            msg = self.format(record)
            self.buffer.push(msg)
        except Exception:
            self.handleError(record)


class StreamInterceptor:
    """Tee wrapper for sys.stdout and sys.stderr to capture print() and tracebacks."""

    def __init__(self, original_stream, buffer: TerminalBuffer, is_stderr: bool = False):
        self.original_stream = original_stream
        self.buffer = buffer
        self.is_stderr = is_stderr
        self._line_buffer = ""

    def write(self, data: str):
        try:
            self.original_stream.write(data)
        except Exception:
            pass
        try:
            self._line_buffer += data
            if "\n" in self._line_buffer:
                lines = self._line_buffer.split("\n")
                for line in lines[:-1]:
                    stripped = ANSI_ESCAPE.sub("", line).strip()
                    if not stripped:
                        continue
                    if any(ign in stripped for ign in ("GET /api/v", "POST /api/v")):
                        continue
                    # Avoid duplicating lines already formatted by DiscordLoggingHandler
                    if not self.is_stderr and re.match(r"^\[\d{2}:\d{2}:\d{2}\] \[(?:INFO|WARNING|ERROR|CRITICAL|DEBUG)\]", stripped):
                        continue
                    self.buffer.push(line)
                self._line_buffer = lines[-1]
        except Exception:
            pass

    def flush(self):
        try:
            self.original_stream.flush()
        except Exception:
            pass

    def isatty(self):
        return getattr(self.original_stream, "isatty", lambda: False)()


# Backward-compatible alias
StdoutInterceptor = StreamInterceptor


class TerminalLogger(commands.Cog):
    """
    Streams live console output (errors, changes, online/offline status)
    strictly to ONE channel in the Bot Owner's server.
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.buffer = _GLOBAL_TERMINAL_BUFFER
        self.config = self._load_config()
        self.is_enabled: bool = self.config.get("enabled", True)
        self.target_channel_id: Optional[int] = self.config.get("channel_id")
        self._dispatch_task: Optional[asyncio.Task] = None
        self._is_sending = False
        self._announced_online = False
        self._setup_interception()

    def _load_config(self) -> dict:
        os.makedirs("data", exist_ok=True)
        if os.path.exists(CONFIG_PATH):
            try:
                with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception:
                pass
        env_cid = os.getenv("TERMINAL_LOG_CHANNEL_ID") or LOG_CHANNEL_ID
        cid = int(str(env_cid).strip()) if env_cid and str(env_cid).strip().isdigit() else None
        return {"enabled": True, "channel_id": cid}

    def _save_config(self):
        os.makedirs("data", exist_ok=True)
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(
                    {"enabled": self.is_enabled, "channel_id": self.target_channel_id},
                    f,
                    indent=2,
                )
        except Exception:
            pass

    def _setup_interception(self):
        # 1. Attach logging handler to root logger if not already present
        root_logger = logging.getLogger()
        has_handler = any(isinstance(h, DiscordLoggingHandler) for h in root_logger.handlers)
        if not has_handler:
            self._log_handler = DiscordLoggingHandler(self.buffer)
            root_logger.addHandler(self._log_handler)

        # 2. Wrap sys.stdout for print() / startup banner
        if not isinstance(sys.stdout, StreamInterceptor):
            self._stdout_wrapper = StreamInterceptor(sys.stdout, self.buffer, is_stderr=False)
            sys.stdout = self._stdout_wrapper

        # 3. Wrap sys.stderr for unhandled exception tracebacks
        if not isinstance(sys.stderr, StreamInterceptor):
            self._stderr_wrapper = StreamInterceptor(sys.stderr, self.buffer, is_stderr=True)
            sys.stderr = self._stderr_wrapper

    async def cog_load(self):
        self._dispatch_task = asyncio.create_task(self._log_dispatch_loop())

    async def cog_unload(self):
        if self._dispatch_task:
            self._dispatch_task.cancel()
        if isinstance(sys.stdout, StreamInterceptor):
            sys.stdout = sys.stdout.original_stream
        if isinstance(sys.stderr, StreamInterceptor):
            sys.stderr = sys.stderr.original_stream
        root_logger = logging.getLogger()
        root_logger.handlers = [h for h in root_logger.handlers if not isinstance(h, DiscordLoggingHandler)]

    async def close(self):
        """Called automatically by bot.close() before shutdown to log OFFLINE state and flush."""
        ts = datetime.now().strftime("%H:%M:%S")
        bot_tag = str(self.bot.user) if self.bot.user else "Nexora"
        self.buffer.push(f"[{ts}] [OFFLINE] 🔴 {bot_tag} is shutting down and going OFFLINE.")
        await self._flush_buffer_now()

    def get_log_channel_id(self) -> Optional[int]:
        if self.target_channel_id:
            return self.target_channel_id
        env_val = os.getenv("TERMINAL_LOG_CHANNEL_ID") or LOG_CHANNEL_ID
        if env_val and str(env_val).strip().isdigit():
            return int(str(env_val).strip())
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
        if not isinstance(channel, discord.TextChannel):
            return None
        return channel

    async def _flush_buffer_now(self):
        """Sends at most 1 consolidated terminal message per cycle to prevent 429 rate limits."""
        if not self.is_enabled or len(self.buffer) == 0:
            return
        channel = await self.get_log_channel()
        if not channel:
            return

        current_chunk = []
        current_len = 0

        while self.buffer._deque and len(current_chunk) < 40:
            raw_line = self.buffer._deque[0]
            formatted = format_ansi_terminal_line(raw_line)
            if not formatted:
                self.buffer._deque.popleft()
                continue
            line_len = len(formatted) + 1
            if current_len + line_len > 1850 and current_chunk:
                break
            self.buffer._deque.popleft()
            current_chunk.append(formatted)
            current_len += line_len

        if not current_chunk:
            return

        chunk_str = "\n".join(current_chunk)[:1900]
        self._is_sending = True
        try:
            await channel.send(f"```ansi\n{chunk_str}\n```")
        except Exception:
            pass
        finally:
            self._is_sending = False

    async def _log_dispatch_loop(self):
        """Dispatches 1 batched terminal message every 5 seconds to stay well under Discord rate limits."""
        try:
            await self.bot.wait_until_ready()
        except RuntimeError:
            return
        await asyncio.sleep(4.0)

        while not self.bot.is_closed():
            try:
                await asyncio.sleep(5.0)
                if not self.is_enabled or len(self.buffer) == 0 or self._is_sending:
                    continue
                await self._flush_buffer_now()
            except asyncio.CancelledError:
                break
            except Exception:
                self._is_sending = False
                await asyncio.sleep(5.0)

    # ── Terminal Lifecycle & Change Listeners (NO command usage logging) ──────

    @commands.Cog.listener()
    async def on_ready(self):
        ts = datetime.now().strftime("%H:%M:%S")
        guilds = len(self.bot.guilds)
        ping_ms = round(self.bot.latency * 1000) if self.bot.latency and str(self.bot.latency) != "inf" else 0
        self.buffer.push(
            f"[{ts}] [ONLINE] 🟢 {self.bot.user} is ONLINE | Guilds: {guilds} | Ping: {ping_ms}ms"
        )

    @commands.Cog.listener()
    async def on_disconnect(self):
        ts = datetime.now().strftime("%H:%M:%S")
        self.buffer.push(f"[{ts}] [WARNING] ⚠️ Gateway disconnected from Discord.")

    @commands.Cog.listener()
    async def on_resumed(self):
        ts = datetime.now().strftime("%H:%M:%S")
        self.buffer.push(f"[{ts}] [ONLINE] 🟢 Gateway session resumed.")

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        ts = datetime.now().strftime("%H:%M:%S")
        self.buffer.push(
            f"[{ts}] [CHANGE] 📥 Joined server: {guild.name} (ID: {guild.id}, Members: {guild.member_count or 0}) | Total: {len(self.bot.guilds)}"
        )

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        ts = datetime.now().strftime("%H:%M:%S")
        self.buffer.push(
            f"[{ts}] [CHANGE] 📤 Left server: {guild.name} (ID: {guild.id}) | Total: {len(self.bot.guilds)}"
        )

    # ── Bot Owner Control Commands (Strictly Owner-Only) ─────────────────────

    @commands.group(name="terminal_logs", aliases=["cmdlogs", "consolelogs", "terminallog"])
    @commands.is_owner()
    async def terminal_logs(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await self.cmd_status(ctx)

    @terminal_logs.command(name="status", description="Check current terminal streaming status and owner channel")
    @commands.is_owner()
    async def cmd_status(self, ctx: commands.Context):
        channel = await self.get_log_channel()
        channel_str = f"{channel.mention} (`{channel.id}` in **{channel.guild.name}**)" if channel else f"`{self.get_log_channel_id() or 'Not configured'}`"
        status_str = (
            "🟢 **Active & Streaming**"
            if self.is_enabled and channel
            else ("🟡 **Enabled (Waiting for Channel)**" if self.is_enabled else "🔴 **Disabled**")
        )

        embed = discord.Embed(
            title="🖥️ Owner Terminal Log Streamer",
            description="Streams terminal console output (errors, online/offline status, and system changes) strictly to one channel in the Bot Owner's server.",
            color=BRAND_COLOR,
            timestamp=datetime.now(timezone.utc),
        )
        embed.add_field(name="Stream Status", value=status_str, inline=True)
        embed.add_field(name="Owner Channel", value=channel_str, inline=True)
        embed.add_field(name="Buffered Lines", value=f"`{len(self.buffer)}` queued", inline=True)
        embed.add_field(
            name="Owner Commands",
            value=(
                "• Set owner channel: `n!terminal_logs set #channel`\n"
                "• Toggle stream: `n!terminal_logs toggle`\n"
                "• Force flush: `n!terminal_logs flush`\n"
                "• Send test log: `n!terminal_logs test`"
            ),
            inline=False,
        )
        embed.set_footer(text="Nexora Core System · Owner Terminal Feed")
        await ctx.send(embed=embed, ephemeral=True)

    @terminal_logs.command(name="set", description="Set the single owner-server channel for live terminal logs")
    @commands.is_owner()
    async def cmd_set(self, ctx: commands.Context, channel: Optional[discord.TextChannel] = None):
        target = channel or ctx.channel
        if not isinstance(target, discord.TextChannel):
            return await ctx.send("❌ Please specify a valid text channel in your server.", ephemeral=True)

        # Ensure the channel is in a server where the bot owner is present/owner
        owner_id = self.bot.owner_id or OWNER_ID
        if target.guild.owner_id != owner_id and target.guild.get_member(owner_id) is None:
            return await ctx.send(
                "❌ The terminal logger can only be bound to a channel in the **Bot Owner's server**.",
                ephemeral=True,
            )

        perms = target.permissions_for(target.guild.me)
        if not perms.send_messages:
            return await ctx.send(f"❌ I don't have permission to send messages in {target.mention}!", ephemeral=True)

        self.target_channel_id = target.id
        self.is_enabled = True
        self._save_config()

        # Sync bot.log_channel to this single owner channel
        self.bot.log_channel = target

        ts = datetime.now().strftime("%H:%M:%S")
        test_msg = (
            "```ansi\n"
            f"\u001b[1;32m[{ts}] [ONLINE] ✔ Terminal Logger bound to #{target.name} ({target.guild.name})\u001b[0m\n"
            "\u001b[36mStreaming console output: errors, warnings, system changes, and online/offline states.\u001b[0m\n"
            "```"
        )
        await target.send(test_msg)
        await ctx.send(
            f"✅ **Owner Terminal Channel Set**: All console output is now routed exclusively to {target.mention}.",
            ephemeral=True,
        )

    @terminal_logs.command(name="toggle", description="Toggle live terminal stream on or off")
    @commands.is_owner()
    async def cmd_toggle(self, ctx: commands.Context):
        self.is_enabled = not self.is_enabled
        self._save_config()
        status = "🟢 Enabled" if self.is_enabled else "🔴 Disabled"
        await ctx.send(f"**Terminal Stream Status**: {status}", ephemeral=True)

    @terminal_logs.command(name="flush", description="Manually flush all pending terminal lines to the log channel")
    @commands.is_owner()
    async def cmd_flush(self, ctx: commands.Context):
        channel = await self.get_log_channel()
        if not channel:
            return await ctx.send("❌ No terminal log channel configured.", ephemeral=True)

        count = len(self.buffer)
        if count == 0:
            return await ctx.send("ℹ️ Terminal buffer is already empty.", ephemeral=True)

        await self._flush_buffer_now()
        await ctx.send(f"✅ Flushed `{count}` terminal lines to {channel.mention}.", ephemeral=True)

    @terminal_logs.command(name="test", description="Send a test log message through the terminal logger")
    @commands.is_owner()
    async def cmd_test(self, ctx: commands.Context):
        ts = datetime.now().strftime("%H:%M:%S")
        self.buffer.push(f"[{ts}] [INFO] terminal_test: Sample terminal log check triggered by {ctx.author}")
        await ctx.send(
            f"✅ Pushed test line to terminal buffer (`{len(self.buffer)}` queued). Dispatching to owner channel...",
            ephemeral=True,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TerminalLogger(bot))
    logger.debug("Loaded TerminalLogger Cog")

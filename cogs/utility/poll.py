"""
cogs/utility/poll.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Real-Time Polling Engine
Interactive buttons, live percentage progress bars, and anti-cheat tracking.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import datetime
import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.mod_utils import fmt_duration, parse_duration
from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    NexoraView,
    progress_bar,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)

EMOJI_NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣", "8️⃣", "9️⃣", "🔟"]


class InteractivePollView(NexoraView):
    """Modern Components V2 Live Interactive Poll Card."""

    def __init__(
        self,
        bot: commands.Bot,
        question: str,
        options: list[str],
        author: discord.abc.User,
        duration: Optional[datetime.timedelta] = None,
        timeout: Optional[float] = 86400,
    ):
        calc_timeout = min(duration.total_seconds(), 86400) if duration else 86400
        super().__init__(bot=bot, color=BRAND_COLOR, timeout=calc_timeout)
        self.question = question
        self.options = options
        self.author = author
        self.duration = duration
        self.end_time = (
            datetime.datetime.now(datetime.timezone.utc) + duration
            if duration
            else None
        )
        self.votes: dict[int, int] = {}  # user_id -> option_index
        self.is_closed = False
        self._build()

    def _build(self):
        self.clear_container()
        total_votes = len(self.votes)

        # Count per option
        counts = [0] * len(self.options)
        for opt_idx in self.votes.values():
            if 0 <= opt_idx < len(self.options):
                counts[opt_idx] += 1

        status_text = "🔒 **Poll Ended**" if self.is_closed else "🟢 **Active Poll**"
        due_str = f" · Closes {ts_format(self.end_time, 'R')}" if (self.end_time and not self.is_closed) else ""

        header = (
            f"# 📊 {self.question}\n"
            f"> {status_text}{due_str} · Total Votes: **{total_votes}**\n"
            f"Created by {self.author.mention}"
        )
        self.add_section(header, thumbnail_url=str(self.author.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        # Build options with progress bars
        option_lines = []
        for i, opt_name in enumerate(self.options):
            c = counts[i]
            pct = (c / total_votes * 100) if total_votes > 0 else 0.0
            pbar = progress_bar(c, total_votes or 1, length=12)
            emoji = EMOJI_NUMBERS[i] if i < len(EMOJI_NUMBERS) else f"[{i+1}]"
            option_lines.append(
                f"### {emoji} {opt_name}\n"
                f"`{pbar}` **{pct:.1f}%** ({c} vote{'s' if c != 1 else ''})"
            )

        self.add_text("\n\n".join(option_lines))

        if self.is_closed:
            # Announce winner
            if total_votes > 0:
                max_votes = max(counts)
                winners = [self.options[i] for i, c in enumerate(counts) if c == max_votes]
                winner_str = ", ".join(f"**{w}**" for w in winners)
                self.add_footer(f"🏆 Winning Choice: {winner_str} with {max_votes} vote(s)")
            else:
                self.add_footer("Poll closed with no votes cast.")
            return

        self.add_footer("Click an option below to vote or toggle your choice · One vote per member")

        # Build voting buttons in ActionRows (up to 5 buttons per row)
        row1_items = []
        row2_items = []

        for i in range(len(self.options)):
            emoji = EMOJI_NUMBERS[i] if i < len(EMOJI_NUMBERS) else None
            btn = discord.ui.Button(
                label=f"Option {i+1}",
                emoji=emoji,
                style=discord.ButtonStyle.primary,
                custom_id=f"poll-opt-{i}",
            )
            btn.callback = self._make_vote_callback(i)
            if i < 5:
                row1_items.append(btn)
            else:
                row2_items.append(btn)

        if row1_items:
            self.add_row(*row1_items)
        if row2_items:
            self.add_row(*row2_items)

        # End Poll Button (author or staff)
        end_btn = discord.ui.Button(
            label="End Poll",
            emoji="🛑",
            style=discord.ButtonStyle.danger,
            custom_id="poll-end",
        )
        end_btn.callback = self._on_end_poll
        self.add_row(end_btn)

    def _make_vote_callback(self, option_index: int):
        async def callback(interaction: discord.Interaction):
            user_id = interaction.user.id
            if self.is_closed:
                return await interaction.response.send_message("❌ This poll has already concluded.", ephemeral=True)

            if user_id in self.votes and self.votes[user_id] == option_index:
                del self.votes[user_id]
                msg = f"↩️ Removed your vote for **{self.options[option_index]}**."
            else:
                self.votes[user_id] = option_index
                msg = f"✅ Recorded your vote for **{self.options[option_index]}**!"

            self._build()
            await interaction.response.edit_message(view=self)
            try:
                await interaction.followup.send(msg, ephemeral=True)
            except Exception:
                pass

        return callback

    async def _on_end_poll(self, interaction: discord.Interaction):
        is_mod = (
            interaction.user.guild_permissions.manage_messages
            if interaction.guild
            else False
        )
        if interaction.user.id != self.author.id and not is_mod:
            return await interaction.response.send_message("❌ Only the poll creator or moderators can end this poll.", ephemeral=True)

        self.is_closed = True
        self.stop()
        self._build()
        await interaction.response.edit_message(view=self)

    async def on_timeout(self):
        if not self.is_closed:
            self.is_closed = True
            self._build()
            try:
                if self.message:
                    await self.message.edit(view=self)
            except Exception:
                pass


class Poll(commands.Cog):
    """Interactive Components V2 Polls."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="poll",
        description="📊 Create an interactive Components V2 button poll",
    )
    @app_commands.describe(
        question="The poll question",
        options="Comma or pipe separated options (up to 10). Leave blank for Yes/No",
        duration="Poll duration (e.g. 10m, 1h, 1d)",
    )
    @commands.guild_only()
    async def poll(
        self,
        ctx: commands.Context,
        question: str,
        options: Optional[str] = None,
        duration: Optional[str] = None,
    ):
        dur_td = None
        if duration:
            dur_td = parse_duration(duration)
            if not dur_td:
                return await ctx.send("❌ Invalid duration format. Examples: `10m`, `30m`, `1h`, `1d`", ephemeral=True)

        if options:
            sep = "|" if "|" in options else ","
            opt_list = [o.strip() for o in options.split(sep) if o.strip()]
        else:
            opt_list = ["Yes", "No"]

        if len(opt_list) < 2:
            return await ctx.send("❌ A poll must have at least **2 options**.", ephemeral=True)
        if len(opt_list) > 10:
            return await ctx.send("❌ A poll can have at most **10 options**.", ephemeral=True)

        view = InteractivePollView(
            bot=self.bot,
            question=question.strip(),
            options=opt_list,
            author=ctx.author,
            duration=dur_td,
        )

        msg = await send_view(ctx, view)
        logger.info("Poll: %s created poll '%s' with %d options", ctx.author, question, len(opt_list))

    @commands.command(
        name="quickpoll",
        description="⚡ Quick Yes/No poll with interactive voting buttons",
    )
    @commands.guild_only()
    async def quickpoll(self, ctx: commands.Context, *, question: str):
        view = InteractivePollView(
            bot=self.bot,
            question=question.strip(),
            options=["Yes 👍", "No 👎"],
            author=ctx.author,
            duration=None,
        )
        await send_view(ctx, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(Poll(bot))
    logger.debug("Loaded Poll")

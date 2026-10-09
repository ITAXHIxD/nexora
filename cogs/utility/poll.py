"""
cogs/utility/poll.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Real-Time Polling Engine.

Supports:
  • 2 to 6 Options (Minimum 2 required, Maximum 6 options)
  • Real-time Unicode percentage progress bars
  • Live button voting with instant toggle/switch capabilities
  • Dynamic option labeling directly on Discord action buttons
  • Auto-close timers (e.g. 10m, 1h, 1d) with relative timestamps
  • Rich winner proclamation upon conclusion
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import datetime
import logging
from typing import Optional, List

import discord
from discord import app_commands
from discord.ext import commands

from cogs.moderation.mod_utils import fmt_duration, parse_duration
from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    CYAN_COLOR,
    DismissButton,
    NexoraView,
    progress_bar,
    send_view,
    ts_format,
)

logger = logging.getLogger(__name__)

EMOJI_NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣"]


class InteractivePollView(NexoraView):
    """Modern Components V2 Live Interactive Poll Card with 2-6 options."""

    def __init__(
        self,
        bot: commands.Bot,
        question: str,
        options: List[str],
        author: discord.abc.User,
        duration: Optional[datetime.timedelta] = None,
        timeout: Optional[float] = 86400,
    ):
        calc_timeout = min(duration.total_seconds(), 86400) if duration else 86400
        super().__init__(bot=bot, color=BRAND_COLOR, timeout=calc_timeout)
        self.question = question
        self.options = options[:6]
        self.author = author
        self.duration = duration
        self.end_time = (
            datetime.datetime.now(datetime.timezone.utc) + duration
            if duration
            else None
        )
        self.votes: dict[int, int] = {}  # user_id -> option_index (0 to 5)
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

        if self.is_closed:
            status_text = "🔒 **Poll Concluded**"
            self._color = SUCCESS_COLOR if total_votes > 0 else WARNING_COLOR
        else:
            due_str = f" · Closes {ts_format(self.end_time, 'R')}" if self.end_time else ""
            status_text = f"🟢 **Active Poll**{due_str}"
            self._color = BRAND_COLOR

        header = (
            f"# 📊 {self.question}\n"
            f"> {status_text} · Total Votes: **{total_votes}**\n"
            f"Created by {self.author.mention}"
        )
        self.add_section(header, thumbnail_url=str(self.author.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        # Build options with visual progress bars
        option_lines = []
        for i, opt_name in enumerate(self.options):
            c = counts[i]
            pct = (c / total_votes * 100) if total_votes > 0 else 0.0
            pbar = progress_bar(c, total_votes or 1, length=12)
            emoji = EMOJI_NUMBERS[i]
            option_lines.append(
                f"### {emoji} {opt_name}\n"
                f"`{pbar}` **{pct:.1f}%** ({c} vote{'s' if c != 1 else ''})"
            )

        self.add_text("\n\n".join(option_lines))

        if self.is_closed:
            self.add_separator(discord.SeparatorSpacing.small)
            if total_votes > 0:
                max_votes = max(counts)
                winners = [self.options[i] for i, c in enumerate(counts) if c == max_votes]
                winner_str = ", ".join(f"**{w}**" for w in winners)
                self.add_text(f"### 🏆 Winning Choice\n> {winner_str} with **{max_votes}** vote(s) ({max_votes/total_votes*100:.1f}%)")
            else:
                self.add_text("### 🛑 Poll Result\n> No votes were cast in this poll.")

            self.add_footer("Poll closed · Thanks for participating!")
            self.add_row(DismissButton(user_id=self.author.id))
            return

        self.add_footer("Tap an option below to vote or switch your choice · 1 vote per member")

        # Build voting buttons
        # 2 options: Option 1 is Success (Green), Option 2 is Danger (Red)
        # 3-6 options: Primary / Secondary with clean labels
        row1_items = []
        row2_items = []

        is_two_opt = (len(self.options) == 2)

        for i, opt_text in enumerate(self.options):
            emoji = EMOJI_NUMBERS[i]
            # Truncate button label to max 70 chars to guarantee within Discord 80 char limit
            clean_label = opt_text[:60] if len(opt_text) > 60 else opt_text

            if is_two_opt:
                style = discord.ButtonStyle.success if i == 0 else discord.ButtonStyle.danger
            else:
                style = discord.ButtonStyle.primary if i < 3 else discord.ButtonStyle.secondary

            btn = discord.ui.Button(
                label=clean_label,
                emoji=emoji,
                style=style,
                custom_id=f"poll-btn-{i}",
            )
            btn.callback = self._make_vote_callback(i)

            if i < 3:
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
    """Interactive Components V2 Polls with 2 to 6 options."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="poll",
        description="📊 Create an interactive poll (2 to 6 options)",
    )
    @app_commands.describe(
        question="The question for the community to vote on",
        option1="First option (Required)",
        option2="Second option (Required)",
        option3="Third option (Optional)",
        option4="Fourth option (Optional)",
        option5="Fifth option (Optional)",
        option6="Sixth option (Optional)",
        duration="Poll duration (e.g. 10m, 1h, 1d)",
    )
    @commands.guild_only()
    async def poll(
        self,
        ctx: commands.Context,
        question: str,
        option1: str,
        option2: str,
        option3: Optional[str] = None,
        option4: Optional[str] = None,
        option5: Optional[str] = None,
        option6: Optional[str] = None,
        duration: Optional[str] = None,
    ):
        raw_options: List[str] = []

        for opt in [option1, option2, option3, option4, option5, option6]:
            if opt and opt.strip():
                raw_options.append(opt.strip())

        if len(raw_options) < 2:
            return await ctx.send(
                "❌ A poll must have at least **2 options**! Please provide both `option1` and `option2`.",
                ephemeral=True,
            )

        if len(raw_options) > 6:
            raw_options = raw_options[:6]

        dur_td = None
        if duration:
            dur_td = parse_duration(duration)
            if not dur_td:
                return await ctx.send("❌ Invalid duration format. Examples: `10m`, `30m`, `1h`, `1d`", ephemeral=True)

        view = InteractivePollView(
            bot=self.bot,
            question=question.strip(),
            options=raw_options,
            author=ctx.author,
            duration=dur_td,
        )

        await send_view(ctx, view)
        logger.info("Poll: %s created poll '%s' with %d options", ctx.author, question, len(raw_options))

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
    logger.debug("Loaded Poll Cog")

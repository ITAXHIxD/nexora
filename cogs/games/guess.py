"""
cogs/games/guess.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Number Guessing Game for Nexora Mini-Games.

Supports:
  • 🤖 Solo Mode: Guess the secret number (1-100) in 6 attempts with
    hot/cold feedback, higher/lower arrows, and narrowing bounds.
  • ⚔️ Multiplayer Duel: Turn-based race against a friend to deduce
    the secret number first!
  • 🎉 Open Party Lobby: Free-for-all for the whole channel! Anyone can
    participate, collaboratively narrowing bounds until someone hits it!
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import random
from typing import Optional, List, Tuple, Set, Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.game_stats import record_game
from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    CYAN_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)


class GuessModal(discord.ui.Modal, title="🔢 Enter Your Number Guess"):
    guess_input = discord.ui.TextInput(
        label="Your Guess (1 - 100)",
        placeholder="Enter a number between 1 and 100...",
        min_length=1,
        max_length=3,
        required=True,
    )

    def __init__(self, view: "GuessGameView"):
        super().__init__()
        self.game_view = view

    async def on_submit(self, interaction: discord.Interaction):
        val = self.guess_input.value.strip()
        if not val.isdigit():
            return await interaction.response.send_message("❌ Please enter a valid positive number!", ephemeral=True)

        guess_int = int(val)
        if guess_int < 1 or guess_int > 100:
            return await interaction.response.send_message("❌ Guess must be between 1 and 100.", ephemeral=True)

        await self.game_view.process_guess(interaction, guess_int)


class GuessGameView(NexoraView):
    """Interactive Number Guessing View supporting Solo, Duel, and Open Channel Party modes."""

    def __init__(
        self,
        bot: commands.Bot,
        player1: discord.Member,
        player2: Optional[discord.Member] = None,
        mode: str = "solo",  # "solo", "duel", "party"
        max_attempts: int = 6,
        timeout: float = 180.0,
    ):
        super().__init__(bot=bot, color=BRAND_COLOR, timeout=timeout)
        self.player1 = player1
        self.player2 = player2
        self.mode = mode.lower()
        self.max_attempts = 15 if self.mode == "party" else max_attempts
        self.secret_number = random.randint(1, 100)
        self.lower_bound = 1
        self.upper_bound = 100
        self.history: List[Tuple[str, int, str]] = []  # (player_name, guess, hint)
        self.participants: Set[int] = {player1.id}
        self.current_turn = player1
        self.winner: Optional[Union[discord.Member, discord.User]] = None
        self.is_game_over = False
        self._build_ui()

    async def _record_stats(self, winner_id: Optional[int]):
        try:
            if self.mode == "solo":
                outcome = "win" if (winner_id == self.player1.id) else "loss"
                await record_game(self.bot, self.player1.id, "guess", outcome)
            elif self.mode == "duel":
                for p in (self.player1, self.player2):
                    if p and not p.bot:
                        outcome = "win" if (winner_id == p.id) else "loss"
                        await record_game(self.bot, p.id, "guess", outcome)
            elif self.mode == "party":
                if winner_id:
                    await record_game(self.bot, winner_id, "guess", "win")
                for uid in self.participants:
                    if uid != winner_id:
                        await record_game(self.bot, uid, "guess", "loss")
        except Exception as e:
            logger.debug("Guess stats error: %s", e)

    def _build_ui(self):
        self.clear_container()

        if self.mode == "party":
            title_mode = "🎉 Open Party Challenge"
            vs_line = f"🌐 **Open Lobby** · Anyone in this channel can guess! ({len(self.participants)} players active)"
        elif self.mode == "duel":
            title_mode = "⚔️ 2-Player Guess Duel"
            vs_line = f"👤 **{self.player1.display_name}** vs 👤 **{self.player2.display_name}**"
        else:
            title_mode = "🤖 Solo Challenge"
            vs_line = f"👤 **{self.player1.display_name}** vs 🤖 **Nexora AI**"

        if self.winner:
            status_line = f"🏆 **Victory! {self.winner.mention} guessed the secret number `{self.secret_number}`!** 🎉"
            self._color = SUCCESS_COLOR
        elif self.is_game_over:
            status_line = f"💀 **Game Over! The secret number was `{self.secret_number}`.**"
            self._color = ERROR_COLOR
        else:
            if self.mode == "party":
                status_line = f"🎯 **Open Turn:** Tap below to guess! · Total Attempts: **{len(self.history)}/{self.max_attempts}**"
            elif self.mode == "duel":
                status_line = f"🎯 **Turn:** {self.current_turn.mention} · Round {len(self.history) + 1}"
            else:
                attempts_left = self.max_attempts - len(self.history)
                status_line = f"🎯 **Turn:** {self.player1.mention} · Attempts Left: **{attempts_left}**"

        range_bar = f"`[ {self.lower_bound} < ??? < {self.upper_bound} ]`"

        header = (
            f"# 🔢 Number Guessing · {title_mode}\n"
            f"> {vs_line}\n\n"
            f"{status_line}\n"
            f"• Narrowed Bounds: {range_bar}"
        )
        thumb = self.winner.display_avatar.url if self.winner else self.player1.display_avatar.url
        self.add_section(header, thumbnail_url=str(thumb))
        self.add_separator(discord.SeparatorSpacing.small)

        if self.history:
            history_lines = []
            for name, g_val, hint in self.history[-6:]:
                history_lines.append(f"• **{name}:** `{g_val}` ➔ {hint}")
            self.add_text("### 📜 Recent Guesses\n" + "\n".join(history_lines))
            self.add_separator(discord.SeparatorSpacing.small)

        if not self.is_game_over:
            btn_guess = discord.ui.Button(label="Make a Guess", emoji="🎯", style=discord.ButtonStyle.primary)
            btn_guess.callback = self._on_guess_click
            self.add_row(btn_guess)
            footer_text = "Free for all: anyone in chat can guess!" if self.mode == "party" else "Click 'Make a Guess' to input your number"
            self.add_footer(f"{footer_text} · 180s timeout")
        else:
            btn_again = discord.ui.Button(label="Play Again", emoji="🔄", style=discord.ButtonStyle.success)
            btn_again.callback = self._on_play_again
            self.add_row(btn_again, DismissButton(user_id=self.player1.id))
            self.add_footer("Nexora Mini-Games · Challenge finished")

    async def _on_guess_click(self, interaction: discord.Interaction):
        if self.mode == "solo":
            if interaction.user.id != self.player1.id:
                return await interaction.response.send_message("❌ This solo game belongs to someone else.", ephemeral=True)
        elif self.mode == "duel":
            if interaction.user.id != self.current_turn.id:
                if interaction.user.id in (self.player1.id, getattr(self.player2, "id", None)):
                    return await interaction.response.send_message("⏳ It is not your turn to guess!", ephemeral=True)
                return await interaction.response.send_message("❌ You are not a player in this duel.", ephemeral=True)
        elif self.mode == "party":
            # Anyone can participate!
            self.participants.add(interaction.user.id)

        await interaction.response.send_modal(GuessModal(self))

    async def process_guess(self, interaction: discord.Interaction, guess: int):
        self.participants.add(interaction.user.id)
        diff = abs(guess - self.secret_number)

        if guess == self.secret_number:
            self.winner = interaction.user
            self.is_game_over = True
            self.history.append((interaction.user.display_name, guess, "🎯 **EXACT HIT!**"))
            await self._record_stats(self.winner.id)
        else:
            direction = "⬆️ **Higher!**" if guess < self.secret_number else "⬇️ **Lower!**"
            warmth = "🔥 Sizzling Hot!" if diff <= 5 else ("🟡 Warm" if diff <= 15 else "❄️ Cold")
            hint_str = f"{direction} ({warmth})"

            # Narrow bounds
            if guess < self.secret_number and guess > self.lower_bound:
                self.lower_bound = guess
            elif guess > self.secret_number and guess < self.upper_bound:
                self.upper_bound = guess

            self.history.append((interaction.user.display_name, guess, hint_str))

            if self.mode in ("solo", "party"):
                if len(self.history) >= self.max_attempts:
                    self.is_game_over = True
                    await self._record_stats(None)
            elif self.mode == "duel":
                # Switch turn in duel
                self.current_turn = self.player2 if self.current_turn == self.player1 else self.player1
                try:
                    await interaction.channel.send(
                        f"🔔 {self.current_turn.mention}, it's your turn to guess! (Bounds: {self.lower_bound} - {self.upper_bound})",
                        delete_after=10,
                    )
                except Exception:
                    pass

        self._build_ui()
        await interaction.response.edit_message(view=self)

    async def _on_play_again(self, interaction: discord.Interaction):
        if self.mode == "duel":
            if interaction.user.id not in (self.player1.id, getattr(self.player2, "id", None)):
                return await interaction.response.send_message("❌ Only duel players can restart.", ephemeral=True)

        self.secret_number = random.randint(1, 100)
        self.lower_bound = 1
        self.upper_bound = 100
        self.history = []
        self.winner = None
        self.is_game_over = False
        self.current_turn = self.player1
        self._color = BRAND_COLOR
        self._build_ui()
        await interaction.response.edit_message(view=self)
        if self.mode == "duel":
            try:
                await interaction.channel.send(
                    f"🔔 Rematch started! {self.player1.mention} has the first guess!",
                    delete_after=10,
                )
            except Exception:
                pass


class NumberGuess(commands.Cog):
    """Number Guessing mini-game supporting solo, duel, and open party modes."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="guess",
        description="🔢 Guess the secret number (1-100) solo, duel a friend, or open a party lobby",
    )
    @app_commands.describe(
        opponent="Member to duel (leave blank for solo or party mode)",
        mode="Game mode: solo, duel, or party (open to entire channel)",
    )
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="🤖 Solo (6 attempts vs AI)", value="solo"),
            app_commands.Choice(name="⚔️ Duel (1v1 against opponent)", value="duel"),
            app_commands.Choice(name="🎉 Party Lobby (Free-for-all for entire channel)", value="party"),
        ]
    )
    @commands.guild_only()
    async def guess(
        self,
        ctx: commands.Context,
        opponent: Optional[discord.Member] = None,
        mode: Optional[str] = "solo",
    ):
        chosen_mode = (mode or "solo").lower()
        if opponent and opponent != ctx.author and not opponent.bot:
            chosen_mode = "duel"
        elif chosen_mode not in ("solo", "duel", "party"):
            chosen_mode = "solo"

        view = GuessGameView(
            bot=self.bot,
            player1=ctx.author,
            player2=opponent,
            mode=chosen_mode,
        )
        msg = await send_view(ctx, view)
        if msg and hasattr(view, "message"):
            view.message = msg

        if chosen_mode == "duel" and opponent:
            try:
                await ctx.channel.send(
                    f"🔔 {opponent.mention}, you were challenged to a Number Guessing Duel by {ctx.author.mention}! {ctx.author.mention} guesses first.",
                    delete_after=12,
                )
            except Exception:
                pass
        logger.info("Guess: %s launched %s game", ctx.author, chosen_mode)


async def setup(bot: commands.Bot):
    await bot.add_cog(NumberGuess(bot))
    logger.debug("Loaded NumberGuess Cog")

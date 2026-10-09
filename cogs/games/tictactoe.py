"""
cogs/games/tictactoe.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Tic-Tac-Toe Engine.

Supports both:
  1. 🤖 Solo Play (vs Automated Smart AI with Easy, Medium, Hard Minimax)
  2. ⚔️ 2-Player Multiplayer PvP Duel

Features:
  • Automatic AI counter-moves on player turn
  • Green win-line tile highlighting
  • Persistent session scoreboards (X Wins, O Wins, Draws)
  • One-click 🔄 Rematch / Play Again button
  • Automatic MongoDB game stats recording
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import random
from typing import Optional, List, Tuple, Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.game_stats import record_game
from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    PURPLE_COLOR,
    CYAN_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)

WINNING_COMBOS = [
    (0, 1, 2), (3, 4, 5), (6, 7, 8),  # Rows
    (0, 3, 6), (1, 4, 7), (2, 5, 8),  # Columns
    (0, 4, 8), (2, 4, 6),              # Diagonals
]


# ══════════════════════════════════════════════════════════════════
# AI MOVE ENGINE
# ══════════════════════════════════════════════════════════════════

def check_board_winner(board: List[Optional[str]]) -> Optional[str]:
    for a, b, c in WINNING_COMBOS:
        if board[a] and board[a] == board[b] == board[c]:
            return board[a]
    return None


def get_available_moves(board: List[Optional[str]]) -> List[int]:
    return [i for i, val in enumerate(board) if val is None]


def minimax(board: List[Optional[str]], depth: int, is_maximizing: bool, ai_sym: str, human_sym: str) -> int:
    winner = check_board_winner(board)
    if winner == ai_sym:
        return 10 - depth
    elif winner == human_sym:
        return depth - 10
    elif not get_available_moves(board):
        return 0

    if is_maximizing:
        best_score = -100
        for move in get_available_moves(board):
            board[move] = ai_sym
            score = minimax(board, depth + 1, False, ai_sym, human_sym)
            board[move] = None
            best_score = max(best_score, score)
        return best_score
    else:
        best_score = 100
        for move in get_available_moves(board):
            board[move] = human_sym
            score = minimax(board, depth + 1, True, ai_sym, human_sym)
            board[move] = None
            best_score = min(best_score, score)
        return best_score


def find_best_move(board: List[Optional[str]], ai_sym: str = "O", difficulty: str = "medium") -> Optional[int]:
    avail = get_available_moves(board)
    if not avail:
        return None

    diff = (difficulty or "medium").lower()
    human_sym = "X" if ai_sym == "O" else "O"

    if diff == "easy":
        # 70% random, 30% check for immediate win
        if random.random() < 0.7:
            return random.choice(avail)
        for move in avail:
            board[move] = ai_sym
            if check_board_winner(board) == ai_sym:
                board[move] = None
                return move
            board[move] = None
        return random.choice(avail)

    elif diff == "medium":
        # 1. Take immediate win
        for move in avail:
            board[move] = ai_sym
            if check_board_winner(board) == ai_sym:
                board[move] = None
                return move
            board[move] = None

        # 2. Block immediate human win
        for move in avail:
            board[move] = human_sym
            if check_board_winner(board) == human_sym:
                board[move] = None
                return move
            board[move] = None

        # 3. Take center if open
        if 4 in avail:
            return 4

        # 4. Take corners
        corners = [c for c in [0, 2, 6, 8] if c in avail]
        if corners:
            return random.choice(corners)

        return random.choice(avail)

    else:  # "hard" - Unbeatable Minimax
        best_score = -1000
        best_move = random.choice(avail)
        for move in avail:
            board[move] = ai_sym
            score = minimax(board, 0, False, ai_sym, human_sym)
            board[move] = None
            if score > best_score:
                best_score = score
                best_move = move
        return best_move


# ══════════════════════════════════════════════════════════════════
# TICTACTOE VIEW (SOLO & MULTIPLAYER)
# ══════════════════════════════════════════════════════════════════

class TicTacToeView(NexoraView):
    """Components V2 3x3 Tic-Tac-Toe Grid supporting Solo AI and 2-Player Duels."""

    def __init__(
        self,
        bot: commands.Bot,
        player_x: discord.Member,
        player_o: Optional[Union[discord.Member, discord.User]],
        is_solo: bool = False,
        difficulty: str = "medium",
        session_scores: Optional[dict] = None,
        timeout: float = 120.0,
    ):
        super().__init__(bot=bot, color=BRAND_COLOR, timeout=timeout)
        self.player_x = player_x
        self.is_solo = is_solo
        self.difficulty = difficulty
        self.player_o = player_o or bot.user
        self.current_player = player_x
        self.board: List[Optional[str]] = [None] * 9
        self.winner = None
        self.is_draw = False
        self.winning_line = None
        self.buttons: List[discord.ui.Button] = []
        self.scores = session_scores or {"X": 0, "O": 0, "draws": 0}
        self._build_board()

    async def _record_game_stats(self, winner_sym: Optional[str]):
        """Persist game session result via unified game stats engine."""
        try:
            if self.is_solo:
                outcome = "win" if winner_sym == "X" else ("loss" if winner_sym == "O" else "draw")
                await record_game(self.bot, self.player_x.id, "tictactoe", outcome)
            else:
                for p, sym in [(self.player_x, "X"), (self.player_o, "O")]:
                    if isinstance(p, (discord.Member, discord.User)) and not p.bot:
                        outcome = "win" if winner_sym == sym else ("loss" if winner_sym is not None else "draw")
                        await record_game(self.bot, p.id, "tictactoe", outcome)
        except Exception as e:
            logger.debug("TicTacToe stats record error: %s", e)

    def _build_board(self):
        self.clear_container()

        status_str = ""
        p_x_name = self.player_x.display_name
        p_o_name = f"Nexora AI ({self.difficulty.title()})" if self.is_solo else self.player_o.display_name

        if self.winner:
            if self.winner == self.player_x:
                status_str = f"🏆 **Winner: {self.player_x.mention}!** 🎉"
                self._color = SUCCESS_COLOR
            else:
                w_str = f"🤖 **Nexora AI ({self.difficulty.title()}) Wins!**" if self.is_solo else f"🏆 **Winner: {self.player_o.mention}!**"
                status_str = f"{w_str} Better luck next round!"
                self._color = ERROR_COLOR if self.is_solo else SUCCESS_COLOR
        elif self.is_draw:
            status_str = "🤝 **Game Draw! A battle of equals!**"
            self._color = WARNING_COLOR
        else:
            turn_symbol = "❌" if self.current_player == self.player_x else "⭕"
            p_turn = self.player_x.mention if self.current_player == self.player_x else (
                "🤖 *Nexora AI thinking...*" if self.is_solo else self.player_o.mention
            )
            status_str = f"🎮 **Turn:** {p_turn} ({turn_symbol})"

        score_line = f"Score: `{p_x_name}` **{self.scores['X']}**  |  `{p_o_name}` **{self.scores['O']}**  |  Draws **{self.scores['draws']}**"

        mode_badge = f"🤖 Solo Play ({self.difficulty.title()})" if self.is_solo else "⚔️ Multiplayer Duel"
        header = (
            f"# ⚔️ Tic-Tac-Toe · {mode_badge}\n"
            f"> ❌ **{p_x_name}** vs ⭕ **{p_o_name}**\n\n"
            f"{status_str}\n"
            f"-# {score_line}"
        )
        self.add_section(header, thumbnail_url=str(self.player_x.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        # 3x3 Button Grid
        self.buttons = []
        for i in range(9):
            val = self.board[i]
            label = "\u200b"
            style = discord.ButtonStyle.secondary

            if val == "X":
                label = "X"
                style = discord.ButtonStyle.primary
            elif val == "O":
                label = "O"
                style = discord.ButtonStyle.danger

            disabled = (val is not None) or (self.winner is not None) or self.is_draw

            btn = discord.ui.Button(
                label=label,
                style=style,
                disabled=disabled,
                custom_id=f"ttt-tile-{i}",
            )
            btn.callback = self._make_move_callback(i)
            self.buttons.append(btn)

        # Winning line highlight in green
        if self.winning_line:
            for idx in self.winning_line:
                self.buttons[idx].style = discord.ButtonStyle.success

        # Place 3 buttons per row
        self.add_row(self.buttons[0], self.buttons[1], self.buttons[2])
        self.add_row(self.buttons[3], self.buttons[4], self.buttons[5])
        self.add_row(self.buttons[6], self.buttons[7], self.buttons[8])

        # Bottom Action Row (Play Again / Rematch / Dismiss)
        if self.winner or self.is_draw:
            btn_play_again = discord.ui.Button(label="Play Again", emoji="🔄", style=discord.ButtonStyle.success, custom_id="ttt-again")
            btn_play_again.callback = self._on_play_again
            btn_dismiss = DismissButton(user_id=self.player_x.id)
            self.add_row(btn_play_again, btn_dismiss)
            self.add_footer("Click 'Play Again' for an instant rematch keeping current scores!")
        else:
            self.add_footer("90s turn timeout · Tap an open tile to make your move")

    def _find_win_combo(self) -> Tuple[Optional[str], Optional[Tuple[int, int, int]]]:
        for a, b, c in WINNING_COMBOS:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a], (a, b, c)
        return None, None

    def _make_move_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if not self.message and interaction.message:
                self.message = interaction.message

            if self.is_solo:
                if interaction.user.id != self.player_x.id:
                    return await interaction.response.send_message("❌ This solo game belongs to someone else.", ephemeral=True)
            else:
                if interaction.user.id != self.current_player.id:
                    if interaction.user.id in (self.player_x.id, self.player_o.id):
                        return await interaction.response.send_message("⏳ It is not your turn yet!", ephemeral=True)
                    return await interaction.response.send_message("❌ You are not a player in this duel.", ephemeral=True)

            if self.board[index] is not None or self.winner or self.is_draw:
                return await interaction.response.send_message("❌ That tile is already taken!", ephemeral=True)

            # Player makes move
            symbol = "X" if self.current_player == self.player_x else "O"
            self.board[index] = symbol

            win_sym, line = self._find_win_combo()
            if win_sym:
                self.winner = self.player_x if win_sym == "X" else self.player_o
                self.winning_line = line
                self.scores[win_sym] += 1
                await self._record_game_stats(win_sym)
            elif all(b is not None for b in self.board):
                self.is_draw = True
                self.scores["draws"] += 1
                await self._record_game_stats(None)
            else:
                # If Solo play vs AI, AI makes its move automatically!
                if self.is_solo:
                    ai_move = find_best_move(self.board, ai_sym="O", difficulty=self.difficulty)
                    if ai_move is not None:
                        self.board[ai_move] = "O"
                        ai_win, ai_line = self._find_win_combo()
                        if ai_win:
                            self.winner = self.player_o
                            self.winning_line = ai_line
                            self.scores["O"] += 1
                            await self._record_game_stats("O")
                        elif all(b is not None for b in self.board):
                            self.is_draw = True
                            self.scores["draws"] += 1
                            await self._record_game_stats(None)
                else:
                    # Switch turn to other player
                    self.current_player = self.player_o if self.current_player == self.player_x else self.player_x

            self._build_board()
            content = f"🔔 {self.current_player.mention}, it's your turn! (❌ vs ⭕)" if not self.is_solo and not self.winner and not self.is_draw else None
            await interaction.response.edit_message(content=content, view=self)

            if not self.is_solo and not self.winner and not self.is_draw:
                try:
                    await interaction.channel.send(
                        f"🔔 {self.current_player.mention}, it's your turn in Tic-Tac-Toe! Choose your tile.",
                        delete_after=10,
                    )
                except Exception:
                    pass

        return callback

    async def _on_play_again(self, interaction: discord.Interaction):
        if not self.message and interaction.message:
            self.message = interaction.message
        if interaction.user.id not in (self.player_x.id, getattr(self.player_o, "id", None)):
            return await interaction.response.send_message("❌ Only game participants can start a rematch.", ephemeral=True)

        self.board = [None] * 9
        self.winner = None
        self.is_draw = False
        self.winning_line = None
        self.current_player = self.player_x
        self._color = BRAND_COLOR
        self._build_board()
        content = f"🔔 {self.current_player.mention}, it's your turn! (❌ vs ⭕)" if not self.is_solo else None
        await interaction.response.edit_message(content=content, view=self)

        if not self.is_solo:
            try:
                await interaction.channel.send(
                    f"🔔 Rematch started! {self.current_player.mention} makes the first move (❌)!",
                    delete_after=10,
                )
            except Exception:
                pass

    async def on_timeout(self):
        if not self.winner and not self.is_draw:
            self.clear_container()
            p_o_name = "Nexora AI" if self.is_solo else self.player_o.mention
            self.add_section(
                f"# ⏱️ Game Timed Out\n"
                f"> Tic-Tac-Toe between {self.player_x.mention} and {p_o_name} was closed due to inactivity."
            )
            self.add_footer("Nexora Mini-Games")
            try:
                if self.message:
                    await self.message.edit(view=self)
            except Exception:
                pass


# ══════════════════════════════════════════════════════════════════
# COG COMMAND DEFINITIONS
# ══════════════════════════════════════════════════════════════════

class TicTacToe(commands.Cog):
    """Interactive Tic-Tac-Toe supporting both Solo Play (vs AI) and 2-Player Duels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="tictactoe",
        aliases=["ttt"],
        description="🎮 Play Tic-Tac-Toe solo against smart AI or challenge a friend",
    )
    @app_commands.describe(
        opponent="Member to duel (leave blank to play against Nexora AI)",
        difficulty="AI difficulty for solo play (easy, medium, hard)",
    )
    @app_commands.choices(
        difficulty=[
            app_commands.Choice(name="🟢 Easy (Casual)", value="easy"),
            app_commands.Choice(name="🟡 Medium (Balanced)", value="medium"),
            app_commands.Choice(name="🔴 Hard (Master Minimax)", value="hard"),
        ]
    )
    @commands.guild_only()
    async def tictactoe(
        self,
        ctx: commands.Context,
        opponent: Optional[discord.Member] = None,
        difficulty: Optional[str] = "medium",
    ):
        diff_clean = (difficulty or "medium").lower()
        if diff_clean not in ("easy", "medium", "hard"):
            diff_clean = "medium"

        # Check if Solo mode
        is_solo = False
        if opponent is None or opponent == ctx.author or opponent.bot:
            is_solo = True
            opponent = self.bot.user

        view = TicTacToeView(
            bot=self.bot,
            player_x=ctx.author,
            player_o=opponent,
            is_solo=is_solo,
            difficulty=diff_clean,
        )
        msg = await send_view(ctx, view)
        if msg and hasattr(view, "message"):
            view.message = msg

        if not is_solo:
            try:
                await ctx.channel.send(
                    f"🔔 {opponent.mention}, you were challenged to Tic-Tac-Toe by {ctx.author.mention}! {ctx.author.mention} makes the first move (❌).",
                    delete_after=12,
                )
            except Exception:
                pass
        logger.info(
            "TicTacToe: %s started %s game (Opponent: %s, Difficulty: %s)",
            ctx.author,
            "Solo" if is_solo else "Multiplayer",
            opponent,
            diff_clean,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TicTacToe(bot))
    logger.debug("Loaded TicTacToe Cog")

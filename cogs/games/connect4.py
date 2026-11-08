"""
cogs/games/connect4.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Connect 4 (Four-in-a-Row) Engine.

Supports:
  • 🤖 Solo Mode: Play against smart Nexora AI (Easy, Medium, Hard)
    with instant winning-drop logic, threat blocking, and column strategy.
  • ⚔️ 2-Player Multiplayer Duel: Turn-based battle (🔴 Red vs 🟡 Yellow).

Features:
  • 7 columns x 6 rows board with realistic gravity
  • Visual board rendering with winning chip highlights (🌟)
  • Column drop buttons with real-time full-column disabling
  • Persistent session scoreboards (Red, Yellow, Draws)
  • 🔄 Play Again rematch button keeping current session scores
  • MongoDB Atlas game stats integration
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import copy
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
    CYAN_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)

ROWS = 6
COLS = 7

COLUMN_NUMBERS = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣", "6️⃣", "7️⃣"]
EMPTY_SLOT = "⚪"
RED_SLOT = "🔴"
YELLOW_SLOT = "🟡"
WIN_SLOT = "🌟"


# ══════════════════════════════════════════════════════════════════
# CONNECT 4 LOGIC & AI
# ══════════════════════════════════════════════════════════════════

def create_board() -> List[List[Optional[str]]]:
    """Create an empty 6-row by 7-column board (None for empty)."""
    return [[None for _ in range(COLS)] for _ in range(ROWS)]


def get_lowest_empty_row(board: List[List[Optional[str]]], col: int) -> Optional[int]:
    """Return the row index (0-5) where a chip falls in the given column, or None if full."""
    for r in range(ROWS - 1, -1, -1):
        if board[r][col] is None:
            return r
    return None


def get_valid_columns(board: List[List[Optional[str]]]) -> List[int]:
    """Return list of columns that are not yet completely filled."""
    return [c for c in range(COLS) if board[0][c] is None]


def check_connect4_winner(board: List[List[Optional[str]]]) -> Tuple[Optional[str], List[Tuple[int, int]]]:
    """
    Check if either player has 4 in a row.
    Returns (winner_symbol, list_of_winning_coords) or (None, []).
    """
    # 1. Horizontal
    for r in range(ROWS):
        for c in range(COLS - 3):
            val = board[r][c]
            if val and val == board[r][c + 1] == board[r][c + 2] == board[r][c + 3]:
                return val, [(r, c), (r, c + 1), (r, c + 2), (r, c + 3)]

    # 2. Vertical
    for r in range(ROWS - 3):
        for c in range(COLS):
            val = board[r][c]
            if val and val == board[r + 1][c] == board[r + 2][c] == board[r + 3][c]:
                return val, [(r, c), (r + 1, c), (r + 2, c), (r + 3, c)]

    # 3. Diagonal down-right (\)
    for r in range(ROWS - 3):
        for c in range(COLS - 3):
            val = board[r][c]
            if val and val == board[r + 1][c + 1] == board[r + 2][c + 2] == board[r + 3][c + 3]:
                return val, [(r, c), (r + 1, c + 1), (r + 2, c + 2), (r + 3, c + 3)]

    # 4. Diagonal up-right (/)
    for r in range(3, ROWS):
        for c in range(COLS - 3):
            val = board[r][c]
            if val and val == board[r - 1][c + 1] == board[r - 2][c + 2] == board[r - 3][c + 3]:
                return val, [(r, c), (r - 1, c + 1), (r - 2, c + 2), (r - 3, c + 3)]

    return None, []


def find_ai_move(board: List[List[Optional[str]]], ai_sym: str = "Y", difficulty: str = "medium") -> Optional[int]:
    """
    Intelligent Connect 4 AI move selection.
    ai_sym is typically 'Y' (Yellow).
    """
    valid_cols = get_valid_columns(board)
    if not valid_cols:
        return None

    human_sym = "R" if ai_sym == "Y" else "Y"
    diff = (difficulty or "medium").lower()

    if diff == "easy":
        # 70% random, 30% check immediate win
        if random.random() < 0.7:
            return random.choice(valid_cols)
        for c in valid_cols:
            r = get_lowest_empty_row(board, c)
            if r is not None:
                board[r][c] = ai_sym
                w, _ = check_connect4_winner(board)
                board[r][c] = None
                if w == ai_sym:
                    return c
        return random.choice(valid_cols)

    # 1. Immediate Win Check
    for c in valid_cols:
        r = get_lowest_empty_row(board, c)
        if r is not None:
            board[r][c] = ai_sym
            w, _ = check_connect4_winner(board)
            board[r][c] = None
            if w == ai_sym:
                return c

    # 2. Immediate Block Opponent Win
    for c in valid_cols:
        r = get_lowest_empty_row(board, c)
        if r is not None:
            board[r][c] = human_sym
            w, _ = check_connect4_winner(board)
            board[r][c] = None
            if w == human_sym:
                return c

    # 3. Filter out suicide moves (moves that allow the human to win directly on the row above)
    safe_cols = []
    for c in valid_cols:
        r = get_lowest_empty_row(board, c)
        if r is not None and r > 0:
            board[r][c] = ai_sym
            board[r - 1][c] = human_sym
            w, _ = check_connect4_winner(board)
            board[r - 1][c] = None
            board[r][c] = None
            if w != human_sym:
                safe_cols.append(c)
        else:
            safe_cols.append(c)

    candidate_cols = safe_cols if safe_cols else valid_cols

    # 4. Positional strategy: center columns are vastly superior
    col_preference = [3, 2, 4, 1, 5, 0, 6]
    for pref in col_preference:
        if pref in candidate_cols:
            return pref

    return random.choice(candidate_cols)


# ══════════════════════════════════════════════════════════════════
# CONNECT 4 VIEW
# ══════════════════════════════════════════════════════════════════

class Connect4View(NexoraView):
    """Interactive Connect 4 Components V2 View with New-Message Rematch & Reply Turn Pings."""

    def __init__(
        self,
        bot: commands.Bot,
        player_r: discord.Member,
        player_y: Optional[Union[discord.Member, discord.User]],
        is_solo: bool = True,
        difficulty: str = "medium",
        session_scores: Optional[dict] = None,
        round_num: int = 1,
        starting_turn: str = "R",
        timeout: float = 180.0,
    ):
        super().__init__(bot=bot, color=BRAND_COLOR, timeout=timeout)
        self.player_r = player_r
        self.player_y = player_y or bot.user
        self.is_solo = is_solo
        self.difficulty = difficulty
        self.round_num = round_num
        self.board = create_board()
        self.current_turn = starting_turn if not is_solo else "R"
        self.winner_sym: Optional[str] = None
        self.winning_coords: List[Tuple[int, int]] = []
        self.is_draw = False
        self.rematch_started = False
        self.scores = session_scores or {"R": 0, "Y": 0, "draws": 0}
        self.turn_ping_msg: Optional[discord.Message] = None
        self._build_ui()

    async def _clear_turn_ping(self):
        if self.turn_ping_msg is not None:
            try:
                await self.turn_ping_msg.delete()
            except Exception:
                pass
            self.turn_ping_msg = None

    async def send_turn_ping(self, channel: Optional[discord.abc.Messageable], target_user: discord.abc.User, text: str):
        """Send a turn/chance ping that replies directly to the active match board and cleans up the old ping."""
        await self._clear_turn_ping()
        if channel is None:
            return
        try:
            ref = self.message.to_reference(fail_if_not_exists=False) if self.message else None
            self.turn_ping_msg = await channel.send(
                content=text,
                reference=ref,
                allowed_mentions=discord.AllowedMentions(users=[target_user], roles=False, everyone=False, replied_user=False),
                delete_after=30,
            )
        except Exception:
            pass

    async def _record_stats(self, winner: Optional[str]):
        """Persist game session result via unified game stats engine."""
        try:
            if self.is_solo:
                outcome = "win" if winner == "R" else ("loss" if winner == "Y" else "draw")
                await record_game(self.bot, self.player_r.id, "connect4", outcome)
            else:
                for p, sym in [(self.player_r, "R"), (self.player_y, "Y")]:
                    if isinstance(p, (discord.Member, discord.User)) and not p.bot:
                        outcome = "win" if winner == sym else ("loss" if winner is not None else "draw")
                        await record_game(self.bot, p.id, "connect4", outcome)
        except Exception as e:
            logger.debug("Connect4 stats error: %s", e)

    def _render_board_text(self) -> str:
        """Render board with emojis into Discord Markdown."""
        lines = [" ".join(COLUMN_NUMBERS)]
        win_set = set(self.winning_coords)

        for r in range(ROWS):
            row_emojis = []
            for c in range(COLS):
                if (r, c) in win_set:
                    row_emojis.append(WIN_SLOT)
                elif self.board[r][c] == "R":
                    row_emojis.append(RED_SLOT)
                elif self.board[r][c] == "Y":
                    row_emojis.append(YELLOW_SLOT)
                else:
                    row_emojis.append(EMPTY_SLOT)
            lines.append(" ".join(row_emojis))

        return "\n".join(lines)

    def _build_ui(self):
        self.clear_container()

        p_r_name = self.player_r.display_name
        p_y_name = f"Nexora AI ({self.difficulty.title()})" if self.is_solo else self.player_y.display_name

        if self.winner_sym:
            if self.winner_sym == "R":
                status_str = f"🏆 **Winner: {self.player_r.mention} (🔴 Red)!** 🎉"
                self._color = SUCCESS_COLOR
            else:
                w_str = f"🤖 **Nexora AI ({self.difficulty.title()}) Wins!**" if self.is_solo else f"🏆 **Winner: {self.player_y.mention} (🟡 Yellow)!**"
                status_str = f"{w_str} Four in a row!"
                self._color = ERROR_COLOR if self.is_solo else SUCCESS_COLOR
        elif self.is_draw:
            status_str = "🤝 **Board Full! Connect 4 Draw!**"
            self._color = WARNING_COLOR
        else:
            if self.current_turn == "R":
                turn_str = f"🔴 **Turn:** {self.player_r.mention}"
            else:
                turn_str = "🟡 **Turn:** 🤖 *Nexora AI thinking...*" if self.is_solo else f"🟡 **Turn:** {self.player_y.mention}"
            status_str = turn_str

        score_line = f"Round #{self.round_num}  ·  Score: `{p_r_name}` **{self.scores['R']}**  |  `{p_y_name}` **{self.scores['Y']}**  |  Draws **{self.scores['draws']}**"
        mode_label = f"🤖 Solo Play ({self.difficulty.title()})" if self.is_solo else "⚔️ Multiplayer Duel"

        header = (
            f"# 🔴🟡 Connect Four · {mode_label}\n"
            f"> 🔴 **{p_r_name}** vs 🟡 **{p_y_name}**\n\n"
            f"{status_str}\n"
            f"-# {score_line}"
        )
        self.add_section(header, thumbnail_url=str(self.player_r.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        # Render Game Board
        board_render = self._render_board_text()
        self.add_text(f"```\n{board_render}\n```")
        self.add_separator(discord.SeparatorSpacing.small)

        # Drop buttons (Columns 1-7)
        if not self.winner_sym and not self.is_draw:
            row1_btns = []
            for c in range(4):
                is_full = (self.board[0][c] is not None)
                btn = discord.ui.Button(
                    label=f"{c + 1}",
                    style=discord.ButtonStyle.primary if not is_full else discord.ButtonStyle.secondary,
                    disabled=is_full,
                    custom_id=f"c4-col-{c}",
                )
                btn.callback = self._make_drop_callback(c)
                row1_btns.append(btn)
            self.add_row(*row1_btns)

            row2_btns = []
            for c in range(4, 7):
                is_full = (self.board[0][c] is not None)
                btn = discord.ui.Button(
                    label=f"{c + 1}",
                    style=discord.ButtonStyle.primary if not is_full else discord.ButtonStyle.secondary,
                    disabled=is_full,
                    custom_id=f"c4-col-{c}",
                )
                btn.callback = self._make_drop_callback(c)
                row2_btns.append(btn)
            self.add_row(*row2_btns)

            self.add_footer("Tap a column number (1-7) to drop your chip · 180s timeout")
        else:
            if self.rematch_started:
                btn_done = discord.ui.Button(
                    label="Rematch Started Below",
                    emoji="✅",
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                )
                self.add_row(btn_done, DismissButton(user_id=self.player_r.id))
            else:
                btn_again = discord.ui.Button(label="Play Again", emoji="🔄", style=discord.ButtonStyle.success)
                btn_again.callback = self._on_play_again
                btn_dismiss = DismissButton(user_id=self.player_r.id)
                self.add_row(btn_again, btn_dismiss)
            self.add_footer("Nexora Mini-Games · Click 'Play Again' to spawn a brand-new rematch board!")

    def _make_drop_callback(self, col: int):
        async def callback(interaction: discord.Interaction):
            if not self.message and interaction.message:
                self.message = interaction.message

            if self.is_solo:
                if interaction.user.id != self.player_r.id:
                    return await interaction.response.send_message("❌ This solo game belongs to someone else.", ephemeral=True)
            else:
                expected_user = self.player_r if self.current_turn == "R" else self.player_y
                if interaction.user.id != expected_user.id:
                    if interaction.user.id in (self.player_r.id, getattr(self.player_y, "id", None)):
                        return await interaction.response.send_message("⏳ It is not your turn yet!", ephemeral=True)
                    return await interaction.response.send_message("❌ You are not a player in this duel.", ephemeral=True)

            r = get_lowest_empty_row(self.board, col)
            if r is None or self.winner_sym or self.is_draw:
                return await interaction.response.send_message("❌ That column is already full!", ephemeral=True)

            # Player drops chip
            self.board[r][col] = self.current_turn
            w, coords = check_connect4_winner(self.board)
            if w:
                self.winner_sym = w
                self.winning_coords = coords
                self.scores[w] += 1
                await self._record_stats(w)
            elif not get_valid_columns(self.board):
                self.is_draw = True
                self.scores["draws"] += 1
                await self._record_stats(None)
            else:
                if self.is_solo:
                    # AI takes its turn
                    ai_col = find_ai_move(self.board, ai_sym="Y", difficulty=self.difficulty)
                    if ai_col is not None:
                        ai_r = get_lowest_empty_row(self.board, ai_col)
                        if ai_r is not None:
                            self.board[ai_r][ai_col] = "Y"
                            ai_w, ai_coords = check_connect4_winner(self.board)
                            if ai_w:
                                self.winner_sym = ai_w
                                self.winning_coords = ai_coords
                                self.scores["Y"] += 1
                                await self._record_stats("Y")
                            elif not get_valid_columns(self.board):
                                self.is_draw = True
                                self.scores["draws"] += 1
                                await self._record_stats(None)
                else:
                    # Switch turn
                    self.current_turn = "Y" if self.current_turn == "R" else "R"

            self._build_ui()
            next_user = self.player_r if self.current_turn == "R" else self.player_y
            await interaction.response.edit_message(view=self)

            if self.winner_sym or self.is_draw:
                await self._clear_turn_ping()
            elif not self.is_solo:
                chip_badge = "🔴 Red" if self.current_turn == "R" else "🟡 Yellow"
                await self.send_turn_ping(
                    interaction.channel,
                    next_user,
                    f"🎯 **Your Chance!** {next_user.mention} — it's your turn ({chip_badge}) in **Connect 4**! *(Drop a chip in columns 1–7 on the replied board)*",
                )

        return callback

    async def _on_play_again(self, interaction: discord.Interaction):
        if not self.message and interaction.message:
            self.message = interaction.message
        if interaction.user.id not in (self.player_r.id, getattr(self.player_y, "id", None)):
            return await interaction.response.send_message("❌ Only game participants can start a rematch.", ephemeral=True)

        await self._clear_turn_ping()
        self.rematch_started = True
        self._build_ui()
        self.stop()
        await interaction.response.edit_message(view=self)

        next_round = self.round_num + 1
        next_turn = ("Y" if next_round % 2 == 0 else "R") if not self.is_solo else "R"

        new_view = Connect4View(
            bot=self.bot,
            player_r=self.player_r,
            player_y=self.player_y,
            is_solo=self.is_solo,
            difficulty=self.difficulty,
            session_scores=dict(self.scores),
            round_num=next_round,
            starting_turn=next_turn,
        )
        new_msg = None
        if interaction.channel:
            try:
                ref = self.message.to_reference(fail_if_not_exists=False) if self.message else None
                new_msg = await interaction.channel.send(
                    view=new_view,
                    reference=ref,
                    allowed_mentions=discord.AllowedMentions.none(),
                )
            except Exception:
                new_msg = None
        if new_msg is None:
            try:
                new_msg = await interaction.followup.send(view=new_view, wait=True)
            except Exception:
                pass
        if new_msg:
            new_view.message = new_msg

        if not self.is_solo and interaction.channel:
            starter = self.player_r if next_turn == "R" else self.player_y
            chip_badge = "🔴 Red" if next_turn == "R" else "🟡 Yellow"
            await new_view.send_turn_ping(
                interaction.channel,
                starter,
                f"🔄 **Rematch Round #{next_round}!** 🎯 **Your Chance:** {starter.mention} drops first ({chip_badge}) on the replied board!",
            )

    async def on_timeout(self):
        await self._clear_turn_ping()
        await super().on_timeout()


# ══════════════════════════════════════════════════════════════════
# CONNECT 4 COG
# ══════════════════════════════════════════════════════════════════

class Connect4(commands.Cog):
    """Interactive Connect 4 supporting both Solo Mode (vs AI) and 2-Player Duels."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="connect4",
        aliases=["c4", "fourinrow"],
        description="🎮 Play Connect 4 solo against Nexora AI or challenge a friend",
    )
    @app_commands.describe(
        opponent="Member to duel (leave blank to play against Nexora AI)",
        difficulty="AI difficulty for solo play (easy, medium, hard)",
    )
    @app_commands.choices(
        difficulty=[
            app_commands.Choice(name="🟢 Easy (Casual)", value="easy"),
            app_commands.Choice(name="🟡 Medium (Balanced)", value="medium"),
            app_commands.Choice(name="🔴 Hard (Tactical)", value="hard"),
        ]
    )
    async def connect4(
        self,
        ctx: commands.Context,
        opponent: Optional[Union[discord.Member, discord.User]] = None,
        difficulty: Optional[str] = "medium",
    ):
        diff_clean = (difficulty or "medium").lower()
        if diff_clean not in ("easy", "medium", "hard"):
            diff_clean = "medium"

        is_solo = False
        if opponent is None or opponent == ctx.author or opponent.bot:
            is_solo = True
            opponent = self.bot.user

        view = Connect4View(
            bot=self.bot,
            player_r=ctx.author,
            player_y=opponent,
            is_solo=is_solo,
            difficulty=diff_clean,
        )
        msg = await send_view(ctx, view)
        if msg and hasattr(view, "message"):
            view.message = msg

        if not is_solo:
            await view.send_turn_ping(
                ctx.channel,
                opponent,
                f"⚔️ **Connect 4 Challenge!** {opponent.mention}, you were challenged by {ctx.author.mention}! 🎯 **First Chance:** {ctx.author.mention} (🔴 Red) on the replied board!",
            )
        logger.info(
            "Connect4: %s started %s game (Opponent: %s, Diff: %s)",
            ctx.author,
            "Solo" if is_solo else "Duel",
            opponent,
            diff_clean,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(Connect4(bot))
    logger.debug("Loaded Connect4 Cog")

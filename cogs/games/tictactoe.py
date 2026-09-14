"""
cogs/games/tictactoe.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Tic-Tac-Toe Engine
Full 2-player 3x3 button grid game with turn management and win-line highlighting.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)


class TicTacToeView(NexoraView):
    """Components V2 3x3 Tic-Tac-Toe Button Grid."""

    WINNING_COMBOS = [
        (0, 1, 2), (3, 4, 5), (6, 7, 8),  # Rows
        (0, 3, 6), (1, 4, 7), (2, 5, 8),  # Columns
        (0, 4, 8), (2, 4, 6),              # Diagonals
    ]

    def __init__(
        self,
        bot: commands.Bot,
        player_x: discord.Member,
        player_o: discord.Member,
        timeout: float = 90.0,
    ):
        super().__init__(bot=bot, color=BRAND_COLOR, timeout=timeout)
        self.player_x = player_x
        self.player_o = player_o
        self.current_player = player_x
        self.board = [None] * 9  # None, "X", or "O"
        self.winner = None
        self.is_draw = False
        self.buttons: list[discord.ui.Button] = []
        self._build_board()

    def _build_board(self):
        self.clear_container()

        status_str = ""
        if self.winner:
            status_str = f"🏆 **Winner: {self.winner.mention}!**"
            self._color = SUCCESS_COLOR
        elif self.is_draw:
            status_str = "🤝 **Game Draw! Well played both!**"
            self._color = WARNING_COLOR
        else:
            turn_symbol = "❌" if self.current_player == self.player_x else "⭕"
            status_str = f"🎮 Turn: {self.current_player.mention} ({turn_symbol})"

        header = (
            f"# ⚔️ Tic-Tac-Toe Showdown\n"
            f"> ❌ **{self.player_x.display_name}** vs ⭕ **{self.player_o.display_name}**\n\n"
            f"{status_str}"
        )
        self.add_section(header)
        self.add_separator(discord.SeparatorSpacing.small)

        # Create 3x3 buttons
        self.buttons = []
        for i in range(9):
            val = self.board[i]
            label = "\u200b"
            style = discord.ButtonStyle.secondary
            emoji = None

            if val == "X":
                label = "X"
                style = discord.ButtonStyle.primary
            elif val == "O":
                label = "O"
                style = discord.ButtonStyle.danger

            # If finished, disable
            disabled = (val is not None) or (self.winner is not None) or self.is_draw

            btn = discord.ui.Button(
                label=label,
                style=style,
                disabled=disabled,
                custom_id=f"ttt-{i}",
            )
            btn.callback = self._make_move_callback(i)
            self.buttons.append(btn)

        # Highlight winning buttons in green
        if self.winner:
            winning_symbol = "X" if self.winner == self.player_x else "O"
            for a, b, c in self.WINNING_COMBOS:
                if self.board[a] == self.board[b] == self.board[c] == winning_symbol:
                    for idx in (a, b, c):
                        self.buttons[idx].style = discord.ButtonStyle.success
                    break

        # Group into 3 ActionRows
        self.add_row(self.buttons[0], self.buttons[1], self.buttons[2])
        self.add_row(self.buttons[3], self.buttons[4], self.buttons[5])
        self.add_row(self.buttons[6], self.buttons[7], self.buttons[8])

        if not self.winner and not self.is_draw:
            self.add_footer("90s turn timeout · Click an open tile to make your move")
        else:
            self.add_footer("Nexora Mini-Games · Game finished")

    def _check_win(self) -> Optional[str]:
        for a, b, c in self.WINNING_COMBOS:
            if self.board[a] and self.board[a] == self.board[b] == self.board[c]:
                return self.board[a]
        return None

    def _make_move_callback(self, index: int):
        async def callback(interaction: discord.Interaction):
            if interaction.user.id != self.current_player.id:
                if interaction.user.id in (self.player_x.id, self.player_o.id):
                    return await interaction.response.send_message("⏳ It is not your turn yet!", ephemeral=True)
                return await interaction.response.send_message("❌ You are not a player in this game.", ephemeral=True)

            if self.board[index] is not None or self.winner or self.is_draw:
                return await interaction.response.send_message("❌ That tile is already taken!", ephemeral=True)

            symbol = "X" if self.current_player == self.player_x else "O"
            self.board[index] = symbol

            win_symbol = self._check_win()
            if win_symbol:
                self.winner = self.player_x if win_symbol == "X" else self.player_o
                self.stop()
            elif all(b is not None for b in self.board):
                self.is_draw = True
                self.stop()
            else:
                # Switch turn
                self.current_player = (
                    self.player_o if self.current_player == self.player_x else self.player_x
                )

            self._build_board()
            await interaction.response.edit_message(view=self)

        return callback

    async def on_timeout(self):
        if not self.winner and not self.is_draw:
            self.clear_container()
            self.add_section(
                f"# ⏱️ Game Timed Out\n"
                f"> Tic-Tac-Toe between {self.player_x.mention} and {self.player_o.mention} was cancelled due to inactivity."
            )
            self.add_footer("Nexora Mini-Games")
            try:
                if self.message:
                    await self.message.edit(view=self)
            except Exception:
                pass


class TicTacToe(commands.Cog):
    """Interactive Tic-Tac-Toe mini-game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="tictactoe",
        aliases=["ttt"],
        description="🎮 Challenge a server member to an interactive game of Tic-Tac-Toe",
    )
    @app_commands.describe(opponent="The member you want to challenge")
    @commands.guild_only()
    async def tictactoe(self, ctx: commands.Context, opponent: discord.Member):
        if opponent == ctx.author:
            return await ctx.send("❌ You cannot play Tic-Tac-Toe against yourself!", ephemeral=True)
        if opponent.bot:
            return await ctx.send("❌ You cannot play against a bot!", ephemeral=True)

        view = TicTacToeView(
            bot=self.bot,
            player_x=ctx.author,
            player_o=opponent,
        )
        await send_view(ctx, view)
        logger.info("TicTacToe: %s challenged %s", ctx.author, opponent)


async def setup(bot: commands.Bot):
    await bot.add_cog(TicTacToe(bot))
    logger.debug("Loaded TicTacToe")

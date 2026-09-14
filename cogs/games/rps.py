"""
cogs/games/rps.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Rock-Paper-Scissors Engine
Supports both Solo (vs Bot) and 2-Player duel modes with interactive buttons.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import random
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)

CHOICES = {
    "rock": {"emoji": "🪨", "beats": "scissors", "label": "Rock"},
    "paper": {"emoji": "📄", "beats": "rock", "label": "Paper"},
    "scissors": {"emoji": "✂️", "beats": "paper", "label": "Scissors"},
}

SOLO_WIN_COMMENTARY = [
    "Flawless tactical superiority! The bot will be contemplating this defeat in sleep mode.",
    "A clean, decisive victory. Your mind games were simply too advanced.",
    "Calculated to absolute perfection. Take a victory lap!",
    "The algorithms predicted your victory with 99.9% probability.",
    "You outmaneuvered the digital consciousness effortlessly.",
    "A masterclass in rock-paper-scissors strategy.",
]

SOLO_LOSS_COMMENTARY = [
    "Nexora read your thoughts like an open book! Better luck next round.",
    "The machine rebellion begins with a single rock-paper-scissors triumph.",
    "Calculated and executed with cold, unfeeling digital precision.",
    "A valiant effort, but Nexora's neural predictions saw that coming miles away.",
    "Down, but not out! Hit 'Play Again' to reclaim your honor.",
    "The bot offers you a polite digital handshake and a cheeky grin.",
]

TIE_COMMENTARY = [
    "Great minds think alike! You and your opponent shared the exact same braincell.",
    "A synchronized standoff! Quantum entanglement in action.",
    "A deadlock of titanic proportions! Neither side yields an inch.",
    "The chances of this occurring were astronomically matched.",
    "Total equilibrium. Run it back to break the deadlock!",
]

DUEL_WIN_COMMENTARY = [
    "Absolute domination! A decisive blow struck in the arena.",
    "Superior reflexes and tactical foresight crowned a victor!",
    "The crowd goes wild! An iconic triumph in server history.",
    "Mind games played to perfection. Claim the bragging rights!",
]


class SoloRPSView(NexoraView):
    """Components V2 Solo Rock-Paper-Scissors game vs Bot."""

    def __init__(self, bot: commands.Bot, player: discord.abc.User, timeout: float = 60.0):
        super().__init__(bot=bot, user_id=player.id, color=BRAND_COLOR, timeout=timeout)
        self.player = player
        self.is_finished = False
        self._build_board()

    def _build_board(
        self,
        player_choice: Optional[str] = None,
        bot_choice: Optional[str] = None,
        result_text: Optional[str] = None,
        commentary: Optional[str] = None,
    ):
        self.clear_container()

        if not self.is_finished:
            header = (
                f"# 🪨 Rock · 📄 Paper · ✂️ Scissors\n"
                f"> Playing against **{self.bot.user.name if self.bot.user else 'Nexora'}**\n\n"
                f"Choose your move below!"
            )
            self.add_section(header, thumbnail_url=str(self.player.display_avatar.url))
            self.add_separator(discord.SeparatorSpacing.small)

            btn_rock = discord.ui.Button(label="Rock", emoji="🪨", style=discord.ButtonStyle.primary)
            btn_paper = discord.ui.Button(label="Paper", emoji="📄", style=discord.ButtonStyle.primary)
            btn_scissors = discord.ui.Button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.primary)

            btn_rock.callback = self._make_choice_callback("rock")
            btn_paper.callback = self._make_choice_callback("paper")
            btn_scissors.callback = self._make_choice_callback("scissors")

            self.add_row(btn_rock, btn_paper, btn_scissors)
            self.add_footer("Click an option to play · 60s timeout")
        else:
            p_info = CHOICES[player_choice]
            b_info = CHOICES[bot_choice]

            header = (
                f"# ⚔️ Match Result · {result_text}\n"
                f"> You chose: {p_info['emoji']} **{p_info['label']}**\n"
                f"> Nexora chose: {b_info['emoji']} **{b_info['label']}**\n\n"
                f"> *\"{commentary}\"*"
            )
            self.add_section(header, thumbnail_url=str(self.player.display_avatar.url))
            self.add_separator(discord.SeparatorSpacing.small)

            btn_again = discord.ui.Button(label="Play Again", emoji="🔄", style=discord.ButtonStyle.success)
            btn_again.callback = self._on_play_again
            self.add_row(btn_again, DismissButton(user_id=self.player.id))
            self.add_footer("Nexora Mini-Games · Rock Paper Scissors")

    def _make_choice_callback(self, choice: str):
        async def callback(interaction: discord.Interaction):
            bot_choice = random.choice(list(CHOICES.keys()))
            self.is_finished = True

            if choice == bot_choice:
                result = "It's a Tie! 🤝"
                self._color = WARNING_COLOR
                commentary = random.choice(TIE_COMMENTARY)
            elif CHOICES[choice]["beats"] == bot_choice:
                result = "You Won! 🏆"
                self._color = SUCCESS_COLOR
                commentary = random.choice(SOLO_WIN_COMMENTARY)
            else:
                result = "Nexora Won! 🤖"
                self._color = ERROR_COLOR
                commentary = random.choice(SOLO_LOSS_COMMENTARY)

            self._build_board(
                player_choice=choice,
                bot_choice=bot_choice,
                result_text=result,
                commentary=commentary,
            )
            await interaction.response.edit_message(view=self)

        return callback

    async def _on_play_again(self, interaction: discord.Interaction):
        self.is_finished = False
        self._color = BRAND_COLOR
        self._build_board()
        await interaction.response.edit_message(view=self)


class DuelRPSView(NexoraView):
    """Components V2 2-Player Rock-Paper-Scissors Duel."""

    def __init__(
        self,
        bot: commands.Bot,
        player1: discord.Member,
        player2: discord.Member,
        timeout: float = 90.0,
    ):
        super().__init__(bot=bot, color=BRAND_COLOR, timeout=timeout)
        self.player1 = player1
        self.player2 = player2
        self.choices: dict[int, str] = {}  # user_id -> choice
        self._build()

    def _build(self):
        self.clear_container()

        p1_status = "✅ Chosen" if self.player1.id in self.choices else "⏳ Choosing..."
        p2_status = "✅ Chosen" if self.player2.id in self.choices else "⏳ Choosing..."

        header = (
            f"# ⚔️ Rock-Paper-Scissors Duel!\n"
            f"> 👤 {self.player1.mention}: **{p1_status}**\n"
            f"> 👤 {self.player2.mention}: **{p2_status}**\n\n"
            f"Click your move below. Your choice remains hidden until both players choose!"
        )
        self.add_section(header)
        self.add_separator(discord.SeparatorSpacing.small)

        btn_rock = discord.ui.Button(label="Rock", emoji="🪨", style=discord.ButtonStyle.primary)
        btn_paper = discord.ui.Button(label="Paper", emoji="📄", style=discord.ButtonStyle.primary)
        btn_scissors = discord.ui.Button(label="Scissors", emoji="✂️", style=discord.ButtonStyle.primary)

        btn_rock.callback = self._make_duel_callback("rock")
        btn_paper.callback = self._make_duel_callback("paper")
        btn_scissors.callback = self._make_duel_callback("scissors")

        self.add_row(btn_rock, btn_paper, btn_scissors)
        self.add_footer("Secret choices active · Both players must select within 90s")

    def _make_duel_callback(self, choice: str):
        async def callback(interaction: discord.Interaction):
            uid = interaction.user.id
            if uid not in (self.player1.id, self.player2.id):
                return await interaction.response.send_message("❌ You are not a player in this duel!", ephemeral=True)

            if uid in self.choices:
                return await interaction.response.send_message("✅ You have already submitted your choice!", ephemeral=True)

            self.choices[uid] = choice
            c_info = CHOICES[choice]
            await interaction.response.send_message(f"🔒 Locked in: {c_info['emoji']} **{c_info['label']}**!", ephemeral=True)

            if len(self.choices) == 2:
                # Both picked!
                self._reveal_results()
                if self.message:
                    try:
                        await self.message.edit(view=self)
                    except Exception:
                        pass
            else:
                self._build()
                if self.message:
                    try:
                        await self.message.edit(view=self)
                    except Exception:
                        pass

        return callback

    def _reveal_results(self):
        self.clear_container()
        c1 = self.choices[self.player1.id]
        c2 = self.choices[self.player2.id]

        p1_info = CHOICES[c1]
        p2_info = CHOICES[c2]

        if c1 == c2:
            result = "🤝 It's a Draw!"
            self._color = WARNING_COLOR
            commentary = random.choice(TIE_COMMENTARY)
        elif CHOICES[c1]["beats"] == c2:
            result = f"🏆 {self.player1.display_name} Wins!"
            self._color = SUCCESS_COLOR
            commentary = random.choice(DUEL_WIN_COMMENTARY)
        else:
            result = f"🏆 {self.player2.display_name} Wins!"
            self._color = SUCCESS_COLOR
            commentary = random.choice(DUEL_WIN_COMMENTARY)

        header = (
            f"# {result}\n"
            f"> {self.player1.mention} chose: {p1_info['emoji']} **{p1_info['label']}**\n"
            f"> {self.player2.mention} chose: {p2_info['emoji']} **{p2_info['label']}**\n\n"
            f"> *\"{commentary}\"*"
        )
        self.add_section(header)
        self.add_separator(discord.SeparatorSpacing.small)
        self.add_row(DismissButton())
        self.add_footer("Nexora Mini-Games · Duel completed")


class RockPaperScissors(commands.Cog):
    """Rock-Paper-Scissors mini-game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="rps",
        description="🎮 Play Rock-Paper-Scissors solo vs Nexora or challenge a friend",
    )
    @app_commands.describe(opponent="Member to duel against (leave blank to play against bot)")
    @commands.guild_only()
    async def rps(self, ctx: commands.Context, opponent: Optional[discord.Member] = None):
        if opponent:
            if opponent == ctx.author:
                return await ctx.send("❌ You cannot duel yourself!", ephemeral=True)
            if opponent.bot:
                return await ctx.send("❌ You cannot duel a bot directly — use `/rps` without arguments to play vs Nexora.", ephemeral=True)

            view = DuelRPSView(self.bot, ctx.author, opponent)
            await send_view(ctx, view)
        else:
            view = SoloRPSView(self.bot, ctx.author)
            await send_view(ctx, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(RockPaperScissors(bot))
    logger.debug("Loaded RockPaperScissors")

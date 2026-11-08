"""
cogs/games/rps.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Rock-Paper-Scissors Engine.

Supports:
  • Solo Mode vs Nexora AI with streak tracking & commentary
  • 2-Player Multiplayer Duel with hidden choices, rematch button,
    turn-based notifications, and permanent lifetime scoreboards.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
import random
from typing import Optional, Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.game_stats import record_game
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
    """Components V2 Solo Rock-Paper-Scissors game vs Bot with streak tracker."""

    def __init__(
        self,
        bot: commands.Bot,
        player: discord.abc.User,
        streak: int = 0,
        best_streak: int = 0,
        round_num: int = 1,
        timeout: float = 120.0,
    ):
        super().__init__(bot=bot, user_id=player.id, color=BRAND_COLOR, timeout=timeout)
        self.player = player
        self.is_finished = False
        self.rematch_started = False
        self.streak = streak
        self.best_streak = best_streak
        self.round_num = round_num
        self._build_board()

    def _build_board(
        self,
        player_choice: Optional[str] = None,
        bot_choice: Optional[str] = None,
        result_text: Optional[str] = None,
        commentary: Optional[str] = None,
    ):
        self.clear_container()

        streak_badge = (
            f"Round #{self.round_num} · 🔥 Current Streak: **{self.streak}** (Best: {self.best_streak})"
            if self.streak > 0
            else f"Round #{self.round_num} · Best Streak: **{self.best_streak}**"
        )

        if not self.is_finished:
            header = (
                f"# 🪨 Rock · 📄 Paper · ✂️ Scissors\n"
                f"> Playing against **{self.bot.user.name if self.bot.user else 'Nexora'}**\n\n"
                f"Choose your move below!\n"
                f"-# {streak_badge}"
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
            self.add_footer("Click an option to play · 120s timeout")
        else:
            p_info = CHOICES[player_choice]
            b_info = CHOICES[bot_choice]

            header = (
                f"# ⚔️ Match Result · {result_text}\n"
                f"> You chose: {p_info['emoji']} **{p_info['label']}**\n"
                f"> Nexora chose: {b_info['emoji']} **{b_info['label']}**\n\n"
                f"> *\"{commentary}\"*\n"
                f"-# {streak_badge}"
            )
            self.add_section(header, thumbnail_url=str(self.player.display_avatar.url))
            self.add_separator(discord.SeparatorSpacing.small)

            if self.rematch_started:
                btn_done = discord.ui.Button(
                    label="Rematch Started Below",
                    emoji="✅",
                    style=discord.ButtonStyle.secondary,
                    disabled=True,
                )
                self.add_row(btn_done, DismissButton(user_id=self.player.id))
            else:
                btn_again = discord.ui.Button(label="Play Again", emoji="🔄", style=discord.ButtonStyle.success)
                btn_again.callback = self._on_play_again
                self.add_row(btn_again, DismissButton(user_id=self.player.id))
            self.add_footer("Nexora Mini-Games · Rock Paper Scissors")

    def _make_choice_callback(self, choice: str):
        async def callback(interaction: discord.Interaction):
            if not self.message and interaction.message:
                self.message = interaction.message

            bot_choice = random.choice(list(CHOICES.keys()))
            self.is_finished = True
            self._last_choice = (choice, bot_choice)

            if choice == bot_choice:
                result = "It's a Tie! 🤝"
                self._color = WARNING_COLOR
                commentary = random.choice(TIE_COMMENTARY)
                await record_game(self.bot, self.player.id, "rps", "draw")
            elif CHOICES[choice]["beats"] == bot_choice:
                result = "You Won! 🏆"
                self._color = SUCCESS_COLOR
                self.streak += 1
                if self.streak > self.best_streak:
                    self.best_streak = self.streak
                commentary = random.choice(SOLO_WIN_COMMENTARY)
                await record_game(self.bot, self.player.id, "rps", "win")
            else:
                result = "Nexora Won! 🤖"
                self._color = ERROR_COLOR
                self.streak = 0
                commentary = random.choice(SOLO_LOSS_COMMENTARY)
                await record_game(self.bot, self.player.id, "rps", "loss")

            self._last_result_meta = (result, commentary)
            self._build_board(
                player_choice=choice,
                bot_choice=bot_choice,
                result_text=result,
                commentary=commentary,
            )
            await interaction.response.edit_message(view=self)

        return callback

    async def _on_play_again(self, interaction: discord.Interaction):
        if not self.message and interaction.message:
            self.message = interaction.message
        self.rematch_started = True
        choice, bot_choice = getattr(self, "_last_choice", ("rock", "rock"))
        result, commentary = getattr(self, "_last_result_meta", ("Finished", ""))
        self._build_board(
            player_choice=choice,
            bot_choice=bot_choice,
            result_text=result,
            commentary=commentary,
        )
        self.stop()
        await interaction.response.edit_message(view=self)

        new_view = SoloRPSView(
            bot=self.bot,
            player=self.player,
            streak=self.streak,
            best_streak=self.best_streak,
            round_num=self.round_num + 1,
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


class DuelRPSView(NexoraView):
    """Components V2 2-Player Rock-Paper-Scissors Duel with New-Message Rematch and Reply Turn Alerts."""

    def __init__(
        self,
        bot: commands.Bot,
        player1: discord.Member,
        player2: discord.Member,
        session_scores: Optional[dict] = None,
        round_num: int = 1,
        timeout: float = 120.0,
    ):
        super().__init__(bot=bot, color=BRAND_COLOR, timeout=timeout)
        self.player1 = player1
        self.player2 = player2
        self.choices: dict[int, str] = {}
        self.scores = session_scores or {player1.id: 0, player2.id: 0, "draws": 0}
        self.round_num = round_num
        self.is_finished = False
        self.rematch_started = False
        self.turn_ping_msg: Optional[discord.Message] = None
        self._build()

    async def _clear_turn_ping(self):
        if self.turn_ping_msg is not None:
            try:
                await self.turn_ping_msg.delete()
            except Exception:
                pass
            self.turn_ping_msg = None

    async def send_turn_ping(self, channel: Optional[discord.abc.Messageable], text: str, ping_users: list):
        """Send a turn/chance ping that replies directly to the active match message and cleans up the old ping."""
        await self._clear_turn_ping()
        if channel is None:
            return
        try:
            ref = self.message.to_reference(fail_if_not_exists=False) if self.message else None
            self.turn_ping_msg = await channel.send(
                content=text,
                reference=ref,
                allowed_mentions=discord.AllowedMentions(users=ping_users, roles=False, everyone=False, replied_user=False),
                delete_after=25,
            )
        except Exception:
            pass

    def _build(self):
        self.clear_container()

        p1_status = "✅ Locked In" if self.player1.id in self.choices else "⏳ Choosing..."
        p2_status = "✅ Locked In" if self.player2.id in self.choices else "⏳ Choosing..."
        score_line = (
            f"Round #{self.round_num}  ·  Score: `{self.player1.display_name}` **{self.scores[self.player1.id]}**  |  "
            f"`{self.player2.display_name}` **{self.scores[self.player2.id]}**  |  "
            f"Draws **{self.scores['draws']}**"
        )

        header = (
            f"# ⚔️ Rock-Paper-Scissors Duel!\n"
            f"> 👤 {self.player1.mention}: **{p1_status}**\n"
            f"> 👤 {self.player2.mention}: **{p2_status}**\n\n"
            f"Click your move below. Choices remain hidden until both players choose!\n"
            f"-# {score_line}"
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
        self.add_footer("Secret choices active · Both players must select within 120s")

    def _make_duel_callback(self, choice: str):
        async def callback(interaction: discord.Interaction):
            if not self.message and interaction.message:
                self.message = interaction.message

            uid = interaction.user.id
            if uid not in (self.player1.id, self.player2.id):
                return await interaction.response.send_message("❌ You are not a player in this duel!", ephemeral=True)

            if uid in self.choices:
                return await interaction.response.send_message("✅ You have already submitted your choice!", ephemeral=True)

            self.choices[uid] = choice
            c_info = CHOICES[choice]
            await interaction.response.send_message(f"🔒 Locked in: {c_info['emoji']} **{c_info['label']}**!", ephemeral=True)

            # Turn-based ping for opponent if only 1 has chosen
            if len(self.choices) == 1:
                other_player = self.player2 if uid == self.player1.id else self.player1
                chooser = self.player1 if uid == self.player1.id else self.player2
                self._build()
                if self.message:
                    try:
                        await self.message.edit(view=self)
                    except Exception:
                        pass
                await self.send_turn_ping(
                    interaction.channel,
                    f"🎯 **Your Chance!** {other_player.mention} — **{chooser.display_name}** locked in their move! Pick **🪨 Rock, 📄 Paper, or ✂️ Scissors** on the replied match board!",
                    [other_player],
                )
            elif len(self.choices) == 2:
                await self._clear_turn_ping()
                await self._reveal_results()
                if self.message:
                    try:
                        await self.message.edit(view=self)
                    except Exception:
                        pass

        return callback

    async def _reveal_results(self):
        self.is_finished = True
        c1 = self.choices[self.player1.id]
        c2 = self.choices[self.player2.id]

        if c1 == c2:
            result = "🤝 It's a Draw!"
            self._color = WARNING_COLOR
            self.scores["draws"] += 1
            commentary = random.choice(TIE_COMMENTARY)
            await record_game(self.bot, self.player1.id, "rps", "draw")
            await record_game(self.bot, self.player2.id, "rps", "draw")
        elif CHOICES[c1]["beats"] == c2:
            result = f"🏆 {self.player1.display_name} Wins!"
            self._color = SUCCESS_COLOR
            self.scores[self.player1.id] += 1
            commentary = random.choice(DUEL_WIN_COMMENTARY)
            await record_game(self.bot, self.player1.id, "rps", "win")
            await record_game(self.bot, self.player2.id, "rps", "loss")
        else:
            result = f"🏆 {self.player2.display_name} Wins!"
            self._color = SUCCESS_COLOR
            self.scores[self.player2.id] += 1
            commentary = random.choice(DUEL_WIN_COMMENTARY)
            await record_game(self.bot, self.player2.id, "rps", "win")
            await record_game(self.bot, self.player1.id, "rps", "loss")

        self._last_reveal = (result, commentary)
        self._render_finished(result, commentary)

    def _render_finished(self, result: str, commentary: str):
        self.clear_container()
        c1 = self.choices[self.player1.id]
        c2 = self.choices[self.player2.id]
        p1_info = CHOICES[c1]
        p2_info = CHOICES[c2]

        score_line = (
            f"Round #{self.round_num}  ·  Score: `{self.player1.display_name}` **{self.scores[self.player1.id]}**  |  "
            f"`{self.player2.display_name}` **{self.scores[self.player2.id]}**  |  "
            f"Draws **{self.scores['draws']}**"
        )

        header = (
            f"# {result}\n"
            f"> {self.player1.mention} chose: {p1_info['emoji']} **{p1_info['label']}**\n"
            f"> {self.player2.mention} chose: {p2_info['emoji']} **{p2_info['label']}**\n\n"
            f"> *\"{commentary}\"*\n"
            f"-# {score_line}"
        )
        self.add_section(header)
        self.add_separator(discord.SeparatorSpacing.small)

        if self.rematch_started:
            btn_done = discord.ui.Button(
                label="Rematch Started Below",
                emoji="✅",
                style=discord.ButtonStyle.secondary,
                disabled=True,
            )
            self.add_row(btn_done, DismissButton())
        else:
            btn_rematch = discord.ui.Button(label="Rematch", emoji="🔄", style=discord.ButtonStyle.success)
            btn_rematch.callback = self._on_rematch
            self.add_row(btn_rematch, DismissButton())
        self.add_footer("Nexora Mini-Games · Click 'Rematch' to spawn a new round!")

    async def _on_rematch(self, interaction: discord.Interaction):
        if not self.message and interaction.message:
            self.message = interaction.message
        if interaction.user.id not in (self.player1.id, self.player2.id):
            return await interaction.response.send_message("❌ Only duel participants can trigger a rematch.", ephemeral=True)

        await self._clear_turn_ping()
        self.rematch_started = True
        result, commentary = getattr(self, "_last_reveal", ("Match Complete", ""))
        self._render_finished(result, commentary)
        self.stop()
        await interaction.response.edit_message(view=self)

        new_view = DuelRPSView(
            bot=self.bot,
            player1=self.player1,
            player2=self.player2,
            session_scores=dict(self.scores),
            round_num=self.round_num + 1,
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
        if interaction.channel:
            other = self.player2 if interaction.user.id == self.player1.id else self.player1
            await new_view.send_turn_ping(
                interaction.channel,
                f"🔄 **Rematch Round #{new_view.round_num}!** {other.mention} & {interaction.user.mention} — lock in your moves on the replied match board!",
                [other, interaction.user],
            )

    async def on_timeout(self):
        await self._clear_turn_ping()
        await super().on_timeout()


class RockPaperScissors(commands.Cog):
    """Rock-Paper-Scissors mini-game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="rps",
        description="🎮 Play Rock-Paper-Scissors solo vs Nexora or challenge a friend",
    )
    @app_commands.describe(opponent="User to duel against (leave blank to play against bot)")
    async def rps(self, ctx: commands.Context, opponent: Optional[Union[discord.Member, discord.User]] = None):
        if opponent and opponent != ctx.author and not opponent.bot:
            view = DuelRPSView(self.bot, ctx.author, opponent)
            msg = await send_view(ctx, view)
            if msg and hasattr(view, "message"):
                view.message = msg
            await view.send_turn_ping(
                ctx.channel,
                f"⚔️ **RPS Duel Challenge!** {opponent.mention} — {ctx.author.mention} challenged you! Lock in your secret move on the replied match board!",
                [opponent],
            )
        else:
            view = SoloRPSView(self.bot, ctx.author)
            await send_view(ctx, view)


async def setup(bot: commands.Bot):
    await bot.add_cog(RockPaperScissors(bot))
    logger.debug("Loaded RockPaperScissors")

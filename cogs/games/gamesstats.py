"""
cogs/games/gamesstats.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Game Statistics Hub for Nexora.

Permanent game statistics tracking wins, losses, win rates,
and activity across mini-games (Tic-Tac-Toe, Rock-Paper-Scissors, Guess, Connect 4).
Supports dual MongoDB and local persistence, plus Admin Reset and Customization.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import logging
from datetime import datetime, timezone
from typing import Optional, Literal, Union

import discord
from discord import app_commands
from discord.ext import commands

from utils.game_stats import (
    get_user_stats,
    get_leaderboard,
    reset_user_stats,
    reset_server_stats,
    set_user_stats,
)
from utils.ui import (
    BRAND_COLOR,
    PREMIUM_COLOR,
    SUCCESS_COLOR,
    ERROR_COLOR,
    WARNING_COLOR,
    CYAN_COLOR,
    progress_bar,
    NexoraView,
    DismissButton,
    send_view,
)

logger = logging.getLogger(__name__)

GAME_LABELS = {
    "all": "🌟 All Mini-Games (Overall)",
    "tictactoe": "⚔️ Tic-Tac-Toe",
    "connect4": "🔴🟡 Connect Four",
    "rps": "🪨 Rock-Paper-Scissors",
    "guess": "🔢 Number Guesser",
}


def _rank_badge(wins: int) -> str:
    if wins >= 25:
        return "🌟 Grandmaster"
    if wins >= 10:
        return "🥇 Veteran"
    if wins >= 3:
        return "🥈 Contender"
    return "🥉 Rookie"


def build_player_stats_embed(target: Union[discord.Member, discord.User], doc: dict) -> discord.Embed:
    embed = discord.Embed(
        title=f"🎮 Mini-Game Record · {target.display_name}",
        color=BRAND_COLOR,
        timestamp=datetime.now(timezone.utc),
    )
    embed.set_thumbnail(url=target.display_avatar.url)

    # 1. Tic-Tac-Toe
    ttt = doc.get("tictactoe", {})
    ttt_played = ttt.get("played", 0)
    ttt_wins = ttt.get("wins", 0)
    ttt_losses = ttt.get("losses", 0)
    ttt_draws = ttt.get("draws", 0)
    ttt_wr = (ttt_wins / ttt_played * 100.0) if ttt_played > 0 else 0.0

    ttt_meter = progress_bar(ttt_wins, max(1, ttt_played), length=10)
    embed.add_field(
        name="⚔️ Tic-Tac-Toe",
        value=(
            f"`[{ttt_meter}]` **{ttt_wr:.1f}% Win Rate**\n"
            f"• Played: **{ttt_played}** · Won: **{ttt_wins}** · Lost: **{ttt_losses}** · Draws: **{ttt_draws}**"
        ),
        inline=False,
    )

    # 2. Rock-Paper-Scissors
    rps = doc.get("rps", {})
    rps_played = rps.get("played", 0)
    rps_wins = rps.get("wins", 0)
    rps_losses = rps.get("losses", 0)
    rps_draws = rps.get("draws", 0)
    rps_wr = (rps_wins / rps_played * 100.0) if rps_played > 0 else 0.0

    rps_meter = progress_bar(rps_wins, max(1, rps_played), length=10)
    embed.add_field(
        name="🪨 Rock-Paper-Scissors",
        value=(
            f"`[{rps_meter}]` **{rps_wr:.1f}% Win Rate**\n"
            f"• Played: **{rps_played}** · Won: **{rps_wins}** · Lost: **{rps_losses}** · Draws: **{rps_draws}**"
        ),
        inline=False,
    )

    # 3. Number Guessing
    guess = doc.get("guess", {})
    g_played = guess.get("played", 0)
    g_wins = guess.get("wins", 0)
    g_losses = guess.get("losses", 0)
    g_wr = (g_wins / g_played * 100.0) if g_played > 0 else 0.0

    g_meter = progress_bar(g_wins, max(1, g_played), length=10)
    embed.add_field(
        name="🔢 Number Guesser",
        value=(
            f"`[{g_meter}]` **{g_wr:.1f}% Win Rate**\n"
            f"• Played: **{g_played}** · Solved: **{g_wins}** · Failed: **{g_losses}**"
        ),
        inline=False,
    )

    # 4. Connect Four
    c4 = doc.get("connect4", {})
    c4_played = c4.get("played", 0)
    c4_wins = c4.get("wins", 0)
    c4_losses = c4.get("losses", 0)
    c4_draws = c4.get("draws", 0)
    c4_wr = (c4_wins / c4_played * 100.0) if c4_played > 0 else 0.0

    c4_meter = progress_bar(c4_wins, max(1, c4_played), length=10)
    embed.add_field(
        name="🔴🟡 Connect Four",
        value=(
            f"`[{c4_meter}]` **{c4_wr:.1f}% Win Rate**\n"
            f"• Played: **{c4_played}** · Won: **{c4_wins}** · Lost: **{c4_losses}** · Draws: **{c4_draws}**"
        ),
        inline=False,
    )

    total_played = ttt_played + rps_played + g_played + c4_played
    total_wins = ttt_wins + rps_wins + g_wins + c4_wins
    overall_wr = (total_wins / total_played * 100.0) if total_played > 0 else 0.0

    rank_title = _rank_badge(total_wins)
    embed.add_field(
        name="🏆 Overall Performance",
        value=f"Rank: **{rank_title}** · Total Matches: **{total_played}** · Overall Win Rate: **{overall_wr:.1f}%**",
        inline=False,
    )

    embed.set_footer(text="Nexora Mini-Games · Click 🏆 Leaderboard below to see top players!")
    return embed


class GameStatsHubView(discord.ui.View):
    """Interactive switcher between Player Stats Card and Server/Global Top 10 Leaderboard."""

    def __init__(
        self,
        bot: commands.Bot,
        requester: Union[discord.Member, discord.User],
        target: Union[discord.Member, discord.User],
        guild: Optional[discord.Guild],
        initial_doc: dict,
        mode: str = "profile",  # 'profile' or 'leaderboard'
    ):
        super().__init__(timeout=180)
        self.bot = bot
        self.requester = requester
        self.target = target
        self.guild = guild
        self.doc = initial_doc
        self.mode = mode
        self.scope = "server" if guild is not None else "global"
        self.game_filter = "all"
        self._sync_components()

    def _sync_components(self):
        self.clear_items()

        btn_profile = discord.ui.Button(
            label=f"{self.target.display_name[:18]}'s Stats",
            emoji="👤",
            style=discord.ButtonStyle.primary if self.mode == "profile" else discord.ButtonStyle.secondary,
            row=0,
        )
        btn_profile.callback = self._on_profile
        self.add_item(btn_profile)

        btn_lb = discord.ui.Button(
            label="Top 10 Leaderboard",
            emoji="🏆",
            style=discord.ButtonStyle.primary if self.mode == "leaderboard" else discord.ButtonStyle.secondary,
            row=0,
        )
        btn_lb.callback = self._on_leaderboard
        self.add_item(btn_lb)

        if self.mode == "leaderboard" and self.guild is not None:
            btn_scope = discord.ui.Button(
                label="Server Ranking" if self.scope == "server" else "Global Ranking",
                emoji="🏰" if self.scope == "server" else "🌍",
                style=discord.ButtonStyle.success,
                row=0,
            )
            btn_scope.callback = self._on_toggle_scope
            self.add_item(btn_scope)

        if self.mode == "leaderboard":
            select = discord.ui.Select(
                placeholder="🎮 Filter leaderboard by game...",
                row=1,
                options=[
                    discord.SelectOption(
                        label="Overall (All Mini-Games)",
                        value="all",
                        emoji="🌟",
                        default=(self.game_filter == "all"),
                    ),
                    discord.SelectOption(
                        label="Tic-Tac-Toe",
                        value="tictactoe",
                        emoji="⚔️",
                        default=(self.game_filter == "tictactoe"),
                    ),
                    discord.SelectOption(
                        label="Connect Four",
                        value="connect4",
                        emoji="🔴",
                        default=(self.game_filter == "connect4"),
                    ),
                    discord.SelectOption(
                        label="Rock-Paper-Scissors",
                        value="rps",
                        emoji="🪨",
                        default=(self.game_filter == "rps"),
                    ),
                    discord.SelectOption(
                        label="Number Guesser",
                        value="guess",
                        emoji="🔢",
                        default=(self.game_filter == "guess"),
                    ),
                ],
            )
            select.callback = self._on_select_game
            self.add_item(select)

    async def build_current_embed(self) -> discord.Embed:
        if self.mode == "profile":
            self.doc = await get_user_stats(self.bot, self.target.id)
            return build_player_stats_embed(self.target, self.doc)

        member_ids = None
        scope_title = "🌍 Global Leaderboard"
        if self.scope == "server" and self.guild is not None:
            member_ids = {m.id for m in self.guild.members}
            scope_title = f"🏰 {self.guild.name} Leaderboard"

        entries = await get_leaderboard(
            self.bot,
            game=self.game_filter,
            member_ids=member_ids,
            limit=10,
        )
        game_title = GAME_LABELS.get(self.game_filter, "🌟 All Mini-Games")
        embed = discord.Embed(
            title=f"🏆 {scope_title} · {game_title}",
            color=PREMIUM_COLOR,
            timestamp=datetime.now(timezone.utc),
        )

        if not entries:
            embed.description = (
                "> *No matches recorded for this filter yet!*\n"
                "> Start a game with `/rps`, `/tictactoe`, `/connect4`, or `/guess` to claim **#1**!"
            )
        else:
            medals = ["🥇", "🥈", "🥉"]
            lines = []
            for idx, item in enumerate(entries, start=1):
                uid = item["user_id"]
                badge = medals[idx - 1] if idx <= 3 else f"`#{idx:02d}`"
                user_obj = (self.guild.get_member(uid) if self.guild else None) or self.bot.get_user(uid)
                name_str = f"**{user_obj.display_name}**" if user_obj else f"<@{uid}>"
                lines.append(
                    f"{badge} {name_str} — **{item['wins']} Wins** "
                    f"(`{item['win_rate']:.1f}%` WR · `{item['played']}` played)"
                )
            embed.description = "\n".join(lines)

        embed.set_footer(text="Nexora Competitive Rankings · Sorted by Wins & Win Rate")
        return embed

    async def _on_profile(self, interaction: discord.Interaction):
        self.mode = "profile"
        self._sync_components()
        embed = await self.build_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_leaderboard(self, interaction: discord.Interaction):
        self.mode = "leaderboard"
        self._sync_components()
        embed = await self.build_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_toggle_scope(self, interaction: discord.Interaction):
        self.scope = "global" if self.scope == "server" else "server"
        self._sync_components()
        embed = await self.build_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)

    async def _on_select_game(self, interaction: discord.Interaction):
        values = interaction.data.get("values") or ["all"]
        self.game_filter = values[0]
        self._sync_components()
        embed = await self.build_current_embed()
        await interaction.response.edit_message(embed=embed, view=self)


class GameStats(commands.Cog):
    """Mini-game statistics tracking and administration."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="gamestats",
        aliases=["game_stats", "leaderboard_games", "leaderboard", "lb"],
        description="📊 View mini-game statistics, win rates, and the Top 10 Leaderboard",
    )
    @app_commands.describe(member="User to inspect stats for (leave blank for yourself)")
    async def gamestats(self, ctx: commands.Context, member: Optional[Union[discord.Member, discord.User]] = None):
        target = member or ctx.author
        doc = await get_user_stats(self.bot, target.id)
        invoked = (ctx.invoked_with or "").lower()
        initial_mode = "leaderboard" if invoked in ("leaderboard", "lb", "leaderboard_games") else "profile"
        view = GameStatsHubView(
            bot=self.bot,
            requester=ctx.author,
            target=target,
            guild=ctx.guild,
            initial_doc=doc,
            mode=initial_mode,
        )
        embed = await view.build_current_embed()
        await ctx.send(embed=embed, view=view)

    @commands.hybrid_command(
        name="resetgamestats",
        aliases=["cleargamestats", "resetgamestat"],
        description="🛡️ Reset game stats for a user or the entire server (Admin only)",
    )
    @app_commands.describe(
        scope="Choose whether to reset for a specific user or everyone in the server",
        member="Target user if scope is user",
        game="Specific game to reset (leave empty for all games)",
    )
    @app_commands.choices(
        scope=[
            app_commands.Choice(name="👤 Specific User", value="user"),
            app_commands.Choice(name="🏰 Entire Server", value="server"),
        ],
        game=[
            app_commands.Choice(name="🎮 All Games", value="all"),
            app_commands.Choice(name="🪨 Rock-Paper-Scissors", value="rps"),
            app_commands.Choice(name="⚔️ Tic-Tac-Toe", value="tictactoe"),
            app_commands.Choice(name="🔴🟡 Connect Four", value="connect4"),
            app_commands.Choice(name="🔢 Number Guesser", value="guess"),
        ],
    )
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def resetgamestats(
        self,
        ctx: commands.Context,
        scope: str = "user",
        member: Optional[discord.Member] = None,
        game: Optional[str] = "all",
    ):
        selected_game = None if (not game or game == "all") else game.lower()
        game_label = f"**{selected_game.upper()}**" if selected_game else "**all mini-games**"

        if scope == "server":
            member_ids = [m.id for m in ctx.guild.members]
            await reset_server_stats(self.bot, member_ids, game=selected_game)
            view = NexoraView(color=WARNING_COLOR, timeout=60)
            view.add_text(
                f"# 🛡️ Server Game Stats Reset\n"
                f"> Admin {ctx.author.mention} reset {game_label} stats for **all members in {ctx.guild.name}**."
            )
            view.add_footer("Nexora Mini-Game Administration")
            await send_view(ctx, view)
            logger.info("GameStats: %s reset server stats in %s (%s)", ctx.author, ctx.guild.name, game_label)
        else:
            target = member or ctx.author
            await reset_user_stats(self.bot, target.id, game=selected_game)
            view = NexoraView(color=SUCCESS_COLOR, timeout=60)
            view.add_text(
                f"# 🛡️ User Game Stats Reset\n"
                f"> Reset {game_label} stats for {target.mention}."
            )
            view.add_footer("Nexora Mini-Game Administration")
            await send_view(ctx, view)
            logger.info("GameStats: %s reset stats for %s (%s)", ctx.author, target, game_label)

    @commands.hybrid_command(
        name="setgamestats",
        aliases=["customizestats"],
        description="⚙️ Customize/modify mini-game stats for a user (Admin/Owner)",
    )
    @app_commands.describe(
        member="Target user to modify stats for",
        game="Mini-game to adjust",
        wins="Number of wins to set",
        losses="Number of losses to set (default: 0)",
        draws="Number of draws to set (default: 0)",
    )
    @app_commands.choices(
        game=[
            app_commands.Choice(name="🪨 Rock-Paper-Scissors", value="rps"),
            app_commands.Choice(name="⚔️ Tic-Tac-Toe", value="tictactoe"),
            app_commands.Choice(name="🔴🟡 Connect Four", value="connect4"),
            app_commands.Choice(name="🔢 Number Guesser", value="guess"),
        ]
    )
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def setgamestats(
        self,
        ctx: commands.Context,
        member: discord.Member,
        game: str,
        wins: int,
        losses: int = 0,
        draws: int = 0,
    ):
        if wins < 0 or losses < 0 or draws < 0:
            return await ctx.send("❌ Values cannot be negative numbers.", ephemeral=True)

        g = game.lower()
        if g not in ("rps", "tictactoe", "connect4", "guess"):
            return await ctx.send("❌ Game must be `rps`, `tictactoe`, `connect4`, or `guess`.", ephemeral=True)

        await set_user_stats(self.bot, member.id, g, wins, losses, draws)

        view = NexoraView(color=SUCCESS_COLOR, timeout=60)
        view.add_text(
            f"# ⚙️ Game Stats Updated\n"
            f"> Customized **{g.upper()}** record for {member.mention}:\n\n"
            f"• **Wins:** `{wins}`\n"
            f"• **Losses:** `{losses}`\n"
            f"• **Draws:** `{draws}`\n"
            f"• **Total Matches:** `{wins + losses + draws}`"
        )
        view.add_footer(f"Configured by Administrator {ctx.author.display_name}")
        await send_view(ctx, view)
        logger.info("GameStats: %s adjusted %s stats for %s (W:%d, L:%d, D:%d)", ctx.author, g, member, wins, losses, draws)


async def setup(bot: commands.Bot):
    await bot.add_cog(GameStats(bot))
    logger.debug("Loaded GameStats Cog")

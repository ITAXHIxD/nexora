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


class GameStats(commands.Cog):
    """Mini-game statistics tracking and administration."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="gamestats",
        aliases=["game_stats", "leaderboard_games"],
        description="📊 View your lifetime mini-game statistics, win rates, and match records",
    )
    @app_commands.describe(member="User to inspect stats for (leave blank for yourself)")
    async def gamestats(self, ctx: commands.Context, member: Optional[Union[discord.Member, discord.User]] = None):
        target = member or ctx.author
        doc = await get_user_stats(self.bot, target.id)

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

        rank_title = (
            "🌟 Grandmaster" if total_wins >= 25
            else ("🥇 Veteran" if total_wins >= 10
            else ("🥈 Contender" if total_wins >= 3
            else "🥉 Rookie"))
        )
        embed.add_field(
            name="🏆 Overall Performance",
            value=f"Rank: **{rank_title}** · Total Matches: **{total_played}** · Overall Win Rate: **{overall_wr:.1f}%**",
            inline=False,
        )

        embed.set_footer(text="Nexora Mini-Games · Stats are tracked permanently across every match!")
        await ctx.send(embed=embed)

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

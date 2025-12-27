import discord
import sqlite3
import json
import logging
from discord.ext import commands
from discord import app_commands

logger = logging.getLogger(__name__)

class GameStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="game_stats", description="View your game stats")
    async def game_stats(self, interaction: discord.Interaction):
        """View your game statistics from the database"""
        
        # Enhanced database checking
        if not getattr(self.bot, 'db_manager', None):
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Database Not Available",
                    description="The database manager is not initialized.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
        
        if not self.bot.db_manager.enabled:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Database Required",
                    description="Game stats require database functionality to be enabled.\n\n"
                               "Database features are currently disabled in this bot instance.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        user_id = str(interaction.user.id)
        stats = {}
        
        try:
            # Proper context manager usage for SQLite connection
            with sqlite3.connect(self.bot.db_manager.db_path) as conn:
                # Set row factory for easier data access
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                # Check if game_sessions table exists
                cur.execute('''
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='game_sessions'
                ''')
                
                if not cur.fetchone():
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="❌ Game Table Not Found",
                            description="The game sessions table doesn't exist in the database.\n"
                                       "Play some games first to create stats!",
                            color=discord.Color.orange()
                        ),
                        ephemeral=True
                    )
                    return
                
                # Fetch game statistics
                cur.execute('''
                    SELECT 
                        game_type, 
                        COUNT(*) as games_played, 
                        MAX(score) as best_score, 
                        AVG(score) as avg_score,
                        MIN(score) as worst_score,
                        SUM(score) as total_score
                    FROM game_sessions
                    WHERE user_id = ?
                    GROUP BY game_type
                    ORDER BY games_played DESC
                ''', (user_id,))
                
                rows = cur.fetchall()
                
                for row in rows:
                    game_type = row['game_type']
                    stats[game_type] = {
                        "games": row['games_played'] or 0,
                        "best": row['best_score'] or 0,
                        "worst": row['worst_score'] or 0,
                        "avg": round(row['avg_score'] or 0, 2),
                        "total": row['total_score'] or 0
                    }
                    
        except sqlite3.DatabaseError as e:
            logger.error(f"Database error fetching game stats for user {user_id}: {e}")
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Database Error",
                    description="There was an error accessing your game statistics.\n"
                               "Please try again later.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
            
        except Exception as e:
            logger.error(f"Unexpected error fetching game stats for user {user_id}: {e}")
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Unexpected Error",
                    description="An unexpected error occurred while fetching your stats.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return

        # Handle no stats found
        if not stats:
            embed = discord.Embed(
                title="🎮 No Game History Found",
                description="You haven't played any games yet!\n\n"
                           "**Get started with:**\n"
                           "• `/play_trivia` - Test your knowledge\n"
                           "• `/play_guess` - Number guessing game\n"
                           "• `/play_quiz` - Quick quiz challenges",
                color=discord.Color.orange()
            )
            embed.set_footer(text="Play some games and check back later!")
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        # Build comprehensive stats embed
        embed = discord.Embed(
            title=f"🎮 Game Statistics for {interaction.user.display_name}",
            description=f"Your performance across **{len(stats)}** game types",
            color=discord.Color.green(),
            timestamp=discord.utils.utcnow()
        )
        
        # Add user avatar
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        
        # Calculate overall stats
        total_games = sum(stat['games'] for stat in stats.values())
        total_score = sum(stat['total'] for stat in stats.values())
        overall_avg = round(total_score / total_games, 2) if total_games > 0 else 0
        
        # Add overall summary
        embed.add_field(
            name="📊 Overall Summary",
            value=f"**Total Games:** {total_games}\n"
                  f"**Total Score:** {total_score:,}\n"
                  f"**Average Score:** {overall_avg}",
            inline=False
        )
        
        # Add individual game stats
        for game_type, data in stats.items():
            game_name = game_type.replace('_', ' ').title()
            
            # Calculate accuracy or performance indicator
            if data['best'] > 0:
                performance = round((data['avg'] / data['best']) * 100, 1)
            else:
                performance = 0
            
            value = f"**Games Played:** {data['games']}\n" \
                   f"**Best Score:** {data['best']}\n" \
                   f"**Average:** {data['avg']}\n" \
                   f"**Performance:** {performance}%"
            
            embed.add_field(
                name=f"🎯 {game_name}",
                value=value,
                inline=True
            )
        
        # Add helpful footer
        embed.set_footer(
            text=f"Keep playing to improve your stats! • Total games: {total_games}",
            icon_url=interaction.user.display_avatar.url
        )
        
        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="leaderboard", description="View game leaderboards")
    @app_commands.describe(
        game_type="Specific game type to show leaderboard for",
        limit="Number of top players to show (default: 10)"
    )
    async def leaderboard(self, interaction: discord.Interaction, game_type: str = None, limit: int = 10):
        """Show game leaderboards"""
        
        if not getattr(self.bot, 'db_manager', None) or not self.bot.db_manager.enabled:
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Database Required",
                    description="Leaderboards require database functionality.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )
            return
        
        # Limit validation
        if limit < 1 or limit > 25:
            limit = 10
        
        try:
            with sqlite3.connect(self.bot.db_manager.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cur = conn.cursor()
                
                if game_type:
                    # Specific game type leaderboard
                    cur.execute('''
                        SELECT 
                            user_id,
                            COUNT(*) as games,
                            MAX(score) as best_score,
                            AVG(score) as avg_score,
                            SUM(score) as total_score
                        FROM game_sessions
                        WHERE game_type = ?
                        GROUP BY user_id
                        ORDER BY best_score DESC, avg_score DESC
                        LIMIT ?
                    ''', (game_type, limit))
                    
                    title = f"🏆 {game_type.replace('_', ' ').title()} Leaderboard"
                else:
                    # Overall leaderboard
                    cur.execute('''
                        SELECT 
                            user_id,
                            COUNT(*) as games,
                            MAX(score) as best_score,
                            AVG(score) as avg_score,
                            SUM(score) as total_score
                        FROM game_sessions
                        GROUP BY user_id
                        ORDER BY total_score DESC, best_score DESC
                        LIMIT ?
                    ''', (limit,))
                    
                    title = "🏆 Overall Game Leaderboard"
                
                rows = cur.fetchall()
                
                if not rows:
                    await interaction.response.send_message(
                        embed=discord.Embed(
                            title="📊 No Leaderboard Data",
                            description="No game data found for leaderboard.",
                            color=discord.Color.orange()
                        ),
                        ephemeral=True
                    )
                    return
                
                embed = discord.Embed(
                    title=title,
                    description=f"Top {len(rows)} players",
                    color=discord.Color.gold(),
                    timestamp=discord.utils.utcnow()
                )
                
                leaderboard_text = ""
                medals = ["🥇", "🥈", "🥉"]
                
                for i, row in enumerate(rows):
                    try:
                        user = self.bot.get_user(int(row['user_id']))
                        username = user.display_name if user else f"User {row['user_id']}"
                    except:
                        username = f"User {row['user_id']}"
                    
                    medal = medals[i] if i < 3 else f"{i+1}."
                    
                    leaderboard_text += f"{medal} **{username}**\n"
                    leaderboard_text += f"    Games: {row['games']} | Best: {row['best_score']} | Avg: {round(row['avg_score'], 1)}\n\n"
                
                embed.description = f"Top {len(rows)} players\n\n{leaderboard_text}"
                
                await interaction.response.send_message(embed=embed)
                
        except Exception as e:
            logger.error(f"Error fetching leaderboard: {e}")
            await interaction.response.send_message(
                embed=discord.Embed(
                    title="❌ Error",
                    description="Failed to fetch leaderboard data.",
                    color=discord.Color.red()
                ),
                ephemeral=True
            )

async def setup(bot):
    await bot.add_cog(GameStats(bot))

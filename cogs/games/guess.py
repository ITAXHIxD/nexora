import discord
import random
import sqlite3
import json
import logging
import asyncio
from discord.ext import commands
from discord import app_commands
from datetime import datetime

logger = logging.getLogger(__name__)

class QuizGame(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.active_games = {}
        self.leaderboard = {}
        self.reactions = ["🇦", "🇧", "🇨", "🇩"]
        self.questions = [
            {
                "question": "What is Python?",
                "options": ["A programming language", "A snake", "A movie", "A book"],
                "correct": 0
            },
            # Add more questions here
        ]

    @app_commands.command(name="quizgame")
    async def quizgame(self, interaction: discord.Interaction, rounds: int = 10, time_limit: int = 30):
        """Start a multiplayer quiz game"""
        if rounds < 1 or rounds > 50:
            await interaction.response.send_message("Rounds must be between 1 and 50!", ephemeral=True)
            return
            
        channel_id = str(interaction.channel.id)
        if channel_id in self.active_games:
            await interaction.response.send_message("A game is already in progress!", ephemeral=True)
            return
            
        game_data = {
            "current_round": 0,
            "total_rounds": rounds,
            "time_limit": time_limit,
            "scores": {},
            "message": None,
            "current_question": None
        }
        
        self.active_games[channel_id] = game_data
        
        embed = discord.Embed(
            title="📚 Multiplayer Quiz Game",
            description=f"Get ready for {rounds} questions!\nAnswer by reacting to the correct option.",
            color=discord.Color.blue()
        )
        
        await interaction.response.send_message(embed=embed)
        game_data["message"] = await interaction.original_response()
        await self.start_new_round(channel_id)

    async def start_new_round(self, channel_id):
        game_data = self.active_games[channel_id]
        game_data["current_round"] += 1
        
        if game_data["current_round"] > game_data["total_rounds"]:
            await self.end_game(channel_id)
            return
            
        question = random.choice(self.questions)
        game_data["current_question"] = question
        
        embed = discord.Embed(
            title=f"Question {game_data['current_round']}/{game_data['total_rounds']}",
            description=question["question"],
            color=discord.Color.green()
        )
        
        options_text = "\n".join([f"{self.reactions[i]} {opt}" for i, opt in enumerate(question["options"])])
        embed.add_field(name="Options", value=options_text, inline=False)
        
        if game_data["scores"]:
            embed.add_field(name="🏆 Leaderboard", value=self.format_leaderboard(game_data["scores"]), inline=False)
        
        message = await game_data["message"].edit(embed=embed)
        for reaction in self.reactions[:len(question["options"])]:
            await message.add_reaction(reaction)
            
        # Timer
        embed.add_field(name="⏳ Time Remaining", value=f"{game_data['time_limit']} seconds", inline=False)
        await message.edit(embed=embed)
        
        await asyncio.sleep(game_data["time_limit"])
        await self.process_round_end(channel_id)

    async def process_round_end(self, channel_id):
        game_data = self.active_games[channel_id]
        if channel_id not in self.active_games:  # Game might have ended already
            return
            
        message = game_data["message"]
        question = game_data["current_question"]
        
        # Get reactions
        message = await message.channel.fetch_message(message.id)
        correct_reaction = self.reactions[question["correct"]]
        
        for reaction in message.reactions:
            if str(reaction.emoji) == correct_reaction:
                async for user in reaction.users():
                    if not user.bot:
                        user_id = str(user.id)
                        game_data["scores"][user_id] = game_data["scores"].get(user_id, 0) + 100
        
        embed = discord.Embed(
            title="✅ Round Complete!",
            description=f"The correct answer was: {question['options'][question['correct']]}",
            color=discord.Color.gold()
        )
        
        await message.clear_reactions()
        await message.edit(embed=embed)
        await asyncio.sleep(3)
        await self.start_new_round(channel_id)

    def format_leaderboard(self, scores):
        sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return "\n".join([f"#{i+1} <@{user_id}>: {score} points" 
                         for i, (user_id, score) in enumerate(sorted_scores[:5])])

    async def end_game(self, channel_id):
        game_data = self.active_games[channel_id]
        embed = discord.Embed(
            title="🎮 Game Over!",
            description="Final Results:",
            color=discord.Color.purple()
        )
        
        if game_data["scores"]:
            embed.add_field(name="🏆 Final Leaderboard", value=self.format_leaderboard(game_data["scores"]), inline=False)
        else:
            embed.add_field(name="🏆 Final Leaderboard", value="No scores recorded!", inline=False)
        
        await game_data["message"].edit(embed=embed)
        del self.active_games[channel_id]

async def setup(bot):
    await bot.add_cog(QuizGame(bot))

"""
cogs/fun/tod.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Truth or Dare Party Engine
Supports Solo (self) and PvP challenges, multiple rating tiers (PG / Teen / Spicy),
dedicated /truth, /dare, and /tod commands, seamless Truth/Dare switching in the
same session, turn notifications, and 100% active, instant prompts (no waiting 30 min).
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import logging
import random
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from utils.ui import (
    BRAND_COLOR,
    ERROR_COLOR,
    PURPLE_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    send_view,
)

logger = logging.getLogger(__name__)

# ── Truth & Dare Prompt Database ───────────────────────────────────────────────

TRUTHS = {
    "pg": [
        "What is the most embarrassing thing your parents or family ever caught you doing?",
        "If you could trade lives with anyone in this server for 24 hours, who would it be and why?",
        "What is the weirdest food combination you secretly love that everyone else finds gross?",
        "Have you ever pretended to be sick or asleep just to avoid hanging out with someone?",
        "What is the dumbest argument you have ever had with someone on the internet?",
        "What is your ultimate guilty pleasure song or video that you would never admit publicly?",
        "What is one weird habit you have when you are completely alone in your room?",
        "If you were forced to delete every app on your phone except three, which three are staying?",
        "What cartoon or video game character were you irrationally terrified of as a kid?",
        "What is the most ridiculous excuse you ever gave a teacher or boss for being late or missing work?",
        "Have you ever accidentally waved back at someone who was waving to the person behind you?",
        "What is the single worst meal you have ever cooked or prepared with your own hands?",
        "If you were an animal, what species would match your exact personality and morning mood?",
        "Have you ever tripped in public and pretended to stretch or tie your shoe to play it off?",
        "What is something you believed for way too long before finding out it was completely fake?",
        "If you were forced to live inside a video game universe forever, which game are you choosing?",
        "What is a popular movie, anime, or TV show that everyone loves but you secretly think is pure garbage?",
        "Have you ever practiced an argument in the shower with full dramatic hand gestures and facial expressions?",
        "What is the most useless talent or party trick you possess that serves zero real-world purpose?",
        "If your pet (or a pet you know) could speak for 5 minutes, what is the first thing they would expose you for?",
        "What is the funniest or weirdest WiFi network name you have ever connected to or seen?",
        "If you were arrested with zero context given, what would your friends automatically assume you did?",
        "Have you ever replied to a message with 'sorry just seeing this' when you literally saw it 3 weeks ago?",
        "What is your spirit vegetable and why does it represent your current life stage?",
        "If you had a permanent warning label stamped on you, what would the fine print say?",
        "What is the weirdest or most chaotic dream you remember having recently?",
        "Have you ever eaten something that dropped on the floor well past the 5-second rule?",
        "What is the longest you have gone without showering during an intense gaming or lazy binge?",
        "If you won 1 million dollars tomorrow, what is the first completely unnecessary thing you would buy?",
        "What is your least favorite daily chore that you will actively procrastinate on for days?",
        "Have you ever tried to unlock your front door using your car remote key fob?",
        "What board game or video game ruins friendships the fastest in your experience?",
        "If your life was turned into a comedy sitcom, what would the season finale be about?",
        "What is the worst fashion trend or haircut you unironically rocked in the past?",
        "Have you ever sung at the top of your lungs in your car only to notice someone staring at a red light?",
        "What is your most controversial hot take about food or pizza toppings?",
        "If you could have any completely useless superpower, what would you choose?",
        "What is your most irrational fear that makes zero logical sense to anyone else?",
        "Have you ever laughed at a completely inappropriate moment and had to cough to cover it up?",
    ],
    "teen": [
        "What is the biggest lie you have ever told on Discord or social media to sound cooler?",
        "Who in this server would you trust the least with your unlocked phone and private DMs?",
        "What is the cringiest message you ever sent to someone you had a crush on that keeps you awake at night?",
        "Have you ever ghosted someone because you found a small petty flaw you couldn't get over? What was it?",
        "What is something you searched up on Google or YouTube that you immediately cleared from your history?",
        "If you had to date someone currently active in this text or voice channel, who are you picking?",
        "What is the biggest secret you have kept from your best friend that would shock them?",
        "Have you ever stalked someone's profile, status, or Spotify listening activity for more than 20 minutes straight?",
        "What is the worst outfit or haircut you ever wore where you genuinely thought you were the main character?",
        "Have you ever blamed a pet, sibling, or 'bad internet' for something that was 100% your own fault?",
        "Who was your very first fictional character or anime crush that you were obsessed with?",
        "What is the most petty reason you ever stopped being friends or talking with someone?",
        "What is the highest daily screen time you have ever clocked on your phone in a single day?",
        "Have you ever muted a group chat or server because you couldn't stand one specific person's messages?",
        "What is something you pretend to dislike just because it's popular or cool to hate on it?",
        "Have you ever accidentally sent a screenshot of a chat to the exact person the screenshot was about?",
        "What is the most desperate thing you have ever done to get someone's attention online?",
        "If your camera roll was projected onto a big screen right now, how cooked are you on a scale of 1 to 10?",
        "What is the cringiest username, gamertag, or email address you ever unironically used?",
        "Have you ever faked having bad WiFi or microphone lag just to escape an awkward voice call?",
        "Who in this server gives off the most chaotic energy and keeps you on edge?",
        "Have you ever pretended to fall asleep while texting someone just to end the conversation?",
        "If you had to delete either Discord, TikTok/Reels, or YouTube forever, which one goes first?",
        "Have you ever stalked an ex or someone you disliked from a secret burner or alt account?",
        "What is the weirdest thing you do when you are home completely alone with nobody watching?",
        "Have you ever lied about your age, location, or hobbies on the internet?",
        "Who was the last person you looked up on Instagram, Twitter, or Discord search bar?",
        "What is the most dramatic meltdown you ever had over a video game loss or minor inconvenience?",
        "Have you ever talked trash about someone in this server and then acted super friendly to them right after?",
        "What is your biggest personal ick in people that immediately makes you lose interest?",
        "Have you ever re-read your own text messages repeatedly after sending them just to admire how cool they sounded?",
        "What is the longest amount of time you spent drafting a single text or DM before hitting send?",
        "If you could read the DMs of any one person in this server for 5 minutes, whose DMs are you opening?",
        "Have you ever unfriended or blocked someone without giving them any explanation whatsoever?",
        "What is the most awkward or humiliating interaction you have had with a crush in real life?",
        "What is the dumbest thing you ever bought with your own money that you immediately regretted?",
        "If someone offered you $10,000 to never speak to your best friend again, would you take the money?",
        "What is the cringiest trend or dance you secretly attempted in your room with the door locked?",
        "Who in this server would survive the longest in a zombie apocalypse, and who dies within 5 minutes?",
    ],
    "spicy": [
        "Confess the initials of someone in this server (or Discord) who you secretly find attractive or have vibes with.",
        "What is the boldest, most flirtatious, or unhinged DM you have ever sent to someone?",
        "Have you ever flirted with someone just to get free stuff, game carries, Discord Nitro, or attention?",
        "Rate your own flirting rizz from 1 to 10 with complete honesty, and give one example of your work.",
        "What is the most romantic or embarrassing dream you've ever had about someone you know in real life?",
        "Have you ever sent a risky photo or late-night text and immediately put your phone face down in pure panic?",
        "If you had to go on a 24-hour date with one person in this server, who are you picking?",
        "What is the quickest you have ever caught deep feelings for someone you barely knew?",
        "Have you ever had a crush on someone your friend was actively dating or into?",
        "What is your biggest secret turn-on or personality trait that instantly attracts you to someone?",
        "What is the absolute worst date or romantic hangout you have ever experienced? Give the juicy details.",
        "Have you ever stayed up until 4 AM texting someone and caught feelings that you later denied to everyone?",
        "What is the biggest red flag you willingly ignored in someone just because you found them attractive?",
        "Confess the most embarrassing pet name you have ever used or been called in a relationship.",
        "Have you ever checked someone's follower count or profile before deciding if they were worth talking to?",
        "What is the closest you have ever come to getting caught doing something intimate or forbidden?",
        "If you were 100% guaranteed they would say yes, who would you ask out on a date right this second?",
        "What is the most dramatic breakup or fight you have ever witnessed or been a part of?",
        "Have you ever lied about your dating experience or past relationships to seem more experienced?",
        "Who in this server gives off the biggest 'heartbreaker' energy?",
        "What is the most cringe-inducing pickup line you have ever delivered or received?",
        "Have you ever stalked someone's location on Snap Map, Find My, or Discord activity to see who they were with?",
        "What is something you find extremely attractive that most other people would find weird or unconventional?",
        "Have you ever led someone on just because you were bored and enjoyed the attention?",
        "If the challenger could read your last 3 deleted messages or search history, what would they find out about you?",
    ],
}

DARES = {
    "pg": [
        "Send a 10-second voice note reading the ingredients on the nearest bottle or snack packaging like an epic movie battle speech.",
        "Post the 7th photo in your camera roll into chat right now with zero explanation.",
        "Send a voice note doing your most accurate animal impression (cow, dolphin, or goat) for 8 seconds.",
        "Write a 4-line dramatic poetry stanza dedicated to your favorite food in chat right now.",
        "Post your most frequently used emojis list into chat and let everyone judge your vibes.",
        "Send a voice note attempting to beatbox for 10 seconds straight with zero hesitation.",
        "Ping someone in this server and say: 'The ancient prophecy foretold your return.' and refuse to elaborate.",
        "Send a selfie holding a random household object from your desk like an Olympic gold medal.",
        "Send a voice note doing your most sinister, dramatic movie villain laugh.",
        "Ask a completely serious, unhinged philosophical question in general chat (e.g. 'Are hot dogs tacos?').",
        "Send a message typed using only your nose or elbow and see what comes out.",
        "Rate the challenger's avatar and banner on a scale of 1 to 10 with honest critique.",
        "Send a voice note reading Wikipedia's article on potatoes in a dramatic British nature documentary voice.",
        "Post the funniest or dumbest meme currently saved on your device right now.",
        "Declare yourself the main character of this server and state your dramatic superhero backstory in chat.",
        "Send a voice note singing the chorus of your favorite childhood cartoon theme song.",
        "Drop a screenshot of your current music queue on Spotify, YouTube, or Apple Music.",
        "Challenge the challenger to an immediate game of Rock-Paper-Scissors right now in chat.",
        "Send a message in chat giving a passionate 3-sentence motivational speech about drinking water.",
        "Send a photo of an ordinary object nearby and describe it in chat as if it's an ultra-rare mythical RPG artifact.",
    ],
    "teen": [
        "DM a friend in this server: 'We need to talk... it's about what happened yesterday.' and screenshot their confused response!",
        "Post a screenshot of your phone's screen time for today (no cropping out your most used apps!).",
        "Send a voice note confessing your undying love to a household object (toaster, chair, or pillow) with extreme passion.",
        "DM your best friend: 'I have a confession to make... I think I'm Batman' and post the screenshot proof.",
        "Send a voice note reading the lyrics of a hard rap song like an emotional Shakespearean sonnet.",
        "DM someone active: 'You won't believe what they said about you...' and wait 60 seconds before saying 'they said you're awesome!'",
        "Rate everyone currently active in this channel on a scale of 1 to 10 based purely on their aura.",
        "Post a screenshot of your Discord mutual servers with the person who dared you.",
        "Write a 4-line diss track about your favorite video game or anime in chat right now.",
        "DM someone in this server: 'Are you free later? We need to calculate our astrological compatibility.' and screenshot the reply.",
        "Send a message asking: 'If I were a vegetable, which one would I be?' and accept whatever chat says.",
        "Send a voice note singing the chorus of a cheesy pop song at the top of your lungs.",
        "Post the oldest saved meme in your camera roll into chat right now.",
        "DM a random person in this server: 'You dropped your crown, king/queen 👑' and screenshot their reaction.",
        "Send a message in chat confessing what you think your biggest red flag is in friendships.",
        "Send a voice note attempting to speak in a fancy royal Victorian accent for 15 seconds.",
        "Reveal your biggest musical guilty pleasure and send a link to the song in chat right now.",
        "Send a screenshot of your YouTube recommended page right this second.",
        "DM someone: 'Quick, act natural, they are watching us' and screenshot their confusion.",
        "Type out a formal 3-sentence resignation speech stepping down as an active chatter in chat.",
    ],
    "spicy": [
        "DM the person you find most attractive or coolest in this server a genuine compliment, and screenshot the proof!",
        "Post a screenshot of the last DM you sent to anyone (names can be blurred, but the message must be visible!).",
        "Send a voice note whispering something utterly dramatic and romantic like a movie trailer voiceover.",
        "Ping the person you think gives off the biggest 'heartbreaker' energy in this server and explain why.",
        "DM someone: 'I had a dream about you last night' and wait for their reply before explaining a silly dream about cheese.",
        "Post your top 3 most recently played songs on Spotify or YouTube without hiding anything.",
        "Send a voice note delivering your best, smoothest flirty pickup line directly to the challenger.",
        "Send a flirty or dramatic meme into chat and tag the person you think fits the meme best.",
        "DM a friend: 'Be 100% honest, on a scale of 1-10, how good am I at flirting?' and screenshot the response.",
        "Voice note a 10-second dramatic romantic movie line impression with maximum cinematic intensity.",
        "Describe what your ideal romantic rainy day date looks like in 3 detailed sentences.",
        "Send a message in chat asking: 'Who here would survive a week on a deserted island with me?'",
        "Send a message declaring who in this server you think would make the best couple, and why.",
        "Ping someone in this server and confess what your very first impression of them was when you first saw them.",
        "Post a screenshot of your blocked list count or search history bar right now.",
    ],
}

FORFEIT_PUNISHMENTS = [
    "🐔 **Chicken Out Penalty:** Send a 5-second voice note clucking like a confused rooster right now in chat!",
    "🐔 **Chicken Out Penalty:** Type out a 3-sentence formal apology in chat explaining why you backed down from glory.",
    "🐔 **Chicken Out Penalty:** Post a picture of chicken nuggets in chat and admit: 'These are my brothers and sisters.'",
    "🐔 **Chicken Out Penalty:** Give the challenger 1,000 imaginary Aura points in chat with a formal certificate of defeat.",
    "🐔 **Chicken Out Penalty:** Send a GIF of a fainting goat in chat and state: 'This is a live photo of my bravery.'",
    "🐔 **Chicken Out Penalty:** Send a message in chat declaring the challenger as your supreme overlord for the day.",
    "🐔 **Chicken Out Penalty:** You must react to the challenger's last 5 messages with 🐣 and 👑.",
    "🐔 **Chicken Out Penalty:** Write a 4-line poem dedicated to the prompt you were too terrified to complete.",
    "🐔 **Chicken Out Penalty:** Send a message in chat saying: 'I have brought dishonor upon my Discord ancestors.'",
    "🐔 **Chicken Out Penalty:** Send a voice note doing a 5-second dramatic gasp of utter defeat.",
]


class TODView(NexoraView):
    """Components V2 Truth or Dare Interactive Game View."""

    def __init__(
        self,
        bot: commands.Bot,
        challenger: discord.Member,
        target: discord.Member,
        rating: str = "teen",
        initial_prompt_type: Optional[str] = None,
        timeout: float = 180.0,
    ):
        super().__init__(bot=bot, color=PURPLE_COLOR, timeout=timeout)
        self.challenger = challenger
        self.target = target
        self.rating = rating.lower()
        self.current_prompt = None
        self.prompt_type = None  # "Truth" or "Dare"
        self.is_completed = False
        self.is_forfeit = False
        self.reroll_count = 0

        if initial_prompt_type in ("Truth", "Dare"):
            self._show_prompt(initial_prompt_type)
        else:
            self._build_prompt_picker()

    def _build_prompt_picker(self):
        self.clear_container()

        rating_badge = {"pg": "🟢 PG (Friendly)", "teen": "🟡 Teen (Party)", "spicy": "🔴 Spicy (Wild)"}.get(self.rating, "🟡 Teen")

        if self.challenger.id == self.target.id:
            header = (
                f"# 🎭 Truth or Dare · Solo Session\n"
                f"> 👤 Playing: {self.target.mention} · Tier: **{rating_badge}**\n\n"
                f"Choose Truth or Dare below to get your prompt:"
            )
        else:
            header = (
                f"# 🎭 Truth or Dare · PvP Duel!\n"
                f"> ⚔️ **{self.challenger.display_name}** challenged **{self.target.display_name}**!\n"
                f"> 👤 Target: {self.target.mention} · Tier: **{rating_badge}**\n\n"
                f"Waiting for {self.target.mention} to make a choice..."
            )

        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        btn_truth = discord.ui.Button(label="Truth", emoji="💬", style=discord.ButtonStyle.primary)
        btn_dare = discord.ui.Button(label="Dare", emoji="⚡", style=discord.ButtonStyle.danger)
        btn_random = discord.ui.Button(label="Random Pick", emoji="🎲", style=discord.ButtonStyle.secondary)

        btn_truth.callback = self._on_choose_truth
        btn_dare.callback = self._on_choose_dare
        btn_random.callback = self._on_choose_random

        self.add_row(btn_truth, btn_dare, btn_random, DismissButton(user_id=self.challenger.id))
        self.add_footer("Both Truth and Dare can be played on self or friends · 180s timeout")

    def _show_prompt(self, p_type: str, prompt: Optional[str] = None):
        self.prompt_type = p_type
        if prompt:
            self.current_prompt = prompt
        else:
            pool = TRUTHS[self.rating] if p_type == "Truth" else DARES[self.rating]
            self.current_prompt = random.choice(pool)

        self.clear_container()
        emoji = "💬" if p_type == "Truth" else "⚡"
        self._color = BRAND_COLOR if p_type == "Truth" else ERROR_COLOR

        rating_labels = {"pg": "🟢 PG", "teen": "🟡 TEEN", "spicy": "🔴 SPICY"}
        r_label = rating_labels.get(self.rating, "🟡 TEEN")

        if self.challenger.id == self.target.id:
            header = (
                f"# {emoji} {p_type} for @{self.target.name} (Solo)\n"
                f"> 👤 Player: {self.target.mention} · Tier: **{r_label}**\n\n"
                f"### 📋 The Task:\n"
                f"> **\"{self.current_prompt}\"**"
            )
        else:
            header = (
                f"# {emoji} {p_type} for @{self.target.name}\n"
                f"> ⚔️ Challenged by {self.challenger.mention} · 👤 Target: {self.target.mention} · Tier: **{r_label}**\n\n"
                f"### 📋 The Task:\n"
                f"> **\"{self.current_prompt}\"**"
            )

        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        # Primary Action Row: Complete, Forfeit, Reroll
        btn_done = discord.ui.Button(label="I Did It! (Completed)", emoji="✅", style=discord.ButtonStyle.success)
        btn_forfeit = discord.ui.Button(label="Chicken Out (Forfeit)", emoji="🐔", style=discord.ButtonStyle.danger)
        btn_reroll = discord.ui.Button(
            label=f"Reroll ({2 - self.reroll_count})",
            emoji="🔄",
            style=discord.ButtonStyle.secondary,
            disabled=(self.reroll_count >= 2),
        )

        btn_done.callback = self._on_done
        btn_forfeit.callback = self._on_forfeit
        btn_reroll.callback = self._on_reroll
        self.add_row(btn_done, btn_forfeit, btn_reroll)

        # Secondary Row: Instant Switch to Truth or Dare in the SAME session!
        if p_type == "Truth":
            btn_switch = discord.ui.Button(label="Switch to Dare ⚡", style=discord.ButtonStyle.danger)
            btn_switch.callback = lambda i: self._switch_to(i, "Dare")
            btn_another = discord.ui.Button(label="Another Truth 💬", style=discord.ButtonStyle.primary)
            btn_another.callback = lambda i: self._switch_to(i, "Truth")
        else:
            btn_switch = discord.ui.Button(label="Switch to Truth 💬", style=discord.ButtonStyle.primary)
            btn_switch.callback = lambda i: self._switch_to(i, "Truth")
            btn_another = discord.ui.Button(label="Another Dare ⚡", style=discord.ButtonStyle.danger)
            btn_another.callback = lambda i: self._switch_to(i, "Dare")

        btn_steal = discord.ui.Button(label="Steal Turn (I'll Do It!)", emoji="🙋", style=discord.ButtonStyle.secondary)
        btn_steal.callback = self._on_steal_turn

        self.add_row(btn_another, btn_switch, btn_steal, DismissButton(user_id=self.challenger.id))
        self.add_footer("Complete the prompt in chat/voice, then click 'I Did It!' or chicken out!")

    async def _check_turn(self, interaction: discord.Interaction) -> bool:
        # If solo, author can click, or if challenge, target OR challenger can click
        if self.challenger.id == self.target.id:
            return True
        if interaction.user.id in (self.target.id, self.challenger.id):
            return True
        await interaction.response.send_message(
            f"❌ It's {self.target.mention}'s turn! (Or click 'Steal Turn' to take it over)",
            ephemeral=True,
        )
        return False

    async def _on_choose_truth(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self._show_prompt("Truth")
        await interaction.response.edit_message(view=self)

    async def _on_choose_dare(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self._show_prompt("Dare")
        await interaction.response.edit_message(view=self)

    async def _on_choose_random(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        p_type = random.choice(["Truth", "Dare"])
        self._show_prompt(p_type)
        await interaction.response.edit_message(view=self)

    async def _switch_to(self, interaction: discord.Interaction, p_type: str):
        if not await self._check_turn(interaction):
            return
        self.reroll_count = 0
        self._show_prompt(p_type)
        await interaction.response.edit_message(view=self)

    async def _on_steal_turn(self, interaction: discord.Interaction):
        # Allow anyone in the channel to jump in and claim this turn!
        old_target = self.target
        self.target = interaction.user
        if self.challenger.id == self.target.id and old_target.id != interaction.user.id:
            self.challenger = old_target

        self.reroll_count = 0
        self._show_prompt(self.prompt_type or "Truth")
        await interaction.response.edit_message(view=self)
        try:
            await interaction.channel.send(
                f"🙋 {interaction.user.mention} stole the turn and took over the {self.prompt_type}!",
                delete_after=10,
            )
        except Exception:
            pass

    async def _on_reroll(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        if self.reroll_count >= 2:
            return await interaction.response.send_message("⚠️ You have used all available rerolls for this prompt!", ephemeral=True)

        self.reroll_count += 1
        pool = TRUTHS[self.rating] if self.prompt_type == "Truth" else DARES[self.rating]
        filtered = [p for p in pool if p != self.current_prompt]
        new_prompt = random.choice(filtered or pool)
        self._show_prompt(self.prompt_type, prompt=new_prompt)
        await interaction.response.edit_message(view=self)

    async def _on_done(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self.is_completed = True
        self.clear_container()
        self._color = SUCCESS_COLOR

        header = (
            f"# 🏆 Challenge Completed!\n"
            f"> {self.target.mention} successfully answered/completed their **{self.prompt_type}**!\n\n"
            f"• **Task:** *\"{self.current_prompt}\"*\n"
            f"• **Respect:** +1000 Aura Points ✨"
        )
        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)
        self.add_footer(f"Nexora Truth or Dare · Next up: {self.target.display_name} gets to challenge someone!")

        btn_truth = discord.ui.Button(label="Next: Truth 💬", style=discord.ButtonStyle.primary)
        btn_dare = discord.ui.Button(label="Next: Dare ⚡", style=discord.ButtonStyle.danger)
        btn_next = discord.ui.Button(label="Pass Torch (New Player)", emoji="🔄", style=discord.ButtonStyle.secondary)
        btn_random = discord.ui.Button(label="Challenge Random", emoji="🎲", style=discord.ButtonStyle.secondary)

        btn_truth.callback = lambda i: self._next_round(i, "Truth")
        btn_dare.callback = lambda i: self._next_round(i, "Dare")
        btn_next.callback = self._on_next_turn
        btn_random.callback = self._on_challenge_random

        self.add_row(btn_truth, btn_dare, btn_next, btn_random, DismissButton(user_id=self.target.id))
        await interaction.response.edit_message(view=self)

    async def _on_forfeit(self, interaction: discord.Interaction):
        if not await self._check_turn(interaction):
            return
        self.is_forfeit = True
        penalty = random.choice(FORFEIT_PUNISHMENTS)
        self.clear_container()
        self._color = WARNING_COLOR

        header = (
            f"# 🐔 CHICKEN OUT!\n"
            f"> {self.target.mention} backed down from their {self.prompt_type}!\n\n"
            f"{penalty}"
        )
        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)
        self.add_footer("Nexora Truth or Dare · Better luck next time!")

        btn_truth = discord.ui.Button(label="Next: Truth 💬", style=discord.ButtonStyle.primary)
        btn_dare = discord.ui.Button(label="Next: Dare ⚡", style=discord.ButtonStyle.danger)
        btn_next = discord.ui.Button(label="Pass Torch (New Player)", emoji="🔄", style=discord.ButtonStyle.secondary)
        btn_random = discord.ui.Button(label="Challenge Random", emoji="🎲", style=discord.ButtonStyle.secondary)

        btn_truth.callback = lambda i: self._next_round(i, "Truth")
        btn_dare.callback = lambda i: self._next_round(i, "Dare")
        btn_next.callback = self._on_next_turn
        btn_random.callback = self._on_challenge_random

        self.add_row(btn_truth, btn_dare, btn_next, btn_random, DismissButton(user_id=self.target.id))
        await interaction.response.edit_message(view=self)

    async def _next_round(self, interaction: discord.Interaction, p_type: str):
        # Start immediate next round for current player or interaction user
        self.target = interaction.user
        self.is_completed = False
        self.is_forfeit = False
        self.reroll_count = 0
        self._show_prompt(p_type)
        await interaction.response.edit_message(view=self)

    async def _on_next_turn(self, interaction: discord.Interaction):
        prev_target = self.target
        self.challenger = prev_target
        if interaction.user.id != prev_target.id:
            self.target = interaction.user
        else:
            self.target = self.challenger if self.challenger.id != prev_target.id else interaction.user

        self.is_completed = False
        self.is_forfeit = False
        self.reroll_count = 0
        self.current_prompt = None
        self.prompt_type = None
        self._color = PURPLE_COLOR
        self._build_prompt_picker()
        await interaction.response.edit_message(view=self)

        try:
            await interaction.channel.send(
                f"🔔 {self.target.mention}, it's your turn in Truth or Dare! Pick Truth or Dare above.",
                delete_after=10,
            )
        except Exception:
            pass

    async def _on_challenge_random(self, interaction: discord.Interaction):
        guild = interaction.guild
        candidates = [m for m in guild.members if not m.bot and m.id != interaction.user.id] if guild else []
        new_target = random.choice(candidates) if candidates else interaction.user

        self.challenger = interaction.user
        self.target = new_target
        self.is_completed = False
        self.is_forfeit = False
        self.reroll_count = 0
        self.current_prompt = None
        self.prompt_type = None
        self._color = PURPLE_COLOR
        self._build_prompt_picker()
        await interaction.response.edit_message(view=self)

        try:
            await interaction.channel.send(
                f"🔔 {self.target.mention}, you have been randomly chosen for Truth or Dare by {self.challenger.mention}!",
                delete_after=10,
            )
        except Exception:
            pass


class TruthOrDare(commands.Cog):
    """Interactive Components V2 Truth or Dare game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _resolve_target_and_rating(
        self,
        ctx: commands.Context,
        target: Optional[discord.Member],
        rating: Optional[str],
    ) -> tuple[discord.Member, str]:
        """Safely resolve target (self vs someone else) and rating tier."""
        resolved_target = target or ctx.author
        resolved_rating = (rating or "teen").lower()

        if resolved_rating not in ("pg", "teen", "spicy"):
            resolved_rating = "teen"

        return resolved_target, resolved_rating

    async def _launch_game(
        self,
        ctx: commands.Context,
        target: Optional[discord.Member],
        rating: Optional[str],
        initial_prompt_type: Optional[str] = None,
    ):
        challenged, selected_rating = self._resolve_target_and_rating(ctx, target, rating)

        if challenged.bot:
            return await ctx.send("❌ You cannot challenge a bot to Truth or Dare!", ephemeral=True)

        view = TODView(
            bot=self.bot,
            challenger=ctx.author,
            target=challenged,
            rating=selected_rating,
            initial_prompt_type=initial_prompt_type,
        )

        is_self = challenged.id == ctx.author.id
        content = None
        if not is_self:
            content = f"🎭 {challenged.mention}, you have been challenged to Truth or Dare by {ctx.author.mention}!"

        sent_msg = await send_view(ctx, view, content=content)
        view.message = sent_msg

        if not is_self:
            try:
                await ctx.channel.send(
                    f"🔔 {challenged.mention}, you have a Truth or Dare challenge from {ctx.author.mention}!",
                    delete_after=10,
                )
            except Exception:
                pass

        logger.info(
            "TOD: %s launched Truth or Dare (target: %s, rating: %s, mode: %s, is_self: %s)",
            ctx.author,
            challenged,
            selected_rating,
            initial_prompt_type or "Picker",
            is_self,
        )

    # ── Error Handlers for flexible prefix commands (e.g. n!truth spicy or n!dare me) ──

    async def _handle_arg_fallback(
        self,
        ctx: commands.Context,
        error: Exception,
        prompt_type: Optional[str],
    ):
        if isinstance(error, commands.MemberNotFound):
            arg = str(error.argument).lower().strip()
            # If user typed "n!truth spicy" or "n!dare pg"
            if arg in ("pg", "teen", "spicy"):
                return await self._launch_game(ctx, ctx.author, arg, prompt_type)
            # If user typed "n!truth me" or "n!dare self"
            if arg in ("me", "self", "myself"):
                return await self._launch_game(ctx, ctx.author, "teen", prompt_type)
        await ctx.send(f"❌ {error}", ephemeral=True)

    @commands.hybrid_command(
        name="tod",
        aliases=["truthordare"],
        description="🎭 Interactive Truth or Dare party game with ratings and PvP/solo modes",
    )
    @app_commands.describe(
        target="Member to challenge (leave empty to play yourself)",
        rating="Content tier: pg, teen, or spicy (default: teen)",
    )
    @app_commands.choices(
        rating=[
            app_commands.Choice(name="🟢 PG (Family Friendly)", value="pg"),
            app_commands.Choice(name="🟡 Teen (Party & Secrets)", value="teen"),
            app_commands.Choice(name="🔴 Spicy (Wild Challenges)", value="spicy"),
        ]
    )
    @commands.guild_only()
    async def tod(
        self,
        ctx: commands.Context,
        target: Optional[discord.Member] = None,
        rating: Optional[str] = "teen",
    ):
        await self._launch_game(ctx, target, rating, None)

    @tod.error
    async def tod_error(self, ctx: commands.Context, error: Exception):
        await self._handle_arg_fallback(ctx, error, None)

    @commands.hybrid_command(
        name="truth",
        description="💬 Get a direct Truth prompt for yourself or challenge someone",
    )
    @app_commands.describe(
        target="Member to challenge (leave empty to play yourself)",
        rating="Content tier: pg, teen, or spicy (default: teen)",
    )
    @app_commands.choices(
        rating=[
            app_commands.Choice(name="🟢 PG (Family Friendly)", value="pg"),
            app_commands.Choice(name="🟡 Teen (Party & Secrets)", value="teen"),
            app_commands.Choice(name="🔴 Spicy (Wild Secrets)", value="spicy"),
        ]
    )
    @commands.guild_only()
    async def truth(
        self,
        ctx: commands.Context,
        target: Optional[discord.Member] = None,
        rating: Optional[str] = "teen",
    ):
        await self._launch_game(ctx, target, rating, "Truth")

    @truth.error
    async def truth_error(self, ctx: commands.Context, error: Exception):
        await self._handle_arg_fallback(ctx, error, "Truth")

    @commands.hybrid_command(
        name="dare",
        description="⚡ Get a direct Dare prompt for yourself or challenge someone",
    )
    @app_commands.describe(
        target="Member to challenge (leave empty to play yourself)",
        rating="Content tier: pg, teen, or spicy (default: teen)",
    )
    @app_commands.choices(
        rating=[
            app_commands.Choice(name="🟢 PG (Family Friendly)", value="pg"),
            app_commands.Choice(name="🟡 Teen (Party Fun)", value="teen"),
            app_commands.Choice(name="🔴 Spicy (Wild Challenges)", value="spicy"),
        ]
    )
    @commands.guild_only()
    async def dare(
        self,
        ctx: commands.Context,
        target: Optional[discord.Member] = None,
        rating: Optional[str] = "teen",
    ):
        await self._launch_game(ctx, target, rating, "Dare")

    @dare.error
    async def dare_error(self, ctx: commands.Context, error: Exception):
        await self._handle_arg_fallback(ctx, error, "Dare")


async def setup(bot: commands.Bot):
    await bot.add_cog(TruthOrDare(bot))
    logger.debug("Loaded TruthOrDare")

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
        "What's a completely pointless hill you'll die on?",
        "Which fictional universe would reject you within five minutes, and why?",
        "What's the weirdest thing you would confidently win a debate about?",
        "What tiny inconvenience turns you into a dramatic supervillain?",
        "What's your most irrational, absolutely non-negotiable food opinion?",
        "If your personality were a patch note, what would the latest update say?",
        "What's a skill you have that is impressive for approximately zero seconds?",
        "Which three objects would you bring to a very badly planned apocalypse?",
        "What's the most NPC thing you've done in real life?",
        "If your pet or favourite animal could roast you, what would its opening line be?",
        "What's a popular thing you still don't understand the hype around?",
        "Which cartoon character would be the worst roommate?",
        "What's the most ridiculous thing you'd buy if you had to spend ₹1,000 today?",
        "What's your most useless superpower, and how would you abuse it?",
        "Which everyday task would you make illegal if you became king for a day?",
        "What's the funniest misunderstanding you've had that you can share publicly?",
        "What would your warning label say if people had to read it before talking to you?",
        "What food could you defend like a lawyer in court?",
        "If your life had loading-screen tips, what would tip number one say?",
        "What's the weirdest name you'd give a Wi-Fi network?",
        "Which game would expose your real personality the fastest?",
        "What's the most dramatic reaction you've had to a minor inconvenience?",
        "What's one thing you were confidently wrong about for an embarrassing amount of time?",
        "If aliens watched you for a day, what would confuse them the most?",
        "What would be your completely unnecessary signature move?",
        "What's the funniest thing your brain has made you forget at the worst possible moment?",
        "Which fictional villain has a point, even if their methods are terrible?",
        "What's the most cursed food combination you'd actually try?",
        "If your week were a movie genre, what genre would it be right now?",
        "What's a harmless conspiracy theory you could invent and almost sell to people?"
    ],
    "teen": [
        "What's your most unserious red flag that your friends would absolutely confirm?",
        "What's the boldest message you've typed and then deleted before sending?",
        "What's your most embarrassing gaming moment that still deserves a replay?",
        "What's a song you know every word to but would never put on aux first?",
        "What's the pettiest reason you've ever lost an argument?",
        "What's your most chaotic habit in group chats?",
        "What's the funniest excuse you've used to dodge a plan?",
        "What's one opinion about a game, anime, or show that would get you cooked here?",
        "What's the most obvious hint you've ever completely failed to notice?",
        "What's something you pretend to be good at until someone asks for proof?",
        "What's your personal definition of being absolutely cooked?",
        "What's your most embarrassing username era?",
        "What's a green flag in a friend that deserves way more appreciation?",
        "What's the most unserious thing that can instantly improve your mood?",
        "What's your biggest 'I can fix it' moment that absolutely did not get fixed?",
        "What's the weirdest thing you've done to procrastinate?",
        "What's a trend you joined late and then defended like an original fan?",
        "What's the most dramatic way you've ever reacted to losing a game?",
        "What's something your friends tease you about because it's painfully accurate?",
        "What's your most chaotic 2 a.m. thought that you can safely share?",
        "What's a fictional character you would trust with your life, despite all evidence?",
        "What's your most harmless delusion about your own talent?",
        "What's the fastest way someone can make you lose an argument with one sentence?",
        "What's a compliment you still remember because it caught you off guard?",
        "What's a social situation where you instantly forget how to act normal?",
        "What's the funniest thing you've done to look cool that had the opposite effect?",
        "What would your enemies put in a presentation titled 'Why They're Like This'?",
        "What's your strongest 'hear me out' opinion about a fictional character?",
        "What's something you judge people for even though you do it too?",
        "If the server gave you an award, what painfully specific category would you win?"
    ],
    "spicy": [
        "What's your most obvious tell when you like someone or really want their approval?",
        "What's the smoothest line you've heard—and was it actually smooth?",
        "What's your biggest green flag that you wish people noticed more?",
        "What's a tiny thing someone can do that instantly makes them more attractive?",
        "What's the boldest move you've made to get someone's attention?",
        "What's your most embarrassing attempt at acting mysterious?",
        "What's your biggest harmless ick that makes no logical sense?",
        "What's a compliment you'd remember for years if the right person said it?",
        "What's your ideal first-date vibe: chaotic adventure, cosy chill, or full main-character cinema?",
        "What's the most obvious hint you've dropped and hoped someone would catch?",
        "What's your flirting style: smooth, awkward, chaotic, or accidental comedian?",
        "What's the most attractive personality trait that has nothing to do with looks?",
        "What's one romantic cliché you secretly think is elite?",
        "What's the most nervous you've been before sending a message?",
        "What's your worst attempt at playing it cool around someone you liked?",
        "What's a green flag that instantly beats a good first impression?",
        "What's your funniest almost-confession or almost-sent message story?",
        "Who would be the best person here to coach you through a crush situation—and why?",
        "What's one thing that makes someone instantly memorable to you?",
        "What's the most chaotic fictional couple you secretly support?",
        "What's your most confident opinion about love that experience has not tested yet?",
        "What's more intimidating: making the first move or keeping eye contact?",
        "What's a pickup line so terrible it might actually work on you?",
        "What's your most dramatic 'I am never doing that again' social moment?",
        "What's the difference between someone being your type and someone being bad news?",
        "What's a romantic gesture that is simple but genuinely elite?",
        "What's your biggest 'I fumbled that' moment, only as detailed as you're comfy sharing?",
        "What's one quality that can make you catch feelings faster than you expected?",
        "What's the most unserious reason you've ever found someone charming?",
        "If your love life had a warning label, what would it say?"
    ],
}

DARES = {
    "pg": [
        "Give a 20-second TED Talk defending why your favourite snack should be a national treasure.",
        "Describe your current mood as a fake movie title and write its dramatic tagline.",
        "Invent a superhero whose only power is mildly inconveniencing villains. Name them.",
        "Type a weather report for the server's current vibe like you're a news anchor.",
        "Explain how to make a sandwich as if you're teaching an alien who has never seen bread.",
        "Write a four-line diss track aimed at your own procrastination.",
        "Describe the nearest object like it's a legendary item with a 0.001% drop rate.",
        "Send one sentence that sounds wise but means absolutely nothing.",
        "Create patch notes for your personality: one buff, one nerf, and one bug.",
        "Give yourself a ridiculous royal title and announce your first law.",
        "Argue for three sentences that a hot dog is either a sandwich or a taco.",
        "Write a dramatic obituary for a snack you just finished—or wish you had.",
        "Speak or type like a sports commentator describing someone making a cup of tea.",
        "Invent a new holiday and explain its weirdest tradition.",
        "Give the group a completely unnecessary life lesson from a potato's perspective.",
        "Make up a fake achievement unlocked for the last thing you did today.",
        "Describe your favourite game badly enough that people have to guess it.",
        "Write a one-star review of gravity as if you've just discovered it.",
        "Create a slogan for the most useless product imaginable.",
        "Give your next message the energy of a final anime villain speech.",
        "Type a sentence without using the letter 'e'. If you fail, defend your failure dramatically.",
        "Invent a ridiculous law for a fictional country where you are the ruler.",
        "Describe your day using only three emojis, then let the chat interpret them.",
        "Write a fake breaking-news headline about something completely ordinary.",
        "Give the challenger a friendly, over-the-top award with a very specific title."
    ],
    "teen": [
        "Write a formal apology to the server for your most recent imaginary crime against the vibes.",
        "Do a 15-second villain monologue about someone stealing your fries. Voice note optional.",
        "Pitch your favourite game or anime like you're trying to save a failing TV network.",
        "Write a four-line rap about your biggest gaming L.",
        "Give your current life situation a difficulty rating, boss name, and loot drop.",
        "Create a fake dating-show intro for yourself without naming or tagging anyone.",
        "Describe your typing style as a character class in an RPG, with stats and weaknesses.",
        "Give a dramatic acceptance speech for an award nobody should ever receive.",
        "Invent a fake rumour about yourself that is obviously ridiculous, then debunk it.",
        "Make a top-three list of the most suspicious things a person can say in a group chat.",
        "Write a patch note that would fix your most annoying habit.",
        "Defend your most controversial game or anime opinion in exactly three sentences.",
        "Turn the last message in the chat into a dramatic movie trailer tagline.",
        "Type a breakup letter to an app, snack, or game you couldn't live without.",
        "Give a 10-second motivational speech to someone about to lose a 1v1.",
        "Describe your aura as a badly reviewed product: include a title and two reviews.",
        "Create a new server role name for yourself and explain the completely unnecessary perks.",
        "Write a two-line poem about your Wi-Fi connection during the worst possible moment.",
        "Give the group a fake patch note for the human species.",
        "Deliver your best PG pickup line to the chat—or write it like a poet with zero confidence.",
        "Invent a conspiracy theory about why socks disappear in the laundry.",
        "Write a confession from the point of view of your most-used emoji.",
        "Describe how you'd survive a zombie apocalypse using only your actual strongest skill.",
        "Create a tier list with three completely ordinary things, then defend the ranking.",
        "Give yourself a boss-fight intro with a name, theme music, and one ridiculous weakness."
    ],
    "spicy": [
        "Deliver your smoothest PG pickup line to the challenger. Confidence matters more than quality.",
        "Write a brutally honest but kind three-word first impression of your own vibe.",
        "Give a dramatic 10-second confession to a snack as if it's the love of your life.",
        "Pitch yourself as the lead in a rom-com in two sentences—make it hilariously overconfident.",
        "Write the most charming compliment you can think of without using the words 'cute', 'hot', or 'beautiful'.",
        "Give your flirting style a product name, slogan, and brutally honest customer review.",
        "Act out or type a scene where you try to look cool and immediately fumble it.",
        "Create a fictional dating profile headline for yourself that is weirdly accurate.",
        "Write a message you'd send to impress your crush, but make it about a very boring object.",
        "Give a 15-second dramatic speech about why you deserve a second chance after fumbling.",
        "Write a green-flag / red-flag list for yourself with one entry in each column.",
        "Deliver a cheesy pickup line in the style of a medieval knight, villain, or news reporter.",
        "Describe your ideal date using only five emojis, then explain the choices.",
        "Give the challenger a sincere compliment with main-character-level dramatic delivery.",
        "Write a two-line confession from the perspective of someone who caught feelings for a Wi-Fi router.",
        "Make a top-three list of qualities that make someone instantly unforgettable.",
        "Act like you're on a dating show and introduce yourself in the most chaotic way possible.",
        "Write a rejection to an imaginary admirer so polite it sounds like a corporate email.",
        "Create a fake movie title about your romantic life and deliver the trailer tagline.",
        "Give your best 'I totally meant to do that' speech after an imaginary social fumble.",
        "Write the most dramatic response possible to receiving a simple 'hey'.",
        "Describe your ideal partner's vibe using only a game class, an emoji, and a song genre.",
        "Invent a flirting tutorial with three steps; at least one step must be terrible advice.",
        "Make a respectful, playful roast of your own flirting skills in two sentences.",
        "End your next message with a ridiculous signature title, like 'Supreme Minister of Rizz'."
    ],
}

FORFEIT_PUNISHMENTS = [
    "🐔 **Certified Chicken:** Write a formal resignation letter from the game, citing 'an unexpected shortage of courage.'",
    "🐔 **Certified Chicken:** Award the challenger 500 imaginary Aura and announce it like a championship result.",
    "🐔 **Certified Chicken:** Give yourself a dramatic defeat title, such as 'The Fallen Legend of This Tuesday.'",
    "🐔 **Certified Chicken:** Write a four-word apology to your own courage.",
    "🐔 **Certified Chicken:** Send a one-line eulogy for the bravery that left your body.",
    "🐔 **Certified Chicken:** Declare the prompt your sworn nemesis and give it a villain name.",
    "🐔 **Certified Chicken:** Write a fake patch note: 'Courage reduced by 99%.' Add one more update.",
    "🐔 **Certified Chicken:** Invent an excuse so dramatic it deserves its own documentary.",
    "🐔 **Certified Chicken:** Give the chat a motivational speech about the importance of knowing your limits.",
    "🐔 **Certified Chicken:** Accept the title 'Mayor of Almost Doing It' until the next round."
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

        rating_badge = {"pg": "🟢 WARM-UP", "teen": "🟡 CHAOS MODE", "spicy": "🔴 UNHINGED MODE"}.get(self.rating, "🟡 CHAOS MODE")

        if self.challenger.id == self.target.id:
            header = (
                f"# 🎭 NEXORA PARTY DECK · SOLO RUN\n"
                f"> 👤 Playing: {self.target.mention} · Tier: **{rating_badge}**\n\n"
                f"Pick your fate. The boring prompts have been banished."
            )
        else:
            header = (
                f"# 🎭 NEXORA PARTY DECK · DUEL MODE\n"
                f"> ⚔️ **{self.challenger.display_name}** challenged **{self.target.display_name}**!\n"
                f"> 👤 Target: {self.target.mention} · Tier: **{rating_badge}**\n\n"
                f"Waiting for {self.target.mention} to make a choice..."
            )

        self.add_section(header, thumbnail_url=str(self.target.display_avatar.url))
        self.add_separator(discord.SeparatorSpacing.small)

        btn_truth = discord.ui.Button(label="Truth", emoji="💬", style=discord.ButtonStyle.primary)
        btn_dare = discord.ui.Button(label="Dare", emoji="⚡", style=discord.ButtonStyle.danger)
        btn_random = discord.ui.Button(label="Spin the Wheel", emoji="🎲", style=discord.ButtonStyle.secondary)

        btn_truth.callback = self._on_choose_truth
        btn_dare.callback = self._on_choose_dare
        btn_random.callback = self._on_choose_random

        self.add_row(btn_truth, btn_dare, btn_random, DismissButton(user_id=self.challenger.id))
        self.add_footer("Funny truths · chaotic dares · two rerolls · zero boring energy")

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

        rating_labels = {"pg": "🟢 WARM-UP", "teen": "🟡 CHAOS MODE", "spicy": "🔴 UNHINGED MODE"}
        r_label = rating_labels.get(self.rating, "🟡 CHAOS MODE")

        if self.challenger.id == self.target.id:
            header = (
                f"# {emoji} {p_type} for @{self.target.name} (Solo)\n"
                f"> 👤 Player: {self.target.mention} · Tier: **{r_label}**\n\n"
                f"### 📋 Your Challenge:\n"
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
        btn_done = discord.ui.Button(label="Completed — EZ", emoji="✅", style=discord.ButtonStyle.success)
        btn_forfeit = discord.ui.Button(label="I’m Cooked", emoji="🐔", style=discord.ButtonStyle.danger)
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

        btn_steal = discord.ui.Button(label="Jump In!", emoji="🙋", style=discord.ButtonStyle.secondary)
        btn_steal.callback = self._on_steal_turn

        self.add_row(btn_another, btn_switch, btn_steal, DismissButton(user_id=self.challenger.id))
        self.add_footer("Make it legendary · Reroll if needed · Keep the chaos friendly.")

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
            f"• **Reward:** +1000 imaginary Aura ✨"
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
        description="🎭 Chaos-packed Truth or Dare with wild prompts, duels, and rerolls",
    )
    @app_commands.describe(
        target="Member to challenge (leave empty to play yourself)",
        rating="Content tier: pg, teen, or spicy (default: teen)",
    )
    @app_commands.choices(
        rating=[
            app_commands.Choice(name="🟢 Warm-up (Funny & Friendly)", value="pg"),
            app_commands.Choice(name="🟡 Chaos Mode (Party & Confessions)", value="teen"),
            app_commands.Choice(name="🔴 Unhinged Mode (Bold & Flirty)", value="spicy"),
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
        description="💬 Get a genuinely chaotic Truth prompt or challenge a friend",
    )
    @app_commands.describe(
        target="Member to challenge (leave empty to play yourself)",
        rating="Content tier: pg, teen, or spicy (default: teen)",
    )
    @app_commands.choices(
        rating=[
            app_commands.Choice(name="🟢 Warm-up (Funny & Friendly)", value="pg"),
            app_commands.Choice(name="🟡 Chaos Mode (Party & Confessions)", value="teen"),
            app_commands.Choice(name="🔴 Unhinged Mode (Bold Truths)", value="spicy"),
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
        description="⚡ Roll a wild Dare or challenge a friend to do it",
    )
    @app_commands.describe(
        target="Member to challenge (leave empty to play yourself)",
        rating="Content tier: pg, teen, or spicy (default: teen)",
    )
    @app_commands.choices(
        rating=[
            app_commands.Choice(name="🟢 Warm-up (Funny & Friendly)", value="pg"),
            app_commands.Choice(name="🟡 Chaos Mode (Party & Confessions)", value="teen"),
            app_commands.Choice(name="🔴 Unhinged Mode (Bold & Flirty)", value="spicy"),
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

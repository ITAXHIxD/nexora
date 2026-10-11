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
        "What's a belief you held for years that you now think was completely wrong? What changed your mind?",
        "What's a mistake you keep repeating even though you know exactly how it ends?",
        "What's something you're proud of that you rarely give yourself credit for?",
        "When was the last time you judged someone too quickly and later realised you were wrong?",
        "What's a promise you made to yourself that you keep postponing?",
        "What's a fear that has stopped you from trying something you genuinely wanted to do?",
        "What's one habit of yours that would annoy you if a friend did the exact same thing?",
        "What's the most useful criticism you've ever received, even if you hated hearing it?",
        "What's a moment you acted confident while secretly having no idea what you were doing?",
        "What's something you pretend not to care about, even though it matters to you?",
        "What's one thing you envy in others, and what do you think that envy is telling you?",
        "What's a time you took the easy way out and later wished you'd handled it differently?",
        "What's a small lie you tell yourself to avoid doing something difficult?",
        "What's a strength you have that becomes a weakness when you overuse it?",
        "What's something you used to make fun of but now understand or enjoy?",
        "What's the hardest apology you've had to make, or one you still owe? No names needed.",
        "What's a time you followed the crowd even though your instincts said not to?",
        "What's a personal rule you have that you often fail to follow yourself?",
        "What's one uncomfortable conversation you've been avoiding, and what's stopping you?",
        "What's the most embarrassing thing you've done while trying to impress someone?",
        "What's an assumption people make about you that is almost the opposite of the truth?",
        "What's a time you got defensive because someone was right about you?",
        "What's something you wish people would ask you about instead of assuming they already know?",
        "What's a decision you made to please someone else that you wouldn't repeat today?",
        "What's the most meaningful compliment you've received, and why did it stick?",
        "What's something you need to stop blaming on bad luck or bad timing?",
        "What's a friendship lesson you learned the hard way?",
        "What's something you would change about how you handled a situation from the past year?",
        "What do you do when you feel insecure that other people might notice?",
        "If your closest friend described your biggest blind spot, what would they probably say?"
    ],
    "teen": [
        "What's the biggest gap between the person you claim to be and how you act when nobody is watching?",
        "What's a truth about yourself you know but keep trying to negotiate with?",
        "When have you let pride ruin something that could have been fixed with one honest conversation?",
        "What's the most unfair thing you've done to someone while convincing yourself you were justified?",
        "What's a red flag in yourself that you notice but haven't properly worked on?",
        "Have you ever kept someone around mainly because you liked the attention? What made you realise it?",
        "What's the most jealous you've felt over something you pretended not to care about?",
        "What's a message you wish you could unsend—not the private details, just what made you regret it?",
        "What's a time you acted unbothered when you were genuinely hurt?",
        "What's something you criticised in another person that you later caught yourself doing?",
        "Have you ever lost respect for someone because they exposed a weakness you share?",
        "What's the most cowardly excuse you've used to avoid being honest with someone?",
        "What's a friendship you damaged by assuming the other person should just know what you needed?",
        "What's the hardest feedback you'd expect from someone who knows you very well?",
        "What's something you hide behind humour because admitting it seriously feels too vulnerable?",
        "Have you ever wanted someone to fail because you felt threatened by their success?",
        "What's a time you mistook attention for genuine care or affection?",
        "What's one boundary you expect others to respect but struggle to respect yourself?",
        "What's the most selfish reason you've ended or maintained a friendship?",
        "What's an opinion you hold mostly because your friend group holds it?",
        "What's a time you knew you owed someone an explanation but chose silence instead?",
        "What's something you would hate to have accurately pointed out about your behaviour?",
        "Have you ever apologised just to end an argument without actually accepting responsibility?",
        "What's something about your online personality that differs from how you are face-to-face?",
        "What do you secretly compete with your friends about, even if nobody agreed to compete?",
        "What's a pattern in your relationships or friendships that you're afraid might be your fault?",
        "What's a time you were the problem in a situation you originally told as someone else's fault?",
        "If someone you respect read your last week of behaviour like a report card, what would get the lowest grade?",
        "What's something you keep waiting to feel ready for instead of simply starting?",
        "What's one honest sentence about yourself that would be difficult to say out loud in this call?"
    ],
    "spicy": [
        "What's the biggest romantic signal you've ignored because accepting it would have meant taking a risk?",
        "Have you ever enjoyed being wanted by someone you knew you didn't want back? What did you do about it?",
        "What's your most uncomfortable dating pattern—the thing you repeat even though you know better?",
        "What's the boldest thing you wanted to say to a crush but chose not to, and why?",
        "What's the difference between the person you say is your type and the person you actually fall for?",
        "Have you ever mistaken the excitement of uncertainty for genuine compatibility?",
        "What's a romantic red flag you've excused because the chemistry was strong?",
        "What's the most vulnerable thing you wish you could say without worrying how it would be received?",
        "Have you ever kept a backup option instead of being honest about what you wanted?",
        "What's something you want in a relationship that you would find difficult to give in return?",
        "What's a time you played it cool and accidentally made someone think you weren't interested?",
        "What's the most honest reason a past crush or relationship didn't work out—without naming anyone?",
        "What's a compliment you desperately want from the right person but would struggle to ask for?",
        "Have you ever liked the idea of someone more than the actual person? How did you notice?",
        "What's your biggest insecurity when you genuinely care about someone's opinion of you?",
        "What's a boundary you would never compromise on, even for someone you really liked?",
        "What's a time attraction made you ignore evidence that someone wasn't right for you?",
        "What's the difference between your standards and your defence mechanisms?",
        "What's a feeling you've tried to disguise as sarcasm, indifference, or a joke?",
        "What's the hardest truth about your own behaviour when you catch feelings?",
        "What's a romantic mistake you would warn your younger self not to repeat?",
        "Have you ever wanted someone to make the first move while giving them absolutely no useful signal?",
        "What's something you find attractive that reveals more about your values than your physical type?",
        "What's a truth about your love life that your friends would recognise instantly?",
        "What's the scariest part of being genuinely known by someone you're attracted to?",
        "Have you ever confused chasing someone with actually wanting a relationship with them?",
        "What's the most meaningful way someone could reject you while still treating you with respect?",
        "What's one thing you would need to change about yourself to be a healthier partner?",
        "What's a romantic boundary you learned only after letting someone cross it?",
        "Finish honestly: 'I act like I don't care about ___, but actually ___.'"
    ],
}

DARES = {
    "pg": [
        "Tell a 60-second story about your most embarrassing harmless mistake. It must have a beginning, a turning point, and a proper ending.",
        "Defend an unpopular opinion for 45 seconds without saying 'because I like it' or repeating the same argument.",
        "Give yourself a brutally accurate 30-second documentary introduction: strengths, flaws, and the plot twist.",
        "Improvise a one-minute courtroom defence of your worst habit. The challenger is the judge and gets one question.",
        "Recreate a memorable scene from a film or game using only your voice and facial expressions, then let the group guess it.",
        "Explain a game, anime, or hobby you love to a complete beginner in 60 seconds without using its obvious keywords.",
        "Give a 45-second motivational speech to your past self about a mistake you actually learned from.",
        "Create a three-round quiz about yourself: two true facts and one lie. The challenger must identify the lie and ask a follow-up.",
        "Tell a true story where you were wrong, including the exact moment you realised it.",
        "Pitch your life as a series in 45 seconds: title, genre, main flaw, season-one conflict, and cliffhanger.",
        "Make a convincing argument for a ridiculous position for 45 seconds, then switch sides and argue against yourself for 30 seconds.",
        "Give a 60-second review of a food, game, or film you know well, including one strength, one flaw, and a final verdict.",
        "Invent a fictional character based on your worst habit and act out a 30-second scene where that habit ruins everything.",
        "Speak for 45 seconds about a topic chosen by the challenger without using the words 'thing', 'stuff', or 'whatever'.",
        "Share three specific lessons you learned the hard way. At least one must be about your own behaviour.",
        "Write and perform a four-line rap about a real recent fail. It has to rhyme at least twice.",
        "Describe your most-used app as if it were an unhealthy relationship, with three pieces of evidence.",
        "Give the challenger a 45-second roast of your own habits—specific enough to be funny, not cruel.",
        "Make a three-step tutorial for a skill you genuinely have. The challenger chooses one step and asks you to explain it in detail.",
        "Tell a suspense story in 60 seconds using three random words chosen by the challenger.",
        "Present a serious 45-second business pitch for the most useless product the challenger can invent.",
        "Without naming names, recount a moment you misunderstood someone and explain what you should have done differently.",
        "Do a one-minute interview with yourself: answer five questions as both the interviewer and the guest, with distinct voices.",
        "Give a 45-second acceptance speech for an award called 'Most Likely to Make Things Harder Than Necessary' and include two real examples.",
        "Let the challenger choose a harmless topic, then speak about it for 30 seconds without pausing longer than three seconds."
    ],
    "teen": [
        "Tell the group about a real time you fumbled badly. No vague summary: explain what happened, your part in it, and what you'd do differently.",
        "Make a 60-second argument defending a belief you hold, then give the strongest argument against your own position.",
        "Give a two-minute 'case against me' presentation: three habits that make you difficult to deal with, each backed by an example.",
        "Voice-note a dramatic retelling of your most awkward social moment as if it were the climax of a thriller.",
        "The challenger picks a topic you disagree on. Steelman their side for 60 seconds before explaining your own.",
        "Tell a story about a time you were jealous, insecure, or wrong without blaming the other person for your reaction.",
        "Give a 90-second apology to an imaginary person you let down. It must include what you did, the impact, and what you'd change—no excuses.",
        "Do a three-minute speed round: answer five challenging questions from the group, with no answer longer than 20 seconds and no dodging with 'I don't know'. You may pass one.",
        "Perform a 60-second job interview for the role of 'Most Chaotic Person in This Server'. Use real examples and answer one tough question.",
        "The challenger gives you three random words. Build a coherent, dramatic two-minute story that includes all three.",
        "Defend your most controversial game, anime, or music opinion for 60 seconds while the challenger cross-examines you with two questions.",
        "Tell the story of a time you changed your mind about a person or belief. Explain what evidence changed it.",
        "Give a 90-second TED Talk called 'How I Accidentally Become My Own Worst Enemy' with three concrete examples.",
        "Act out a one-minute argument between your ideal self and your actual self about a habit you need to change.",
        "Choose one harmless assumption people make about you and explain what they get wrong—with a real example.",
        "Deliver a one-minute roast of your own online persona that is specific, clever, and not just self-insults.",
        "Do a 60-second improvised debate against the challenger. You must respond to their actual argument instead of repeating your point.",
        "Tell a story where you were clearly at fault, and finish with the sentence: 'The part I was responsible for was…'",
        "Let the group choose one of your non-sensitive opinions. Explain its origin, the best argument against it, and whether you're still convinced.",
        "Record a 45-second voice note acting as three versions of yourself: confident, insecure, and brutally honest. Make each reveal a different perspective.",
        "Give a two-minute pitch for why someone should be your friend, including one real strength, one genuine weakness, and one thing you're actively improving.",
        "Explain a recent decision you made using only facts for 30 seconds, then explain the emotion behind it for another 30 seconds.",
        "The challenger asks one follow-up to each answer: name something you avoid, a pattern you repeat, and a lesson you haven't fully learned.",
        "Write a six-line diss track about your own worst habit and perform it with full confidence. No generic 'I'm lazy' answers.",
        "Speak for 90 seconds about something you care about while the challenger tries to distract you with harmless interruptions; keep your argument coherent."
    ],
    "spicy": [
        "Give a 60-second, no-joke answer to: what do you actually want romantically that you rarely admit because it feels risky?",
        "Deliver a confident 45-second flirt scene with the challenger as a fictional rom-com character. Keep it playful; either person can decline.",
        "Explain your biggest dating red flag as if you're giving a warning at a product launch, then state one concrete way you could improve it.",
        "Give a 90-second 'green flag pitch' about yourself: three real qualities, one weakness, and proof for each claim.",
        "Improvise a first-date conversation with the challenger for one minute. The challenger can throw in an awkward curveball at any time.",
        "Tell a romantic almost-fumble story without naming anyone, then explain what you'd do differently now.",
        "Deliver a smooth pickup line, then immediately explain why it might fail. You must commit to both performances.",
        "Answer three bold but respectful questions from the challenger about your romantic preferences. You may pass one question.",
        "Act out a 60-second breakup scene in which you must be honest without being cruel; the challenger chooses the scenario.",
        "Give a two-minute defence of your relationship standards, including one standard you may need to reconsider and why.",
        "Write a heartfelt message you might send to someone you care about, but do not send it. Read it aloud only if comfortable; otherwise paraphrase it.",
        "Do a one-minute live dating-show introduction. Include your best quality, your most obvious flaw, and the kind of person you genuinely connect with.",
        "Explain the difference between your confident flirting persona and how you actually feel when you like someone.",
        "The challenger gives you a cheesy pickup line. Improve it twice: first make it smooth, then make it intentionally hilariously terrible.",
        "Deliver a sincere compliment to another willing player, then explain specifically what you noticed. No appearance-only or backhanded compliments.",
        "Give a 90-second speech called 'Why I Would Be a Great Partner—and Where I Could Be Difficult'. You must include concrete examples.",
        "Roleplay a respectful rejection and then a respectful response to rejection. Make both characters honest, calm, and believable.",
        "Describe your ideal date in detail, then identify one part that reflects your personality and one part that might be unrealistic.",
        "Make a one-minute case for why you should be trusted with someone's feelings. Include one behaviour you need to be held accountable for.",
        "Answer this without hiding behind a joke: what's harder for you, making the first move, being emotionally honest, or accepting rejection—and why?",
        "Act out a 60-second scene where you meet your fictional crush, say the wrong thing, recover, and end the conversation with confidence.",
        "Give the challenger three respectful, specific compliments: one about personality, one about a skill, and one about their energy. No forced flirting.",
        "Pitch your romantic life as a two-minute series trailer, including the flaw that keeps causing the plot and what the next season must change.",
        "The challenger creates a harmless awkward social scenario. Roleplay your response in real time, then explain what you were trying to achieve.",
        "Finish these three sentences honestly: 'I feel wanted when…', 'I tend to pull away when…', and 'I need to get better at…'. Share only what you're comfortable sharing."
    ],
}

FORFEIT_PUNISHMENTS = [
    "🐔 **Certified Chicken:** Give a 30-second concession speech explaining why the prompt defeated you. Make it sound like a defeated champion.",
    "🐔 **Certified Chicken:** Accept the title 'Mayor of Almost Doing It' and give a 20-second campaign speech defending your new office.",
    "🐔 **Certified Chicken:** Deliver a mock press conference: two questions from the challenger, answered as dramatically as possible.",
    "🐔 **Certified Chicken:** Write a four-line eulogy for your courage, then read it with absolute sincerity.",
    "🐔 **Certified Chicken:** Give the challenger 500 imaginary Aura points and explain why they clearly outclassed you.",
    "🐔 **Certified Chicken:** Explain the prompt's difficulty like a game reviewer, including a score out of ten and a patch suggestion.",
    "🐔 **Certified Chicken:** Improvise a 30-second villain origin story explaining how this prompt broke you.",
    "🐔 **Certified Chicken:** Give a formal resignation speech from the game, with one real reason and one completely ridiculous reason.",
    "🐔 **Certified Chicken:** Defend your forfeit in a 45-second courtroom statement. The challenger gets one rebuttal.",
    "🐔 **Certified Chicken:** Announce a comeback plan with three specific promises for the next round."
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
        self.add_footer("Give a specific answer · protect other people’s privacy · reroll if a prompt crosses a line")

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
                f"### ⚡ Your Challenge:\n"
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
        self.add_footer("Make it specific · Respect boundaries · Reroll if a prompt crosses a line.")

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

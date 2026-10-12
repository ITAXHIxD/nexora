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

from cogs.fun.tod_prompts import EXTRA_TRUTHS, EXTRA_DARES

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
        "What's the most embarrassing thing you've confidently claimed to understand but absolutely didn't?",
        "What's a harmless lie you tell so often that you've almost started believing it?",
        "What's the weirdest thing you've spent money on and then tried to justify?",
        "What's your most irrational deal-breaker in a friend, roommate, or date?",
        "What's a first impression people get about you that is completely wrong?",
        "What's the pettiest reason you've ever silently judged somebody?",
        "What's the most effort you've put into avoiding a task that would've taken five minutes?",
        "What's a habit you have that would look ridiculous if someone filmed you doing it?",
        "What's the worst attempt you've made to look cool in front of someone?",
        "What's an opinion you defend like a lawyer even though it genuinely doesn't matter?",
        "What's a basic adult task you still secretly have to look up how to do?",
        "What's the most embarrassing thing in your recent search history that you can safely admit?",
        "What's something you pretend to dislike because you don't want people to know you enjoy it?",
        "What's the most dramatic reaction you've had to a very minor inconvenience?",
        "What's your most useless talent, and when did you last show it off?",
        "What's a purchase you regret but would probably make again?",
        "What's the funniest excuse you've used to get out of a plan?",
        "What's something you were terrible at but used to insist you were good at?",
        "What's one social rule you only learned after breaking it?",
        "What's the most ridiculous thing you've done because you were hungry or tired?",
        "What's a song you know embarrassingly well and how did you learn every word?",
        "What's a trend you mocked before secretly joining it?",
        "What's the strangest thing you do when you're completely alone?",
        "What's a small luxury you would defend even if everyone called it a waste of money?",
        "What's the most chaotic thing you've done because you were bored?",
        "What's something you thought was normal until a friend pointed out it was weird?",
        "What's the worst advice you've given with complete confidence?",
        "What's one thing your friends could imitate about you perfectly?",
        "If your life had a disclaimer, what would the warning say?",
        "What's the funniest misunderstanding you've had with someone you were trying to impress?"
    ],
    "teen": [
        "What's something you've done for attention that you'd deny if your friends asked directly?",
        "When did you last act unbothered while secretly caring a lot?",
        "What's the most selfish reason you've kept a friendship going?",
        "What's a red flag in yourself you keep excusing instead of fixing?",
        "What's a message you typed, deleted, rewrote, and still regret sending?",
        "What's the biggest gap between how confident you look and how confident you feel?",
        "Have you ever kept someone interested mainly because you liked the attention? What happened?",
        "When did pride stop you from apologising even though you knew you were wrong?",
        "What's an opinion you only hold because your friends would judge you for changing it?",
        "What's a situation you originally blamed on someone else but later realised you helped create?",
        "What's something you secretly compete with your friends about?",
        "What's the most jealous you've been while pretending you didn't care?",
        "What's a pattern in your friendships that might partly be your fault?",
        "What's a compliment you act like you don't need but would genuinely love to hear?",
        "What's a boundary you expect others to respect but struggle to respect yourself?",
        "What's something you hide behind humour because sincerity feels too exposing?",
        "What's the weakest excuse you've used to avoid telling someone the truth?",
        "Have you ever confused being wanted with being valued? What made you realise it?",
        "What's one thing about your online personality that doesn't match the real you?",
        "What's the harshest criticism from a friend that might actually be fair?",
        "What's something you've blamed on bad timing that was really fear?",
        "Have you ever apologised just to end an argument without accepting responsibility?",
        "What behaviour in other people annoys you because you recognise it in yourself?",
        "What's something you've outgrown but keep returning to when you feel lonely or bored?",
        "What's a friendship lesson you learned the hard way?",
        "What do you do when you feel replaceable, even if you act completely fine?",
        "What's a decision you made to impress somebody that you wouldn't make again?",
        "What truth would your closest friend tell you if they knew you wouldn't get defensive?",
        "What's something you secretly want to be praised for?",
        "Have you ever pulled away from someone just to see whether they'd chase you?",
        "What's a misunderstanding you allowed to grow because explaining yourself felt uncomfortable?",
        "What's one change you know would improve your life but keep postponing?",
        "How do you act when you're angry, and what part of that behaviour do you dislike?",
        "What do you fear people would think if they saw your biggest insecurity?",
        "What's a tough conversation you know you need to have, even if you keep the details private?"
    ],
    "spicy": [
        "Who was the last person you caught feelings for, and what was the first sign you tried to ignore?",
        "Have you ever flirted for attention while knowing you weren't genuinely interested?",
        "What's the boldest message you've wanted to send to a crush but couldn't make yourself send?",
        "What's your biggest romantic red flag that chemistry makes you overlook?",
        "Have you ever kept a backup option because being alone felt worse than being dishonest?",
        "What's something you find attractive that you rarely admit out loud?",
        "What's the closest you've come to confessing feelings and then backed out?",
        "Have you ever mistaken mixed signals for a challenge instead of a warning?",
        "What's a romantic boundary you learned only after letting someone cross it?",
        "What's the most embarrassing thing you've done to seem desirable to someone?",
        "What's something you want from a relationship that you'd struggle to give in return?",
        "Have you ever enjoyed being someone's favourite person while knowing you couldn't return their feelings?",
        "What's your biggest insecurity when you genuinely like someone?",
        "What's the most obvious hint you've dropped and then pretended was a joke?",
        "What's a type you swear is your type but repeatedly turns out to be bad for you?",
        "What's a romantic mistake you'd warn your younger self not to repeat?",
        "Have you ever gone back to someone you knew wasn't right for you? What pulled you back?",
        "What's something a past crush or partner taught you about yourself, without naming them?",
        "When you like someone, do you get closer, act distant, or become a comedian—and what's your excuse?",
        "What's something you'd find hard to forgive in a relationship even if you still loved the person?",
        "Have you ever tried to make someone jealous on purpose? What reaction were you hoping for?",
        "What's the most intense crush you've had on someone you barely knew?",
        "What compliment from the right person would completely destroy your composure?",
        "What's harder for you: making the first move, being emotionally honest, or handling rejection?",
        "Have you ever liked someone more because they were difficult to get?",
        "What's the romantic gesture you secretly wish someone would make for you?",
        "What's a dating standard you claim to have but have broken before?",
        "What's a feeling you've disguised as sarcasm, indifference, or a joke?",
        "What's the most awkward almost-confession you've experienced?",
        "Have you ever stayed in a talking stage longer than you wanted because ending it felt scary?",
        "What could a partner do that would make you feel genuinely chosen?",
        "What's something about your behaviour that could make dating you difficult?",
        "If your last crush reviewed your flirting honestly, what would they say?",
        "When did you know what you wanted romantically but were too proud to say it?",
        "Finish honestly: 'I act like I don't care about ___, but actually ___.'"
    ]
}

DARES = {
    "pg": [
        "Send a friend a voice note narrating what you're doing like a wildlife documentary. Stay in character for 20 seconds.",
        "DM a friend: 'Important question: would I survive as your lawyer?' Defend your answer in three messages.",
        "Let the challenger choose a harmless topic and deliver a 45-second passionate argument for it.",
        "Voice-note a dramatic apology to a friend for the imaginary crime of stealing their fries. Reveal the dare right after.",
        "Ask a friend to describe your vibe in exactly three words. Give a 30-second rebuttal to their answer.",
        "Give a 60-second TED Talk defending your most controversial food opinion. The challenger gets one cross-examination question.",
        "Send a friend your most confidently terrible pickup line and ask for a score out of ten.",
        "Tell the group a true story about a time you fumbled, including what you did wrong and what you'd do differently.",
        "Perform a 45-second villain monologue about someone taking the last snack.",
        "Ask a friend to choose a random word, then improvise a 60-second story that includes it three times.",
        "DM a friend a ridiculous question and argue the opposite side of their answer for 30 seconds.",
        "Create a three-question quiz about yourself. The challenger must answer without hints.",
        "Give a 45-second courtroom defence of your worst habit. The challenger is the judge.",
        "Record a movie-trailer narration about your friendship with someone you know and send it to them.",
        "Give yourself a brutally accurate 30-second documentary introduction: strengths, flaws, and plot twist.",
        "Explain a hobby you love to a beginner in 60 seconds without using its obvious keywords.",
        "Write a four-line rap about a real recent fail and perform it with full confidence.",
        "Make a convincing argument for a ridiculous position for 45 seconds, then switch sides and argue against yourself.",
        "Deliver a 60-second acceptance speech for 'Most Likely to Make Things Harder Than Necessary' with two real examples.",
        "Ask a friend to rate your most chaotic habit from one to ten. Accept one follow-up question.",
        "Let the challenger pick three random words and build a suspense story around all three in one minute.",
        "Do a one-minute interview with yourself, switching between interviewer and guest with different voices.",
        "Describe your most-used app as if it were a toxic relationship, with three pieces of evidence.",
        "Give the challenger a 45-second roast of your own habits. Include specific examples, not generic insults.",
        "Speak for 45 seconds about a topic chosen by the challenger without saying 'thing', 'stuff', or 'whatever'.",
        "Give a 60-second review of a food, game, or film, including one strength, one flaw, and a final verdict.",
        "Pitch your life as a streaming series: title, genre, main flaw, season finale, and cliffhanger.",
        "Send a friend a voice note singing a dramatic version of 'Happy Birthday' even if it isn't their birthday.",
        "Invent a useless product. Pitch it for 45 seconds like your rent depends on the sale.",
        "For the next five messages, end every sentence with a ridiculous formal title you invent."
    ],
    "teen": [
        "DM a friend: 'I need your professional opinion' and ask them to settle a ridiculous debate. Defend the losing side for 30 seconds.",
        "Send a trusted friend a voice note using your most overconfident motivational-speaker voice for 20 seconds.",
        "Tell the group about a real time you fumbled badly: what happened, your part in it, and what you'd do differently.",
        "Give a two-minute 'case against me' presentation: three habits that make you difficult to deal with, each backed by an example.",
        "Ask a friend to rate your most chaotic quality from one to ten. Respond to their rating without getting defensive.",
        "Give a 90-second apology to an imaginary person you let down. Include what you did, the impact, and what you'd change—no excuses.",
        "Perform a one-minute job interview for the role of 'Most Chaotic Person in This Server'. Use real examples and answer one tough question.",
        "The challenger picks a topic you disagree on. Steelman their side for 60 seconds before explaining your own.",
        "Send a friend a dramatically serious confession about a harmless opinion you hold, then defend it in a voice note.",
        "Do a three-minute speed round: answer five challenging questions from the group, with no answer longer than 20 seconds. You may pass one.",
        "Voice-note a dramatic retelling of your most awkward social moment as if it were a thriller finale.",
        "Give a 90-second TED Talk called 'How I Accidentally Become My Own Worst Enemy' with three concrete examples.",
        "Let the challenger choose one harmless opinion. Explain its origin, the strongest argument against it, and whether you're still convinced.",
        "Send someone you already talk to a genuine, specific compliment you've never said out loud before. No pressure for a reply.",
        "Record a 45-second voice note acting as three versions of yourself: confident, insecure, and brutally honest.",
        "Do a 60-second improvised debate against the challenger. Answer their actual argument instead of repeating your point.",
        "Write a six-line diss track about your own worst habit and perform it. Generic 'I'm lazy' answers don't count.",
        "Ask a friend: 'Be brutally honest, what's my most predictable habit?' React to their answer with a 30-second defence.",
        "Explain a recent decision using only facts for 30 seconds, then explain the emotion behind it for another 30 seconds.",
        "Send a friend a 15-second movie-trailer narration about your friendship. You must own the cringe.",
        "Roleplay a one-minute argument between your ideal self and your actual self about a habit you need to change.",
        "Defend your most controversial game, anime, or music opinion while the challenger cross-examines you with two questions.",
        "Pitch why someone should be your friend in two minutes: one strength, one genuine weakness, and one thing you're improving.",
        "Ask a trusted friend what first impression you gave them. Guess their answer before they tell you.",
        "Give a 60-second roast of your online persona that is specific, clever, and not just self-insults.",
        "Tell a story where you were clearly at fault and finish with: 'The part I was responsible for was…'",
        "Send a friend a ridiculous pickup line and ask them to grade the delivery. Improve it based on their feedback.",
        "Speak for 90 seconds about something you genuinely care about while the challenger tries harmless distractions.",
        "Create a fake award for yourself based on a real weakness and deliver a 45-second acceptance speech.",
        "Answer three follow-up questions about something you avoid, a pattern you repeat, and a lesson you haven't learned.",
        "DM a friend a fake corporate memo promoting them to Chief Executive of Chaos, complete with three absurd responsibilities.",
        "Call or voice-message a willing friend to settle a real, harmless disagreement. Accept their ruling for the rest of the game.",
        "Ask a friend which of your habits would make the funniest reality-show storyline, then pitch the first episode in 45 seconds.",
        "Send a friend a 15-second voice note selling the worst possible holiday destination like a luxury travel host.",
        "Let the challenger choose a common opinion. Record a 60-second voice note defending the opposite view like your reputation depends on it."
    ],
    "spicy": [
        "If you're comfortable, DM someone you genuinely like a low-pressure opener or honest compliment. No fake emergency, and accept any response gracefully.",
        "Send a trusted friend your best clean pickup line and ask them to grade it. Rewrite it based on their feedback.",
        "Give a 60-second, no-joke answer to what you actually want romantically but rarely admit because it feels risky.",
        "Deliver a confident 45-second flirt scene with the challenger as a fictional rom-com character. Either person can decline.",
        "Ask a friend: 'What's my biggest green flag and red flag?' Respond honestly instead of arguing every point.",
        "Give a 90-second green-flag pitch about yourself: three real qualities, one weakness, and proof for each claim.",
        "Improvise a first-date conversation with the challenger for one minute. They can throw in an awkward curveball.",
        "Tell a romantic almost-fumble story without naming anyone, then explain what you'd do differently now.",
        "Deliver your smoothest pickup line, then immediately explain why it might fail. Commit to both performances.",
        "Answer three bold but respectful questions about your romantic preferences. You may pass one.",
        "Act out a 60-second breakup scene in which you must be honest without being cruel. The challenger chooses the scenario.",
        "Give a two-minute defence of your relationship standards, including one standard you may need to reconsider and why.",
        "Write a heartfelt message you might send to someone you care about. You choose whether to send it, read it aloud, or keep it private.",
        "Do a one-minute dating-show introduction: your best quality, your most obvious flaw, and the kind of person you connect with.",
        "Explain the difference between your confident flirting persona and how you actually feel when you like someone.",
        "DM a willing friend your most confidently terrible pickup line and ask for a rating. Don't pressure them to reply.",
        "Give a sincere, specific compliment to another willing player, then explain what you noticed. No backhanded compliments.",
        "Give a 90-second speech called 'Why I'd Be a Great Partner—and Where I'd Be Difficult', with concrete examples.",
        "Roleplay a respectful rejection and a respectful response to rejection. Make both characters honest, calm, and believable.",
        "Describe your ideal date in detail, then identify one part that reflects your personality and one part that may be unrealistic.",
        "Make a one-minute case for why you should be trusted with someone's feelings. Include one behaviour you need to improve.",
        "Answer honestly: what's harder for you, making the first move, being emotionally honest, or accepting rejection—and why?",
        "Act out a 60-second scene where you meet your fictional crush, say the wrong thing, recover, and end confidently.",
        "Give the challenger three respectful, specific compliments: one about personality, one about a skill, and one about their energy.",
        "Pitch your romantic life as a two-minute series trailer, including the flaw that keeps causing the plot and what must change.",
        "Ask a trusted friend which fictional character they'd cast as your romantic rival. Defend your place in the love triangle.",
        "If it feels appropriate, invite someone you know to a casual hangout with a clear, low-pressure message. Accept any answer gracefully.",
        "Send a friend a voice note with a 15-second dramatic confession of a harmless crush on a fictional character. Maximum theatre.",
        "Answer without hiding behind a joke: what's harder for you, admitting you care or admitting you were wrong?",
        "Finish honestly: 'I feel wanted when…', 'I pull away when…', and 'I need to improve…'. Share only what you're comfortable sharing.",
        "Let the challenger invent a harmless awkward flirting scenario. Respond in real time without saying 'bro', 'lol', or 'just kidding'.",
        "Give a 60-second explanation of the difference between chemistry, attention, and actual compatibility.",
        "Send someone you appreciate a specific message explaining why you value them. No vague 'you're cool' answers.",
        "Perform a cheesy pickup line like a medieval knight, then repeat it like a smooth, confident adult.",
        "Make a respectful 'case for dating me' pitch, then let the challenger ask one difficult follow-up question."
    ]
}

# Expand all six prompt pools and de-duplicate case-insensitively.
# Keep the existing hand-written prompts first, then append fresh curated prompts.
def _append_unique_prompts(existing: list[str], additions: list[str]) -> list[str]:
    seen = {prompt.strip().casefold() for prompt in existing}
    for prompt in additions:
        clean = prompt.strip()
        key = clean.casefold()
        if clean and key not in seen:
            existing.append(clean)
            seen.add(key)
    return existing


for _tier in ("pg", "teen", "spicy"):
    TRUTHS[_tier] = _append_unique_prompts(TRUTHS[_tier], EXTRA_TRUTHS[_tier])
    DARES[_tier] = _append_unique_prompts(DARES[_tier], EXTRA_DARES[_tier])
    if len(TRUTHS[_tier]) < 100 or len(DARES[_tier]) < 100:
        raise RuntimeError(
            f"Truth or Dare prompt bank for tier {_tier!r} has fewer than 100 "
            f"entries (truths={len(TRUTHS[_tier])}, dares={len(DARES[_tier])})"
        )

FORFEIT_PUNISHMENTS = [
    "🐔 **Certified Chicken:** Give a 30-second concession speech explaining why the prompt defeated you. Make it sound like a defeated champion.",
    "🐔 **Certified Chicken:** Accept the title 'Mayor of Almost Doing It' and give a 20-second campaign speech defending your new office.",
    "🐔 **Certified Chicken:** Hold a mock press conference: answer two questions from the challenger as dramatically as possible.",
    "🐔 **Certified Chicken:** Write a four-line eulogy for your courage, then read it with absolute sincerity.",
    "🐔 **Certified Chicken:** Give the challenger 500 imaginary Aura points and explain why they clearly outclassed you.",
    "🐔 **Certified Chicken:** Explain the prompt's difficulty like a game reviewer, including a score out of ten and a patch suggestion.",
    "🐔 **Certified Chicken:** Improvise a 30-second villain origin story explaining how this prompt broke you.",
    "🐔 **Certified Chicken:** Give a formal resignation speech from the game, with one real reason and one ridiculous reason.",
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
        # Avoid repeating a prompt in this game session until that tier/type pool
        # has been exhausted.
        self.used_prompts: set[tuple[str, str]] = set()

        if initial_prompt_type in ("Truth", "Dare"):
            self._show_prompt(initial_prompt_type)
        else:
            self._build_prompt_picker()

    def _build_prompt_picker(self):
        self.clear_container()

        rating_badge = {"pg": "🟢 WARM-UP · 18+", "teen": "🟡 CHAOS · 18+", "spicy": "🔴 SPICY · 18+"}.get(self.rating, "🟡 CHAOS · 18+")

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
        pool = TRUTHS[self.rating] if p_type == "Truth" else DARES[self.rating]
        if prompt is not None:
            self.current_prompt = prompt
        else:
            unused = [item for item in pool if (p_type, item) not in self.used_prompts]
            if not unused:
                # Only recycle after every prompt in this rating/type has appeared.
                unused = list(pool)
            self.current_prompt = random.choice(unused)
        self.used_prompts.add((p_type, self.current_prompt))

        self.clear_container()
        emoji = "💬" if p_type == "Truth" else "⚡"
        self._color = BRAND_COLOR if p_type == "Truth" else ERROR_COLOR

        rating_labels = {"pg": "🟢 WARM-UP · 18+", "teen": "🟡 CHAOS · 18+", "spicy": "🔴 SPICY · 18+"}
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
        self.add_footer("18+ party deck · Bold, not explicit · Pass or reroll anytime.")

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
        self._show_prompt(self.prompt_type or "Truth")
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
        sent_msg = await send_view(ctx, view)
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
        description="🎭 18+ Truth or Dare: deeper confessions, bold dares, and party duels",
    )
    @app_commands.describe(
        target="Member to challenge (leave empty to play yourself)",
        rating="Content tier: pg, teen, or spicy (default: teen)",
    )
    @app_commands.choices(
        rating=[
            app_commands.Choice(name="🟢 Warm-Up · 18+ (Playful)", value="pg"),
            app_commands.Choice(name="🟡 Chaos · 18+ (Deeper & Bolder)", value="teen"),
            app_commands.Choice(name="🔴 Spicy · 18+ (Bold & Flirty)", value="spicy"),
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
        description="💬 Get a tough 18+ Truth or challenge a friend",
    )
    @app_commands.describe(
        target="Member to challenge (leave empty to play yourself)",
        rating="Content tier: pg, teen, or spicy (default: teen)",
    )
    @app_commands.choices(
        rating=[
            app_commands.Choice(name="🟢 Warm-up (Funny & Friendly)", value="pg"),
            app_commands.Choice(name="🟡 Chaos Mode (Party & Confessions)", value="teen"),
            app_commands.Choice(name="🔴 Spicy · 18+ (Bold Truths)", value="spicy"),
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
        description="⚡ Roll a bold 18+ Dare or challenge a friend",
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

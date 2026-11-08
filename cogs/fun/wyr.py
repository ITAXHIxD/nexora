"""
cogs/fun/wyr.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Interactive Components V2 Would You Rather Engine
Real-time vote progress bars, multiplayer vote tallying, and instant next dilemma.
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
    CYAN_COLOR,
    PURPLE_COLOR,
    SUCCESS_COLOR,
    WARNING_COLOR,
    DismissButton,
    NexoraView,
    progress_bar,
    send_view,
)

logger = logging.getLogger(__name__)

# ── Dilemma Question Bank ──────────────────────────────────────────────────────

DILEMMAS = [
    # ── Superpowers & Supernatural Curses ──────────────────────────────────────
    ("Have the ability to fly at walking speed", "Be able to teleport anywhere, but you arrive completely naked"),
    ("Read everyone's thoughts, but you can never turn it off", "Be completely invisible, but only when nobody is looking at you"),
    ("Have super-speed like The Flash", "Be able to stop time for 30 seconds once a day"),
    ("Always know when someone is lying to you", "Always be able to get away with any lie you tell"),
    ("Have unlimited money but you can never leave your home city", "Travel anywhere in the world for free but with only $20 in your pocket"),
    ("Be able to speak to all animals", "Fluently speak and read every human language instantly"),
    ("Never have to sleep again with zero fatigue", "Never have to eat or drink again and stay at peak fitness"),
    ("Have a rewind button for your life (go back 5 minutes)", "Have a pause button for everyone around you for 10 minutes"),
    ("Control fire with your mind, but you are always shivering cold", "Control ice and water, but you are always uncomfortably hot"),
    ("Be able to see 10 seconds into the future at all times", "Be able to speak to ghosts and spirits whenever you want"),
    ("Be immortal but trapped at your current age forever", "Live a normal lifespan but be completely invulnerable to physical injury"),
    ("Have telekinesis up to 500 lbs", "Have the power of shapeshifting into any living human or animal"),
    ("Instantly master any musical instrument upon touching it", "Instantly master any coding language or software effortlessly"),
    ("Have a clone of yourself that obeys all your commands", "Be able to duplicate any non-living object once per week"),
    ("Breathe underwater and swim at 50 mph", "Survive in the vacuum of space with zero gear"),
    ("Always find a parking spot and green lights everywhere", "Never get sick or catch a cold/virus ever again"),
    ("Be able to erase bad memories from your own brain", "Be able to implant one true dream into someone else's sleep"),
    ("Control probabilities (e.g. increase your luck by 50%)", "Have an absolute photographic memory of everything you ever perceive"),
    ("Talk to your 10-year-old self for 1 hour", "Talk to your 80-year-old self for 1 hour"),
    ("Have x-ray vision that you can toggle", "Have night vision and telescopic zoom vision up to 5 miles"),

    # ── Chaos & Comedy ────────────────────────────────────────────────────────
    ("Fight 100 duck-sized horses", "Fight 1 horse-sized duck"),
    ("Have clown music play loudly every time you enter a room", "Have an audience laugh-track play every time you speak"),
    ("Have hands for feet", "Have feet for hands"),
    ("Always have a piece of popcorn stuck in your teeth", "Always feel like you're about to sneeze but never can"),
    ("Have all your Discord messages sent to your parents", "Have your search history posted publicly on Twitter/X"),
    ("Only be able to speak in rhymes for a year", "Only be able to whisper for the rest of your life"),
    ("Have whatever you eat taste like black licorice", "Have your skin change color based on your mood like a mood ring"),
    ("Wear soaking wet socks for the rest of your life", "Only be allowed to wash your hair with spicy hot sauce"),
    ("Sneeze glitter every time you sneeze", "Bark loudly like a chihuahua whenever someone asks your name"),
    ("Have cartoon sound effects trigger on your physical movements", "Have an ominous dramatic cello sting play whenever you make eye contact"),
    ("Only be able to wear bright neon yellow clothes forever", "Have your hair styled permanently like a 1980s rockstar"),
    ("Always smell like burnt toast to everyone around you", "Always have sticky fingers no matter how many times you wash them"),
    ("Have to narrate your own life aloud in 3rd person", "Have a tiny personal angel and demon arguing on your shoulders 24/7"),
    ("Every door you touch creaks loudly like a haunted house", "Every chair you sit on makes a suspicious fart noise"),
    ("Have your shoes squeak loudly with every single step", "Have your phone ringtone set to an operatic scream at maximum volume"),
    ("Only be able to communicate using Discord emojis for 3 days", "Have your auto-correct change 'yes' to 'I love you passionately' forever"),
    ("Have hiccups every time you try to tell a joke", "Laugh uncontrollably whenever someone delivers terrible news"),
    ("Accidentally reply-all to a 5,000-person company email", "Accidentally send a screenshot of a DM to the person you screenshotted"),
    ("Have hair made of cooked spaghetti that regrows daily", "Have fingernails that glow in the dark like glowsticks"),
    ("Only be able to sleep hanging upside down like a bat", "Only be able to walk in a crab-walk sideways scuttle"),

    # ── Deep Life, Morality & Fate ─────────────────────────────────────────────
    ("Know the exact date and time you will die", "Know the exact cause of your death but not when"),
    ("Live 1,000 years in the past with your current knowledge", "Live 1,000 years in the future with zero memories"),
    ("Be the smartest person in a world full of idiots", "Be the dumbest person in a world of geniuses"),
    ("Lose all your old memories but make amazing new ones", "Keep all your memories but be unable to make new long-term memories"),
    ("Be famous and hated by everyone", "Be completely forgotten by everyone who ever knew you"),
    ("Always be 20 minutes late to everything", "Always be 45 minutes early to everything"),
    ("Have everyone hear your inner thoughts for 1 hour", "Have your worst enemy dictate your career path"),
    ("Give up internet access for 5 years for $1,000,000", "Have free high-speed gigabit internet anywhere forever but stay broke"),
    ("Live in a world with no music but endless books", "Live in a world with no books, movies, or art but endless music"),
    ("Be able to undo your 3 biggest mistakes in life", "Be able to guarantee your next 3 life goals will succeed 100%"),
    ("Live comfortably in peaceful obscurity", "Change the course of human history but die young and penniless"),
    ("Always know the hard truth in every situation", "Live in blissful, happy ignorance of unpleasant realities"),
    ("Have 100 acquaintances who casually like you", "Have 1 ride-or-die best friend who would cross the world for you"),
    ("Possess immense wealth but zero true love", "Possess boundless true love but always live paycheck to paycheck"),
    ("Be able to see the lifespan countdown above everyone's head", "Be able to see everyone's current emotional state as a color aura"),
    ("Spend 10 years in solitary confinement and walk out with $50M", "Live your normal life with an average salary and normal freedom"),
    ("Live in a cabin in the mountains completely off the grid", "Live in a penthouse in the center of Tokyo with infinite noise"),
    ("Know all the mysteries of the universe but be unable to tell anyone", "Remain curious forever with the human thrill of discovery"),
    ("Never be able to lie ever again (pure Jim Carrey Liar Liar)", "Never be able to tell when anyone is telling the truth"),
    ("Sacrifice your own happiness to make everyone around you happy", "Live completely selfishly with guaranteed personal joy"),

    # ── Modern Tech, Discord & Internet Culture ───────────────────────────────
    ("Have 10 million followers on social media but 0 real friends", "Have 50 real close friends and zero social media footprint"),
    ("Your entire camera roll gets leaked to your school or workplace", "Your entire voice search and Google history gets leaked to your family"),
    ("Be trapped in a Discord voice channel with 10 screeching trolls for 24h", "Be banned from using any screen/device for 2 straight weeks"),
    ("Only be able to play one single video game for the rest of your life", "Only be able to watch one TV show series for the rest of your life"),
    ("Have your ping permanently locked at 300ms in every online game", "Have your video graphics permanently locked at 240p 15 FPS"),
    ("Lose your main Discord account with all badges and friends", "Lose your main email account with all saved logins and recovery codes"),
    ("Be forced to use dial-up 56k internet speeds for 1 full year", "Be forced to use a cracked, shattered smartphone screen for 3 years"),
    ("Have a YouTube channel with 5M subscribers that only posts cringey skits", "Have an anonymous blog that is critically acclaimed by 500 scholars"),
    ("Accidentally screen-share your private DMs to an entire 200-person class/meeting", "Accidentally leave your microphone unmuted while venting about your boss/teacher"),
    ("Only be able to listen to Spotify with non-stop unskippable podcast ads", "Only be able to browse YouTube at 0.75x slow-motion playback"),
    ("Wake up tomorrow with the skills of an elite esports champion", "Wake up tomorrow with the voice of an iconic legendary pop star"),
    ("Be forced to text only in voice memos for the rest of your life", "Be forced to video call every single time someone texts you"),
    ("Have your battery never exceed 15% charge for the rest of your life", "Have your headphone jack or Bluetooth disconnect every 7 minutes"),
    ("Always get spoilers for every movie, show, or game 1 week before release", "Never be allowed to watch a movie or show until 2 years after release"),
    ("Have all your Spotify wrapped stats read on live television", "Have your Amazon shopping history displayed on a highway billboard"),
    ("Never be able to delete any message you ever send on Discord", "Never be able to edit any message with a typo"),
    ("Be the moderator of the most toxic 100,000-member Discord server", "Be the lone survivor in an abandoned haunted forum with 0 active users"),
    ("Have unlimited gaming consoles and PCs but only 1 hour per week to play", "Have a potato laptop that barely runs games at 20 FPS but unlimited free time"),
    ("Be forced to use Internet Explorer 6 as your only web browser forever", "Be forced to type on a touch keyboard with no auto-correct or backspace"),
    ("Have a robot assistant that is 99% helpful but roasts you mercilessly 24/7", "Have an assistant that is sweet and polite but breaks 20% of your things"),

    # ── Food, Survival & Absurd Scenarios ──────────────────────────────────────
    ("Eat only pizza for every meal for 1 year", "Eat only tacos for every meal for 1 year"),
    ("Never be allowed to eat sweet or sugary food again", "Never be allowed to eat spicy or savory food again"),
    ("Have unlimited free coffee/tea for life", "Have unlimited free fresh bakery pastries for life"),
    ("Be stranded in the Sahara desert with 2 gallons of water", "Be stranded in the Arctic tundra with a warm parka and matches"),
    ("Survive 30 days in a haunted forest with only a flashlight", "Survive 30 days in an abandoned psychiatric asylum with only a radio"),
    ("Drink a glass of warm mayonnaise", "Drink a glass of melted butter mixed with soy sauce"),
    ("Only be able to eat food that is boiling hot", "Only be able to eat food that is freezing cold and partially frozen"),
    ("Have every meal you eat be 10% too salty", "Have every meal you eat be completely unseasoned and bland forever"),
    ("Fight Mike Tyson in his prime for 1 minute for $5,000,000", "Fight an angry chimpanzee for 15 seconds for $10,000,000"),
    ("Live in a treehouse 100 feet in the air with no elevator", "Live in an underwater dome with sharks circling overhead 24/7"),
    ("Have to hunt and gather all your own food with primitive tools", "Have all your food served as gray nutrient paste with 100% daily vitamins"),
    ("Only be able to drink warm tap water for the rest of your life", "Only be able to sleep on a solid wooden bench with no pillows"),
    ("Wear a winter parka in 100°F (38°C) summer heat for a day", "Wear a swimsuit in 20°F (-7°C) winter snow for 2 hours"),
    ("Be chased by an intelligent snail that kills you if it touches you (you get $10M)", "Live normally with zero money and no snail"),
    ("Have to fight your way through a dungeon crawl every Friday night", "Have to do 10 hours of intense bureaucratic paperwork every Sunday morning"),
    ("Eat a ghost pepper with zero milk or water nearby", "Bite directly into a whole raw yellow onion like an apple"),
    ("Only be able to brush your teeth with barbecue sauce", "Only be able to wash your body with chocolate syrup"),
    ("Be able to teleport food from anywhere directly into your stomach", "Be able to conjure cold drinks in thin air whenever you snap your fingers"),
    ("Live in a cozy zombie apocalypse bunker with infinite snacks and games", "Live in a peaceful cyberpunk dystopian megacity with zero privacy"),
    ("Have your tastebuds swap places with your elbow", "Have your ears swap places with your hands"),
    ("Be trapped in an IKEA store after dark with creepy mannequins moving", "Be trapped in an abandoned amusement park on a roller coaster stuck at the top"),
    ("Win a lifetime supply of fresh pizza", "Win a lifetime supply of first-class plane tickets anywhere on Earth"),
    ("Never experience physical pain ever again", "Never experience emotional heartbreak or grief ever again"),
    ("Have a personal theme song play every time you wake up in the morning", "Have credits roll and a cool soundtrack play every time you fall asleep"),
    ("Know the answer to every question on every test you will ever take", "Know what every person you meet truly thought of you during your first meeting"),
]


class WYRView(NexoraView):
    """Components V2 Would You Rather Interactive Poll View."""

    def __init__(self, bot: commands.Bot, requester: discord.abc.User, timeout: float = 300.0):
        super().__init__(bot=bot, color=BRAND_COLOR, timeout=timeout)
        self.requester = requester
        self.opt_a = ""
        self.opt_b = ""
        self.votes_a: set[int] = set()
        self.votes_b: set[int] = set()
        self.seen_indices: set[int] = set()
        self._pick_dilemma()
        self._build_card()

    def _pick_dilemma(self):
        available = [i for i in range(len(DILEMMAS)) if i not in self.seen_indices]
        if not available:
            self.seen_indices.clear()
            available = list(range(len(DILEMMAS)))
        idx = random.choice(available)
        self.seen_indices.add(idx)
        self.opt_a, self.opt_b = DILEMMAS[idx]
        self.votes_a.clear()
        self.votes_b.clear()

    def _build_card(self):
        self.clear_container()

        count_a = len(self.votes_a)
        count_b = len(self.votes_b)
        total = count_a + count_b

        pct_a = (count_a / total * 100) if total > 0 else 0.0
        pct_b = (count_b / total * 100) if total > 0 else 0.0

        bar_a = progress_bar(count_a, total or 1, length=12)
        bar_b = progress_bar(count_b, total or 1, length=12)

        header = (
            f"# 🤔 Would You Rather?\n"
            f"> Cast your vote on this dilemma! Total Votes: **{total}**"
        )
        self.add_section(header)
        self.add_separator(discord.SeparatorSpacing.small)

        content = (
            f"### 🔵 Option A:\n"
            f"> **{self.opt_a}**\n"
            f"`{bar_a}` **{pct_a:.1f}%** ({count_a} vote{'s' if count_a != 1 else ''})\n\n"
            f"### 🔴 Option B:\n"
            f"> **{self.opt_b}**\n"
            f"`{bar_b}` **{pct_b:.1f}%** ({count_b} vote{'s' if count_b != 1 else ''})"
        )
        self.add_text(content)
        self.add_separator(discord.SeparatorSpacing.small)

        # Buttons
        btn_a = discord.ui.Button(label="Option A", emoji="🔵", style=discord.ButtonStyle.primary)
        btn_b = discord.ui.Button(label="Option B", emoji="🔴", style=discord.ButtonStyle.danger)
        btn_next = discord.ui.Button(label="Next Dilemma", emoji="➡️", style=discord.ButtonStyle.secondary)

        btn_a.callback = self._on_vote_a
        btn_b.callback = self._on_vote_b
        btn_next.callback = self._on_next

        self.add_row(btn_a, btn_b, btn_next, DismissButton(user_id=self.requester.id))
        self.add_footer("Click an option to vote or toggle your choice · Click 'Next' for a new question")

    async def _on_vote_a(self, interaction: discord.Interaction):
        uid = interaction.user.id
        if uid in self.votes_a:
            self.votes_a.remove(uid)
            msg = "↩️ Removed your vote for **Option A**."
        else:
            self.votes_a.add(uid)
            self.votes_b.discard(uid)
            msg = "✅ Recorded your vote for **Option A**!"

        self._build_card()
        await interaction.response.edit_message(view=self)
        try:
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            pass

    async def _on_vote_b(self, interaction: discord.Interaction):
        uid = interaction.user.id
        if uid in self.votes_b:
            self.votes_b.remove(uid)
            msg = "↩️ Removed your vote for **Option B**."
        else:
            self.votes_b.add(uid)
            self.votes_a.discard(uid)
            msg = "✅ Recorded your vote for **Option B**!"

        self._build_card()
        await interaction.response.edit_message(view=self)
        try:
            await interaction.followup.send(msg, ephemeral=True)
        except Exception:
            pass

    async def _on_next(self, interaction: discord.Interaction):
        self._pick_dilemma()
        self._build_card()
        await interaction.response.edit_message(view=self)


class WouldYouRather(commands.Cog):
    """Interactive Components V2 Would You Rather game."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(
        name="wyr",
        aliases=["wouldyourather"],
        description="🤔 Interactive Would You Rather dilemma with live community voting",
    )
    async def wyr(self, ctx: commands.Context):
        view = WYRView(self.bot, ctx.author)
        await send_view(ctx, view)
        logger.info("WYR: %s opened Would You Rather", ctx.author)


async def setup(bot: commands.Bot):
    await bot.add_cog(WouldYouRather(bot))
    logger.debug("Loaded WouldYouRather")

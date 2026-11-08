"""
cogs/fun/ship.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enhanced ship command with:
  • Cinematic gradient ship card image
  • Animated-style glow rings, particle stars, shimmer bar
  • Modern Discord Components V2 ship card
  • ❤️ Reaction, 💬 score breakdown, and 🔗 share actions
  • Ships members, plain text names, or "random"
  • Consistent (hash-based) results per pair
  • 🔄 Temporary re-roll button — unlimited percentage-only rerolls
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import asyncio
import functools
import hashlib
import io
import logging
import math
import os
import random
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

import aiohttp
import discord
from discord import app_commands

# Ship UI uses Discord Components V2.
try:
    _DPT = tuple(discord.version_info[:3])
except Exception:
    _DPT = tuple(int(x) for x in discord.__version__.split(".")[:3])

if _DPT < (2, 7, 1):
    raise RuntimeError(
        f"ship.py requires discord.py >= 2.7.1 for the Components V2 UI; "
        f"detected {discord.__version__}. Upgrade with: "
        f"python -m pip install -U discord.py"
    )
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ── Tier system ────────────────────────────────────────────────────────────────
TIER_DESCRIPTIONS = {
    "💞 SOULMATES": [
        "Literally made for each other. The universe ships it.",
        "Written in the stars, certified by quantum physics, blessed by ancient deities.",
        "They share a single cosmic heartbeat and an unspoken mental telepathy.",
        "Wedding invitations are practically printing themselves in the server logs.",
        "An absolute 1-in-a-million celestial match. Protect this at all costs.",
        "Even the bot's neural circuits are weeping joyful tears at this synergy.",
    ],
    "💖 Perfect Match": [
        "Off-the-charts chemistry. Do they know yet?",
        "Main character energy. Everyone in voice chat is quietly rooting for them.",
        "The mutual banter is so effortless it feels scripted by an Oscar-winning writer.",
        "Electric tension every time they type in the same channel simultaneously.",
        "Spotify blend score would probably shatter music streaming servers.",
        "Soulmates in training. The vibes are immaculate and completely undeniable.",
    ],
    "💕 Great Vibes": [
        "Strong pull. Something's definitely there.",
        "Late-night voice calls and shared playlists are imminent.",
        "They laugh at each other's jokes before the punchline even drops.",
        "A friendship that could easily stumble into something legendary.",
        "High mutual respect with a spicy dash of unspoken affection.",
        "Comfortable silence or non-stop chaotic laughter — both work flawlessly.",
    ],
    "💓 Promising": [
        "Sparks flying. Could go somewhere beautiful.",
        "A few shared late-night conversations could turn this into a full romance arc.",
        "Subtle eye contact across the digital void. The foundation is solid.",
        "A mutual understanding is brewing. Keep an eye on these two.",
        "Noticeable chemistry that both of them are probably pretending not to notice.",
    ],
    "💛 Neutral": [
        "Neither here nor there… yet. Give it time.",
        "Friendly acquaintances awaiting a shared crisis or common enemy to bond over.",
        "Could be best friends, could stay polite strangers. The dice have yet to roll.",
        "Perfect balance of mutual indifference and mild polite curiosity.",
        "A clean slate with zero baggage. Anything could happen from here.",
    ],
    "🤍 Lukewarm": [
        "The vibe is… complicated.",
        "One texts in full paragraphs; the other replies with 'k' 4 hours later.",
        "They tolerate each other in group calls, but a 1-on-1 DM would be pure silence.",
        "Like water and slightly oiled water — they coexist, but don't really mix.",
        "One likes pineapple on pizza, the other considers it a criminal felony.",
    ],
    "🖤 Unlikely": [
        "Opposites attract? Not this time.",
        "Their communication styles are in two completely different solar systems.",
        "A 5-minute conversation has an 80% chance of turning into a debate on cereal.",
        "Best kept at a safe 3-channel distance for server peace and stability.",
        "Even their Discord activity statuses seem to disagree with each other.",
    ],
    "💔 Disaster": [
        "Run. Just run.",
        "If you put these two in an escape room, neither makes it out alive.",
        "Pure chaotic anti-matter. Contact between them risks digital annihilation.",
        "Two tectonic plates grinding against each other with zero lube.",
        "Moderators have been issued safety goggles just in case they interact.",
        "Not even an intervention from the server owner can salvage this collision.",
    ],
}

TIERS = [
    (100, 100, "💞 SOULMATES",     (255, 100, 180), (255, 20,  120)),
    (85,  99,  "💖 Perfect Match", (255, 130, 160), (220, 50,  130)),
    (70,  84,  "💕 Great Vibes",   (240, 100, 140), (200, 60,  120)),
    (55,  69,  "💓 Promising",     (210, 140, 160), (180, 80,  130)),
    (45,  54,  "💛 Neutral",       (220, 200,  80), (180, 160,  40)),
    (30,  44,  "🤍 Lukewarm",      (180, 180, 200), (140, 140, 170)),
    (15,  29,  "🖤 Unlikely",      (120, 120, 140), ( 80,  80, 110)),
    ( 0,  14,  "💔 Disaster",      ( 80,  80,  90), ( 40,  40,  60)),
]

FUN_FACTS = [
    "Their star signs are {pct}% compatible.",
    "A fortune teller saw this coming from three dimensions away.",
    "Scientists can't explain this result, but the server accepts it.",
    "The algorithm never lies. Trust the digital Oracle.",
    "Even the bot is secretly rooting for them.",
    "Statistically, this pairing was 100% inevitable.",
    "The multiverse agreed on this one across 14 million timelines.",
    "Love language match: {pct}% confirmed by relationship scientists.",
    "Spotify co-listening sessions and shared playlists incoming.",
    "Side effects may include sudden butterflies and erratic typing.",
    "Their combined aura level is radiating through the entire guild.",
    "They would either win The Amazing Race or crash the car on mile 1.",
    "NASA satellite telemetry detected unusual heart rates nearby.",
    "They definitely have shared inside jokes that nobody else understands.",
    "Their meme compatibility index is officially rated at {pct}%.",
    "If they started a podcast, it would debut at #1 on Spotify charts.",
    "One handles the ordering, the other handles the social anxiety.",
    "One loses the keys, the other knows exactly which cushion they fell under.",
    "Together, they possess exactly 1.5 collective braincells on a good day.",
    "They are currently maintaining an unspoken staring contest through their screens.",
    "Server logs show an 87% increase in mutual typing indicators.",
    "They could conquer an escape room in 8 minutes flat.",
    "One starts the sentence, the other orders the dessert.",
    "Their sleep schedules are synchronized in the most chaotic way possible.",
    "A romantic comedy script has already been drafted based on their vibes.",
    "They are one shared midnight snack away from making server history.",
    "Their duo gaming winrate increases by {pct}% when playing together.",
    "An ancient prophecy carved into stone warned the moderators about this pair.",
    "The FBI agent monitoring their chat just shed a solitary happy tear.",
    "They would argue for 45 minutes about dinner and then eat cold pizza happily.",
    "Their collective chaotic energy is currently powering this server's host.",
    "One brings the gas, the other brings the matches — pure fireworks.",
    "Even their autocorrect errors seem to complete each other's sentences.",
    "The server economy would collapse if these two ever went into business together.",
    "They share a mutual love for dramatic late-night voice channel rants.",
    "Rumor has it Cupid specifically took target practice for this ship.",
    "They could communicate entirely through custom Discord emojis and understand everything.",
    "One forgets where they parked; the other has photographic GPS memory.",
    "Their duo playlist would either be pure indie acoustics or unhinged hyperpop.",
    "The astrological alignment when they both enter chat is statistically historic.",
    "They have a 94% chance of sending each other the exact same reel at 2:14 AM.",
    "Their dynamic is classified as 'high risk, infinitely higher reward'.",
    "One is the calm before the storm; the other is the category 5 hurricane.",
    "If they were a duo in an RPG, they'd accidentally speedrun the final boss.",
    "They would survive a zombie apocalypse purely to spite each other.",
    "The vibes are currently vibrating at a resonant frequency of {pct} Hz.",
    "They could build IKEA furniture together without filing for divorce.",
    "Their mutual banter is the only thing keeping general chat alive right now.",
    "Every fortune cookie opened within a 10-mile radius confirms this score.",
    "Even the most cynical lurker in the server paused to admire this match.",
    "Statistically speaking, someone in this pair is smiling at their phone right now.",
]

ROASTS = [
    "Not even on the same WiFi network, let alone wavelength.",
    "They once argued about pineapple on pizza. They still do.",
    "Opposites attract — this is the universe's ultimate exception.",
    "Their vibe difference is measurable in intergalactic light-years.",
    "If they were stranded on an island, they'd build rafts in opposite directions.",
    "Communication between them requires a diplomatic peace delegation.",
    "One likes cold air conditioning, the other brings 4 wool blankets.",
    "Their mutual compatibility is currently buffering at 0% on dial-up.",
    "Putting them in a duo lobby is considered an act of war under the Geneva Convention.",
    "They have the exact synergy of orange juice mixed with freshly brushed teeth.",
    "A conversation between them has more awkward pauses than an elevator full of strangers.",
    "One sends voice notes; the other hasn't listened to a voice note since 2018.",
    "Their text history is a barren wasteland of 'seen at 4:12 PM'.",
    "Even Discord's voice servers drop packet quality when they're in the same VC.",
    "They agree on exactly zero things, including what day of the week it is.",
    "Like oil and water, except the oil is on fire and the water is boiling.",
    "The bot tried calculating their chemistry and blue-screened in protest.",
    "Their compatibility score is lower than their remaining phone battery.",
    "One is an early morning bird; the other wakes up when the sun goes down.",
    "They would argue over the rules of Uno until the cards burst into flames.",
    "A psychic looked at this pair and asked for a refund on their own crystal ball.",
    "They share zero braincells and refuse to negotiate shared custody.",
    "One types in all lowercase aesthetic; the other uses ALL CAPS AND COMIC SANS.",
    "Moderators are legally required to keep a fire extinguisher nearby when they chat.",
    "They have an 8% chance of agreeing on which restaurant to order from.",
    "Their duo aura is radiating negative spiritual energy into the server.",
    "One is a minimalist monk; the other is a hoarder of 3,000 unread Discord pings.",
    "Putting them together is like giving a toddler a drum set and an espresso.",
    "Even their Spotify algorithms refuse to acknowledge each other's existence.",
    "Their banter doesn't have romantic tension, just actual tension.",
    "If this ship was a vessel, it hit the iceberg before leaving the harbor.",
    "They would get lost in a straight hallway arguing about which way is forward.",
    "One is listening to lo-fi beats; the other is blasting Norwegian death metal.",
    "Their synergy is currently being investigated by local authorities as a hazard.",
    "Not even a 100-page peace treaty could bridge this conversational canyon.",
    "They would lose a cooperative puzzle game to a team of trained golden retrievers.",
    "One leaves 45 minutes early; the other arrives 2 hours after the event ended.",
    "Their compatibility chart looks like a flatline on an emergency room monitor.",
    "The chemistry here is strictly toxic waste. Wear protective hazmat gear.",
    "They could turn a simple 'hello' into a 3-hour philosophical tribunal.",
    "Even Cupid took one look at this pairing, sighed deeply, and snapped his arrows.",
    "One is reading classical literature; the other is watching subway surfers gameplay.",
    "Their relationship status is officially classified as 'Mutual Ceasefire'.",
    "If they were colors, they'd be fluorescent beige and aggressively dark glitter.",
    "The only thing they have in common is that neither of them wanted this ship.",
]

HYPE = [
    "Someone's about to confess. We can feel the tension through the server rack.",
    "The tension is palpable from three voice channels away.",
    "Bestie-to-lovers arc loading… currently at 98% completion.",
    "The undisputed main characters of this server. Absolutely no competition.",
    "We need someone to cue the romantic soundtrack and dim the channel lights.",
    "The collective server community is currently preparing the wedding guest list.",
    "If you listen closely, you can hear general chat holding its breath.",
    "Their synergy is bright enough to blind someone with dark mode disabled.",
    "A legendary pairing destined to be immortalized in server lore forever.",
    "The chemistry is radiating so hard it's boosting the bot's server ping.",
    "Every romantic comedy ever written was just leading up to this moment.",
    "Two halves of the exact same chaotic braincell finally reuniting.",
    "Even the server owner is quietly smiling in lurker mode watching them.",
    "They don't even need words — one emoji reaction conveys an entire novel.",
    "The banter is Olympic gold-medal level. Pure effortless electricity.",
    "When they enter the call together, the vibe immediately elevates by 400%.",
    "Everyone else in the chat has officially become an extra in their love story.",
    "Their Spotify Blend score would break the streaming algorithm in half.",
    "They could conquer the entire digital realm if they ever teamed up permanently.",
    "Cupid didn't just shoot an arrow; he launched an orbital heat-seeking missile.",
    "This pairing was prophesied in the ancient patch notes of Discord.",
    "The mutual blushing is detectable through webhooks and IP addresses.",
    "They finish each other's sentences before the other person even thinks them.",
    "A connection so magnetic it's causing compasses in the area to spin wildly.",
    "We are witnessing history in the making. Take a screenshot for the archives.",
    "Their mutual dynamic is pure wholesome serotonin with zero artificial preservatives.",
    "If they aren't already dating, the entire server demands a formal explanation.",
    "One smile from either of them and the other's whole day is instantly saved.",
    "A partnership built on immaculate taste, chaotic humor, and mutual devotion.",
    "The server's collective heart just melted into a puddle on the floor.",
    "They radiate the cozy warmth of hot cocoa by a fireplace during a blizzard.",
    "Their ship score is so high it literally broke our internal grading scale.",
    "Even the most hardened cynics in the server are clapping and wiping tears.",
    "A match so perfect that celestial astronomers are naming a constellation after them.",
    "They are the gold standard of what peak compatibility looks like in 4K.",
    "The universe conspired across billions of years of cosmic history for this ship.",
    "Every late-night conversation they've ever had was quietly building to this.",
    "They could sit in total silence in voice chat for 6 hours and have the best time.",
    "Their mutual respect and adoration could power a small metropolitan city.",
    "We are officially petitioning Discord to give them a customized shared badge.",
    "It's not a question of 'if' — it's strictly a question of 'when'.",
    "Their aura harmony is resonating at 100% pure unfiltered bliss.",
    "The ship of the century. Everyone take notes on how it's done.",
    "They make being in this server 10x more fun just by existing together.",
    "Destiny knocked on the door, and both of them answered at the exact same second.",
]

# ── Duo challenge pool ────────────────────────────────────────────────────────
DUO_CHALLENGES = [
    ("⚡ Sync Check", "Both send the same emoji at the exact same time without coordinating."),
    ("🎯 Quick Draw", "Both name a food you would eat right this second. No copying allowed!"),
    ("🧠 Mind Match", "Count down from 3 and both say a number from 1–10. Matching = instant glory."),
    ("😂 No Laugh Challenge", "Send the funniest meme or joke from your camera roll. First person to react/laugh loses."),
    ("🔤 Letter Lock", "Pick a random letter. For the next 60 seconds, neither person can use a word starting with it."),
    ("🎨 Same Vibe", "Both choose a color that represents your current energy. Reveal in chat together."),
    ("🎵 Song Swap", "Each pick one song that perfectly encapsulates the other person. Reveal simultaneously."),
    ("🤝 Compliment Battle", "Take turns giving genuine, specific compliments. First person to hesitate loses."),
    ("🕵️ Two Truths & A Lie", "Each give two true statements and one fake one. The other person must guess the lie."),
    ("⏱️ Speed Round", "You each get 10 seconds to answer: 'What is your dream vacation destination?'"),
    ("🎬 Movie Pitch", "Take turns adding one sentence each to create the worst blockbuster movie plot ever."),
    ("🍕 Pizza Debate", "Collaborate on designing the ultimate pizza with 4 toppings you both agree on."),
    ("🦁 Spirit Animal", "Assign each other a spirit animal and give a 2-sentence justification for why."),
    ("📻 Radio Host", "Take turns giving a 20-second dramatic radio intro for the other person in chat."),
    ("🧩 Word Association", "One person says a word, the other immediately replies with the first word that comes to mind (10 rounds)."),
    ("🍔 Food Duel", "Both name your favorite fast food chain. Debate which is superior in 3 sentences."),
    ("🎤 Karaoke Duet", "Name a song that you two would sing together at a karaoke bar with zero shame."),
    ("🛡️ Zombie Bunker", "Divide the labor: who is on scavenging duty, and who is defending the bunker?"),
    ("📦 Desert Island", "Each pick ONE item you would bring to a deserted island that benefits both of you."),
    ("🎮 Co-op Draft", "Name the video game you two would dominate as a duo team."),
    ("🎭 Secret Identity", "Come up with a ridiculous superhero duo name and matching superpower combo."),
    ("☕ Coffee Order", "Guess each other's exact morning drink or coffee/tea order. See who gets closest."),
    ("💬 Emoji Sentence", "One sends a 4-emoji sentence; the other must translate it into an English sentence."),
    ("🏆 Award Ceremony", "Award each other a fictional trophy (e.g., 'Most Likely to Fall Asleep in VC')."),
    ("📚 3-Word Story", "Take turns typing exactly three words each to write a cohesive 6-sentence story."),
    ("🧊 Icebreaker Clash", "Ask each other the weirdest question you have ever wanted to ask someone."),
    ("🕶️ Secret Handshake", "Invent an ASCII or emoji-based secret handshake in chat right now."),
    ("🚗 Road Trip DJ", "Assign who drives the car and who gets absolute control of the Spotify AUX cord."),
    ("👑 Crown the Best", "Both agree on the best season of the year, or debate until someone concedes."),
    ("🐾 Pet Name Draft", "If you two co-adopted a golden retriever, what name do you both agree on?"),
    ("🏰 Fantasy Guild", "Name your two-person adventuring guild and assign your RPG classes (Mage, Warrior, etc.)."),
    ("📺 Binge Watch", "Agree on one TV series that you both would happily binge-watch together this weekend."),
    ("💡 Million Dollar Idea", "Brainstorm a completely useless invention that would still make $1,000,000."),
    ("🔮 Future Forecast", "Predict where the other person will be in 5 years in exactly one sentence."),
    ("🍝 Cooking Disaster", "Describe the most horrific dinner you two could accidentally cook together."),
    ("⛺ Camping Survival", "Who starts the campfire, and who accidentally attracts a grizzly bear with snacks?"),
    ("🕵️ Detective Duo", "One plays the 'Good Cop', the other plays the 'Bad Cop' questioning general chat."),
    ("🎪 Circus Act", "What would your duo circus performance act be (acrobats, lion tamers, clowns)?"),
    ("🚀 Mars Mission", "If you two were the first humans on Mars, what are the first words you say to Earth?"),
    ("⚡ Rapid Fire 5", "Answer 5 'This or That' questions back-to-back: Cats vs Dogs, Summer vs Winter, Sweet vs Salty, etc."),
]

# ── Colour helpers ─────────────────────────────────────────────────────────────

def get_tier(pct: int):
    for lo, hi, label, col_a, col_b in TIERS:
        if lo <= pct <= hi:
            desc_pool = TIER_DESCRIPTIONS.get(label, ["Compatible vibes."])
            desc = random.choice(desc_pool)
            return label, col_a, col_b, desc
    return "❓ Unknown", (128,128,128), (64,64,64), "The algorithm is confused."

def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i]-a[i]) * t) for i in range(3))

def hex_col(rgb): return "#{:02x}{:02x}{:02x}".format(*rgb)

# ── Font ───────────────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=32)
def get_font(size: int) -> ImageFont.FreeTypeFont:
    font_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../DejaVuSans-Bold.ttf"))
    try:    return ImageFont.truetype(font_path, size)
    except: return ImageFont.load_default()

# ── Image primitives ───────────────────────────────────────────────────────────

def make_circle(img: Image.Image, size: int) -> Image.Image:
    img = img.resize((size, size), getattr(Image, "Resampling", Image).LANCZOS)
    mask = Image.new("L", (size, size), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(img, (0, 0))
    out.putalpha(mask)
    return out

def glow_ring(draw: ImageDraw.Draw, cx, cy, r, color, width=6, alpha=180):
    """Draw a soft glowing circle ring"""
    for i in range(width, 0, -1):
        a = int(alpha * (i / width) ** 2)
        c = color + (a,)
        draw.ellipse([cx-r-i, cy-r-i, cx+r+i, cy+r+i], outline=c, width=2)

def draw_star(draw, cx, cy, size, color, alpha=200):
    pts = []
    for i in range(8):
        angle = math.radians(i * 45)
        r     = size if i % 2 == 0 else size * 0.4
        pts.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(pts, fill=color + (alpha,))

def scatter_particles(draw, w, h, pct, seed=42):
    rng = random.Random(seed)
    count = int(pct * 0.6)
    for _ in range(count):
        x    = rng.randint(0, w)
        y    = rng.randint(0, h)
        size = rng.randint(1, 4)
        alpha = rng.randint(60, 200)
        draw.ellipse([x-size, y-size, x+size, y+size], fill=(255,255,255,alpha))

def draw_gradient_bar(draw, x, y, w, h, pct, col_a, col_b):
    """Segmented shimmer bar showing percentage"""
    segments = 40
    filled   = int(segments * pct / 100)
    seg_w    = w / segments
    for i in range(segments):
        t   = i / segments
        col = lerp_color(col_a, col_b, t)
        x0  = x + i * seg_w
        x1  = x0 + seg_w - 2
        if i < filled:
            alpha = 255
        elif i == filled:
            alpha = 120
        else:
            alpha = 40
        draw.rounded_rectangle([x0, y, x1, y+h], radius=h//2, fill=col+(alpha,))

def draw_heart_poly(draw, cx, cy, size, color, alpha=255):
    pts = []
    for deg in range(0, 360, 3):
        r   = math.radians(deg)
        hx  = size * (16 * math.sin(r)**3)
        hy  = -size * (13*math.cos(r) - 5*math.cos(2*r) - 2*math.cos(3*r) - math.cos(4*r))
        pts.append((cx + hx, cy + hy))
    draw.polygon(pts, fill=color+(alpha,))

def centered_text(draw, y, text, font, fill, w, shadow=True):
    bbox = draw.textbbox((0,0), text, font=font)
    tw   = bbox[2] - bbox[0]
    x    = (w - tw) // 2
    if shadow:
        for dx, dy in [(-2,2),(2,2),(0,3)]:
            draw.text((x+dx, y+dy), text, font=font, fill=(0,0,0,120))
    draw.text((x, y), text, font=font, fill=fill)

def text_avatar(text: str, size: int = 200) -> Image.Image:
    h   = hashlib.md5(text.encode()).hexdigest()
    r,g,b = int(h[:2],16), int(h[2:4],16), int(h[4:6],16)
    img = Image.new("RGBA", (size, size), (r,g,b,255))
    draw = ImageDraw.Draw(img)
    ch   = text[0].upper() if text else "?"
    font = get_font(size // 2)
    bb   = draw.textbbox((0,0), ch, font=font)
    draw.text(((size-(bb[2]-bb[0]))//2 - bb[0], (size-(bb[3]-bb[1]))//2 - bb[1]), ch, font=font, fill=(255,255,255,230))
    return img

# ── Avatar download ────────────────────────────────────────────────────────────

_SHARED_SHIP_SESSION: Optional[aiohttp.ClientSession] = None

async def _fetch_member_avatar(member) -> Optional[Image.Image]:
    if member is None:
        return None
    try:
        if hasattr(member, "display_avatar") and hasattr(member.display_avatar, "read"):
            raw = await member.display_avatar.read()
            if raw:
                return Image.open(io.BytesIO(raw)).convert("RGBA")
    except Exception:
        pass
    if hasattr(member, "display_avatar"):
        return await fetch_avatar(str(member.display_avatar.url))
    return None

async def fetch_avatar(url: str) -> Optional[Image.Image]:
    global _SHARED_SHIP_SESSION
    try:
        if _SHARED_SHIP_SESSION is None or _SHARED_SHIP_SESSION.closed:
            _SHARED_SHIP_SESSION = aiohttp.ClientSession()
        async with _SHARED_SHIP_SESSION.get(str(url), timeout=aiohttp.ClientTimeout(total=6)) as r:
            if r.status == 200:
                return Image.open(io.BytesIO(await r.read())).convert("RGBA")
    except Exception as e:
        logger.warning("Avatar download failed: %s", e)
    return None

# ── Main image builder ─────────────────────────────────────────────────────────

def _render_ship_card_sync(
    name1: str,
    name2: str,
    pct: int,
    col_a: tuple,
    col_b: tuple,
    av1: Optional[Image.Image],
    av2: Optional[Image.Image],
) -> io.BytesIO:
    W, H = 960, 380
    AVATAR_SIZE = 160

    # ── Background gradient ────────────────────────────────────────────────────
    base = Image.new("RGBA", (W, H))
    bg   = ImageDraw.Draw(base)

    dark_a = tuple(max(0, c - 80) for c in col_a)
    dark_b = tuple(max(0, c - 80) for c in col_b)
    for y in range(H):
        t   = y / H
        col = lerp_color(dark_a, dark_b, t)
        bg.line([(0,y),(W,y)], fill=col+(255,))

    # vignette overlay
    vig = Image.new("RGBA", (W,H), (0,0,0,0))
    vd  = ImageDraw.Draw(vig)
    for i in range(60):
        a = int(180 * (i/60)**2)
        vd.rectangle([i, i, W-i, H-i], outline=(0,0,0,a))
    base = Image.alpha_composite(base, vig)

    # particle stars
    part = Image.new("RGBA", (W,H), (0,0,0,0))
    scatter_particles(ImageDraw.Draw(part), W, H, pct, seed=pct*7)
    base = Image.alpha_composite(base, part)

    # ── Glow layer ─────────────────────────────────────────────────────────────
    glow = Image.new("RGBA", (W,H), (0,0,0,0))
    gd   = ImageDraw.Draw(glow)
    for radius in range(80, 20, -10):
        a = int(80 * (1 - radius/80) * (pct/100))
        gd.ellipse([W//2-radius, H//2-radius, W//2+radius, H//2+radius], fill=lerp_color(col_a,col_b,0.5)+(a,))
    base = Image.alpha_composite(base, glow)

    # ── Avatars ────────────────────────────────────────────────────────────────
    if av1 is None: av1 = text_avatar(name1, AVATAR_SIZE)
    circ1 = make_circle(av1, AVATAR_SIZE)

    if av2 is None: av2 = text_avatar(name2, AVATAR_SIZE)
    circ2 = make_circle(av2, AVATAR_SIZE)

    # Glow rings behind avatars
    av_layer = Image.new("RGBA", (W,H), (0,0,0,0))
    av_draw  = ImageDraw.Draw(av_layer)
    cx1, cy1 = 135, H//2
    cx2, cy2 = W-135, H//2
    for radius in [100, 90, 82]:
        a = int(180 * (1 - (radius-82)/20))
        av_draw.ellipse([cx1-radius, cy1-radius, cx1+radius, cy1+radius], fill=col_a+(min(a,255),))
        av_draw.ellipse([cx2-radius, cy2-radius, cx2+radius, cy2+radius], fill=col_b+(min(a,255),))
    base = Image.alpha_composite(base, av_layer)

    # White border ring
    border_size = AVATAR_SIZE + 8
    brd = Image.new("RGBA", (border_size, border_size), (0,0,0,0))
    ImageDraw.Draw(brd).ellipse((0,0,border_size,border_size), fill=(255,255,255,240))
    base.paste(brd, (cx1 - border_size//2, cy1 - border_size//2), brd)
    base.paste(brd, (cx2 - border_size//2, cy2 - border_size//2), brd)
    base.paste(circ1, (cx1 - AVATAR_SIZE//2, cy1 - AVATAR_SIZE//2), circ1)
    base.paste(circ2, (cx2 - AVATAR_SIZE//2, cy2 - AVATAR_SIZE//2), circ2)

    draw = ImageDraw.Draw(base)

    # ── Heart ─────────────────────────────────────────────────────────────────
    heart_size = 3 + int(pct * 0.12)
    heart_col  = lerp_color(col_a, col_b, 0.5)
    draw_heart_poly(draw, W//2, H//2 - 10, heart_size+4, (255,255,255), alpha=30)
    draw_heart_poly(draw, W//2, H//2 - 10, heart_size,   heart_col,     alpha=230)

    if pct >= 70:
        for sx, sy in [(60,30),(W-60,30),(60,H-30),(W-60,H-30)]:
            draw_star(draw, sx, sy, 8, (255,255,255), alpha=int(pct*2))

    # ── Percentage text ────────────────────────────────────────────────────────
    f_huge = get_font(88)
    f_med  = get_font(28)
    f_xs   = get_font(16)

    pct_txt = f"{pct}%"
    centered_text(draw, H//2 + 30, pct_txt, f_huge, (255,255,255,255), W, shadow=True)

    # ── Names ─────────────────────────────────────────────────────────────────
    n1_disp = (name1[:13] + "…") if len(name1) > 13 else name1
    n2_disp = (name2[:13] + "…") if len(name2) > 13 else name2

    def side_text(draw, cx, y, text, font, col):
        bb  = draw.textbbox((0,0), text, font=font)
        tw  = bb[2]-bb[0]
        x   = cx - tw//2
        for dx,dy in [(-1,1),(1,1),(0,2)]:
            draw.text((x+dx, y+dy), text, font=font, fill=(0,0,0,160))
        draw.text((x, y), text, font=font, fill=col+(255,))

    side_text(draw, cx1, cy1 + AVATAR_SIZE//2 + 14, n1_disp, f_med, col_a)
    side_text(draw, cx2, cy2 + AVATAR_SIZE//2 + 14, n2_disp, f_med, col_b)

    # ── Shimmer bar ────────────────────────────────────────────────────────────
    bar_x = W//2 - 160
    bar_y = H - 44
    bar_w = 320
    bar_h = 14
    bar_layer = Image.new("RGBA", (W, H), (0,0,0,0))
    draw_gradient_bar(ImageDraw.Draw(bar_layer), bar_x, bar_y, bar_w, bar_h, pct, col_a, col_b)
    base = Image.alpha_composite(base, bar_layer)
    draw = ImageDraw.Draw(base)

    bb = draw.textbbox((0,0), "0%",   font=f_xs); draw.text((bar_x - bb[2]-4,       bar_y-1), "0%",   font=f_xs, fill=(200,200,200,160))
    bb = draw.textbbox((0,0), "100%", font=f_xs); draw.text((bar_x+bar_w+4,          bar_y-1), "100%", font=f_xs, fill=(200,200,200,160))

    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="PNG", compress_level=1)
    buf.seek(0)
    return buf


async def build_ship_image(
    name1: str, name2: str,
    pct: int,
    col_a: tuple, col_b: tuple,
    member1=None, member2=None,
) -> io.BytesIO:
    av1, av2 = await asyncio.gather(
        _fetch_member_avatar(member1),
        _fetch_member_avatar(member2),
    )
    return await asyncio.to_thread(
        _render_ship_card_sync, name1, name2, pct, col_a, col_b, av1, av2
    )

# ── Modern Components V2 View ────────────────────────────────────────────────

class ShipView(discord.ui.LayoutView):
    """Modern Components V2 interaction surface for a ship result.

    The normal result is deterministic for the pair. A reroll temporarily
    randomizes only the percentage while keeping the same two people.
    """

    def __init__(
        self,
        cog,
        ctx,
        member1,
        member2,
        name1,
        name2,
        id1,
        id2,
        pct,
        *,
        original_pct=None,
        is_rerolled=False,
    ):
        super().__init__(timeout=180)
        self.cog = cog
        self.ctx = ctx
        self.member1 = member1
        self.member2 = member2
        self.name1 = name1
        self.name2 = name2
        self.id1 = id1
        self.id2 = id2

        self.pct = pct
        self.is_rerolled = is_rerolled

        self.reacts = set()
        self.message = None
        self._fact = cog.fun_fact(pct)
        self._build()

    def _build(self):
        # Rebuild the V2 layout so reroll can replace the entire card cleanly.
        self.clear_items()

        self.container = discord.ui.Container()
        self.container.add_item(
            discord.ui.TextDisplay(
                f"# 💘 {discord.utils.escape_markdown(self.name1)} × "
                f"{discord.utils.escape_markdown(self.name2)}"
            )
        )
        self.container.add_item(
            discord.ui.MediaGallery(
                discord.MediaGalleryItem(
                    "attachment://ship.png",
                    description=f"Compatibility card for {self.name1} and {self.name2}",
                )
            )
        )

        tier_label, _, _, tier_desc = get_tier(self.pct)
        sname = self.cog.ship_name(self.name1, self.name2)

        status = " 🔄 **Temporary reroll**" if self.is_rerolled else ""
        note = (
            "-# 🔄 Temporary reroll — same two people, percentage only. Run `/ship` again for the original result."
            if self.is_rerolled
            else
            "-# 🔒 Original result is deterministic for this pair."
        )

        self.result_text = discord.ui.TextDisplay(
            f"## {tier_label} · **{self.pct}%**{status}\n"
            f"**Ship name:** `{discord.utils.escape_markdown(sname)}`\n"
            f"> {discord.utils.escape_markdown(tier_desc)}\n\n"
            f"✨ *{discord.utils.escape_markdown(self._fact)}*"
        )

        self.container.add_item(self.result_text)
        self.container.add_item(discord.ui.TextDisplay("━━━━━━━━━━━━━━━━━━━━━━━━"))

        self.reaction_button = discord.ui.Button(
            label=f"React · {len(self.reacts)}",
            emoji="❤️",
            style=discord.ButtonStyle.danger,
        )
        self.why_button = discord.ui.Button(
            label="Why this score?",
            emoji="💬",
            style=discord.ButtonStyle.secondary,
        )
        self.reroll_button = discord.ui.Button(
            label="Reroll",
            emoji="🔄",
            style=discord.ButtonStyle.primary,
        )
        self.share_button = discord.ui.Button(
            label="Share",
            emoji="🔗",
            style=discord.ButtonStyle.secondary,
        )
        self.challenge_button = discord.ui.Button(
            label="Duo Challenge",
            emoji="🎯",
            style=discord.ButtonStyle.success,
        )

        self.reaction_button.callback = self._react
        self.why_button.callback = self._why
        self.reroll_button.callback = self._reroll
        self.share_button.callback = self._share
        self.challenge_button.callback = self._duo_challenge

        self.actions = discord.ui.ActionRow(
            self.reaction_button,
            self.why_button,
            self.reroll_button,
            self.challenge_button,
            self.share_button,
        )
        self.container.add_item(self.actions)
        self.container.add_item(discord.ui.TextDisplay(note))

        self.add_item(self.container)

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Public result: everyone in the channel may use the buttons.
        return True

    async def _react(self, interaction: discord.Interaction):
        if interaction.user.id in self.reacts:
            return await interaction.response.send_message(
                "❤️ You already reacted to this ship!",
                ephemeral=True,
            )

        self.reacts.add(interaction.user.id)
        self.reaction_button.label = f"React · {len(self.reacts)}"
        await interaction.response.edit_message(view=self)

    async def _why(self, interaction: discord.Interaction):
        tier_label, _, _, tier_desc = get_tier(self.pct)

        score_bands = (
            "💗 **Chemistry:** absolutely cooking"
            if self.pct >= 70 else
            "✨ **Chemistry:** there is something here"
            if self.pct >= 45 else
            "🌱 **Chemistry:** potential exists, somehow"
            if self.pct >= 25 else
            "💀 **Chemistry:** the algorithm has concerns"
        )
        balance = (
            "🌟 High-synergy pairing"
            if self.pct >= 85 else
            "💫 Strong pairing"
            if self.pct >= 70 else
            "🫶 Mixed signals"
            if self.pct >= 45 else
            "🧊 Low compatibility"
        )

        reroll_note = (
            "-# 🔄 Temporary reroll — same two people, randomized percentage. Run `/ship` again for the original result."
            if self.is_rerolled else ""
        )

        await interaction.response.send_message(
            (
                f"## 💬 Why {self.pct}%?\n"
                f"**{discord.utils.escape_markdown(self.name1)} × "
                f"{discord.utils.escape_markdown(self.name2)}**\n\n"
                f"{score_bands}\n"
                f"{balance}\n"
                f"🏷️ **Tier:** {tier_label}\n\n"
                f"> {discord.utils.escape_markdown(tier_desc)}\n\n"
                f"-# The percentage is fun-score, not a real compatibility measurement."
                f"{reroll_note}"
            ),
            ephemeral=True,
        )


    async def _reroll(self, interaction: discord.Interaction):
        # Keep the exact same two people. Only randomize the percentage.
        await interaction.response.defer()

        self.pct = random.randint(0, 100)
        self._fact = self.cog.fun_fact(self.pct)
        self.is_rerolled = True

        _, col_a, col_b, tier_desc = get_tier(self.pct)

        img_buf = await build_ship_image(
            self.name1,
            self.name2,
            self.pct,
            col_a,
            col_b,
            self.member1,
            self.member2,
        )
        file = discord.File(img_buf, filename="ship.png")

        # Update only the score text. Do not rebuild the view.
        self.result_text.content = (
            f"## {get_tier(self.pct)[0]} · **{self.pct}%** 🔄 **Temporary reroll**\n"
            f"**Ship name:** `{discord.utils.escape_markdown(self.cog.ship_name(self.name1, self.name2))}`\n"
            f"> {discord.utils.escape_markdown(tier_desc)}\n\n"
            f"✨ *{discord.utils.escape_markdown(self._fact)}*"
        )

        await interaction.edit_original_response(
            attachments=[file],
            view=self,
        )

    async def _share(self, interaction: discord.Interaction):
        temp_note = " · 🔄 temporary reroll" if self.is_rerolled else ""
        await interaction.response.send_message(
            (
                f"💘 **{discord.utils.escape_markdown(self.name1)} × "
                f"{discord.utils.escape_markdown(self.name2)}**\n"
                f"**{self.pct}%** · {get_tier(self.pct)[0]}{temp_note}\n"
                f"Ship name: **{discord.utils.escape_markdown(self.cog.ship_name(self.name1, self.name2))}**\n"
                f"🔗 Run `/ship {discord.utils.escape_markdown(self.name1)} {discord.utils.escape_markdown(self.name2)}` to view the original result."
            ),
            ephemeral=False,
        )

    async def _duo_challenge(self, interaction: discord.Interaction):
        title, prompt = random.choice(DUO_CHALLENGES)
        await interaction.response.send_message(
            f"## {title} — Duo Challenge for {discord.utils.escape_markdown(self.name1)} & {discord.utils.escape_markdown(self.name2)}!\n"
            f"> {prompt}\n\n"
            f"-# 💘 Ship Score: **{self.pct}%** · Click **🎯 Duo Challenge** again for another challenge!",
            ephemeral=False,
        )

    async def on_timeout(self):
        for item in self.walk_children():
            if hasattr(item, "disabled"):
                item.disabled = True
        if self.message:
            try:
                await self.message.edit(view=self)
            except (discord.NotFound, discord.HTTPException):
                pass


# ── Cog ────────────────────────────────────────────────────────────────────────

class Ship(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Reuse the MongoDB connection created by bot.py.
        # bot.py connects before loading this cog and exposes the database
        # through bot.mongo_db.
        self.db = getattr(bot, "mongo_db", None)
        self.ship_pairs = self.db["ship_pairs"] if self.db is not None else None
        self.ship_users = self.db["ship_users"] if self.db is not None else None

    async def _record_ship(self, guild_id: Optional[int], id1: str, id2: str,
                           name1: str, name2: str, pct: int, author_id: int):
        """Persist the permanent pair score and the command user's daily streak."""
        if self.db is None or guild_id is None:
            return

        gid = str(guild_id)
        a, b = sorted([str(id1), str(id2)])
        pair_key = f"{a}:{b}"
        now = datetime.now(timezone.utc)
        today = now.date().isoformat()

        await self.ship_pairs.update_one(
            {"guild_id": gid, "pair_key": pair_key},
            {
                "$set": {
                    "guild_id": gid,
                    "pair_key": pair_key,
                    "id1": a,
                    "id2": b,
                    "name1": name1 if str(id1) == a else name2,
                    "name2": name2 if str(id2) == b else name1,
                    "score": pct,
                    "last_shipped": now,
                },
                "$inc": {"times_shipped": 1},
            },
            upsert=True,
        )

        user_key = {"guild_id": gid, "user_id": str(author_id)}
        user = await self.ship_users.find_one(user_key)
        if not user:
            await self.ship_users.insert_one({
                **user_key,
                "current_streak": 1,
                "longest_streak": 1,
                "last_date": today,
                "total_ships": 1,
            })
            return

        last_date = user.get("last_date")
        current = int(user.get("current_streak", 0))
        longest = int(user.get("longest_streak", current))
        total = int(user.get("total_ships", 0)) + 1

        if last_date == today:
            # Multiple ships on the same day do not inflate the streak.
            await self.ship_users.update_one(
                user_key,
                {"$set": {"total_ships": total}},
            )
        else:
            try:
                last = datetime.fromisoformat(str(last_date)).date()
                day_gap = (now.date() - last).days
            except Exception:
                day_gap = 999

            current = current + 1 if day_gap == 1 else 1
            longest = max(longest, current)
            await self.ship_users.update_one(
                user_key,
                {"$set": {
                    "current_streak": current,
                    "longest_streak": longest,
                    "last_date": today,
                    "total_ships": total,
                }},
            )

    def _mongo_required(self):
        return self.db is not None and self.ship_pairs is not None and self.ship_users is not None

    def calc_pct(self, id1: str, id2: str) -> int:
        a, b = sorted([str(id1), str(id2)])
        return int(hashlib.md5(f"{a}:{b}".encode()).hexdigest()[:8], 16) % 101

    def ship_name(self, n1: str, n2: str) -> str:
        return (n1[:len(n1)//2] + n2[len(n2)//2:]).title()

    def fun_fact(self, pct: int) -> str:
        pool = ROASTS if pct < 25 else (HYPE if pct >= 75 else FUN_FACTS)
        return random.choice(pool).format(pct=pct)

    def _resolve(self, ctx: commands.Context, val: Optional[str]):
        """(member_or_user | None, display_name | None)"""
        if not val:
            return None, None
        val = val.strip()
        if val.lower() == "random":
            return None, "random"

        # 1. Mention (<@123> or <@!123>) or numeric ID
        m = re.match(r"<@!?(\d+)>$", val)
        uid_int = int(m.group(1)) if m else (int(val) if val.isdigit() else None)
        if uid_int is not None:
            if ctx.guild:
                mem = ctx.guild.get_member(uid_int)
                if mem:
                    return mem, mem.display_name
            # Check Group DM recipients or 1-on-1 DM recipient
            recipients = getattr(ctx.channel, "recipients", None)
            if recipients:
                for u in recipients:
                    if u.id == uid_int:
                        return u, u.display_name
            recipient = getattr(ctx.channel, "recipient", None)
            if recipient and recipient.id == uid_int:
                return recipient, recipient.display_name
            cached_u = self.bot.get_user(uid_int)
            if cached_u:
                return cached_u, cached_u.display_name

        # 2. Name search across guild, Group DM, or bot cache
        low = val.lower()
        if ctx.guild:
            for mem in ctx.guild.members:
                if not mem.bot and (mem.display_name.lower() == low or mem.name.lower() == low):
                    return mem, mem.display_name
        recipients = getattr(ctx.channel, "recipients", None)
        if recipients:
            for u in recipients:
                if not u.bot and (u.display_name.lower() == low or u.name.lower() == low):
                    return u, u.display_name
        recipient = getattr(ctx.channel, "recipient", None)
        if recipient and not recipient.bot and (recipient.display_name.lower() == low or recipient.name.lower() == low):
            return recipient, recipient.display_name

        return None, val

    async def _resolve_async(self, ctx: commands.Context, val: Optional[str]):
        """Resolve member/user with REST API fallback for mentions/IDs in DMs & User Apps."""
        mem, name = self._resolve(ctx, val)
        if mem is not None or not val:
            return mem, name
        raw = val.strip()
        m = re.match(r"<@!?(\d+)>$", raw)
        uid_int = int(m.group(1)) if m else (int(raw) if raw.isdigit() else None)
        if uid_int is not None:
            try:
                fetched = await self.bot.fetch_user(uid_int)
                if fetched:
                    return fetched, fetched.display_name
            except Exception:
                pass
        return mem, name

    def _random_member(self, ctx, exclude=None):
        exclude_id = getattr(exclude, "id", None)
        # 1. Server (Guild) members
        if ctx.guild and ctx.guild.members:
            pool = [m for m in ctx.guild.members if not m.bot and m.id != exclude_id]
            if pool:
                return random.choice(pool)

        # 2. Group DM recipients (2 or more members in a group chat)
        recipients = getattr(ctx.channel, "recipients", None)
        if recipients:
            pool = [u for u in recipients if not u.bot and u.id != exclude_id]
            if pool:
                return random.choice(pool)

        # 3. 1-on-1 DM recipient (if chatting with another user via User App)
        recipient = getattr(ctx.channel, "recipient", None)
        if recipient and not recipient.bot and recipient.id != exclude_id:
            return recipient

        # 4. Fallback in DMs: pick a random human user from the bot's user cache
        cached_pool = [u for u in getattr(self.bot, "users", []) if not u.bot and u.id != exclude_id]
        if cached_pool:
            return random.choice(cached_pool)

        return None

    async def build_output(self, ctx, name1, name2, pct, m1, m2):
        tier_label, col_a, col_b, tier_desc = get_tier(pct)
        sname = self.ship_name(name1, name2)
        fact = self.fun_fact(pct)

        img_buf = await build_ship_image(name1, name2, pct, col_a, col_b, m1, m2)
        file = discord.File(img_buf, filename="ship.png")

        return {
            "tier_label": tier_label,
            "tier_desc": tier_desc,
            "ship_name": sname,
            "fact": fact,
            "file": file,
        }

    async def build_error_view(self, title: str, description: str):
        view = discord.ui.LayoutView(timeout=60)
        view.add_item(
            discord.ui.Container(
                discord.ui.TextDisplay(f"# ❌ {title}\n\n{description}")
            )
        )
        return view

    @commands.hybrid_command(name="ship", description="Ship two people and see their love compatibility 💘")
    @app_commands.describe(
        user1="First person — mention, name, or text (leave blank = you)",
        user2="Second person — mention, name, or 'random' (leave blank = random member)",
    )
    async def ship(self, ctx: commands.Context, user1: Optional[str] = None, user2: Optional[str] = None):
        await ctx.defer()

        m1, n1 = await self._resolve_async(ctx, user1)
        m2, n2 = await self._resolve_async(ctx, user2)

        # ── Normalise cases ───────────────────────────────────────────────────
        # No args → ship author with random
        if user1 is None and user2 is None:
            m1, n1 = ctx.author, ctx.author.display_name
            rnd    = self._random_member(ctx, exclude=ctx.author)
            m2, n2 = (rnd, rnd.display_name) if rnd else (ctx.author, ctx.author.display_name)

        # One arg
        elif user2 is None:
            if n1 == "random":
                m1, n1 = ctx.author, ctx.author.display_name
                rnd    = self._random_member(ctx, exclude=ctx.author)
                m2, n2 = (rnd, rnd.display_name) if rnd else (ctx.author, ctx.author.display_name)
            elif m1:
                m2, n2 = m1, n1
                m1, n1 = ctx.author, ctx.author.display_name
            else:
                # plain text second slot
                m2, n2 = None, n1
                m1, n1 = ctx.author, ctx.author.display_name

        # Two args — handle randoms
        else:
            if n1 == "random" and m1 is None:
                rnd    = self._random_member(ctx)
                m1, n1 = (rnd, rnd.display_name) if rnd else (ctx.author, ctx.author.display_name)
            if n2 == "random" and m2 is None:
                rnd    = self._random_member(ctx, exclude=m1)
                m2, n2 = (rnd, rnd.display_name) if rnd else (ctx.author, ctx.author.display_name)

        # Safety
        if (m1 and m1.bot) or (m2 and m2.bot):
            error_view = await self.build_error_view(
                "Can't ship bots",
                "Pick human members for the ship result. 🤖💔",
            )
            return await ctx.send(view=error_view, ephemeral=True)

        name1 = n1 or (m1.display_name if m1 else "Unknown")
        name2 = n2 or (m2.display_name if m2 else "Unknown")
        id1   = str(m1.id) if m1 else name1
        id2   = str(m2.id) if m2 else name2

        pct = self.calc_pct(id1, id2)
        await self._record_ship(
            getattr(ctx.guild, "id", None),
            id1, id2, name1, name2, pct, getattr(ctx.author, "id", 0),
        )
        output = await self.build_output(ctx, name1, name2, pct, m1, m2)
        view = ShipView(
            self,
            ctx,
            m1,
            m2,
            name1,
            name2,
            id1,
            id2,
            pct,
            is_rerolled=False,
        )
        msg = await ctx.send(file=output["file"], view=view)
        view.message = msg

    @commands.hybrid_command(
        name="shipleaderboard",
        description="Show the highest-scoring ships in this server 🏆",
    )
    @app_commands.describe(limit="How many ships to show (1–10)")
    async def shipleaderboard(self, ctx: commands.Context, limit: Optional[int] = 10):
        if not self._mongo_required():
            return await ctx.send(
                "⚠️ Ship leaderboard needs MongoDB. Check the bot MongoDB connection in `bot.py`.",
                ephemeral=True,
            )

        limit = max(1, min(int(limit or 10), 10))
        cursor = self.ship_pairs.find({"guild_id": str(ctx.guild.id) if ctx.guild else ""}).sort(
            [("score", -1), ("times_shipped", -1)]
        ).limit(limit)
        rows = await cursor.to_list(length=limit)

        view = discord.ui.LayoutView(timeout=60)
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay("# 🏆 Ship Leaderboard"))

        if not rows:
            container.add_item(discord.ui.TextDisplay(
                "No ship stats yet. Run `/ship` to start the leaderboard!"
            ))
        else:
            lines = []
            medals = ["🥇", "🥈", "🥉"]
            for i, row in enumerate(rows, 1):
                medal = medals[i - 1] if i <= 3 else f"**{i}.**"
                lines.append(
                    f"{medal} **{discord.utils.escape_markdown(str(row.get('name1', 'Unknown')))} × "
                    f"{discord.utils.escape_markdown(str(row.get('name2', 'Unknown')))}** — "
                    f"**{int(row.get('score', 0))}%** · {int(row.get('times_shipped', 0))} ships"
                )
            container.add_item(discord.ui.TextDisplay("\n".join(lines)))
            container.add_item(discord.ui.TextDisplay(
                "-# Scores are the permanent `/ship` results. Rerolls are temporary and do not change the leaderboard."
            ))

        view.add_item(container)
        await ctx.send(view=view)

    @commands.hybrid_command(
        name="shipstreak",
        description="Show a user's daily ship streak 🔥",
    )
    @app_commands.describe(user="User to check (leave blank = you)")
    async def shipstreak(self, ctx: commands.Context, user: Optional[str] = None):
        if not self._mongo_required():
            return await ctx.send(
                "⚠️ Ship streak needs MongoDB. Check the bot MongoDB connection in `bot.py`.",
                ephemeral=True,
            )

        member, name = self._resolve(ctx, user)
        target = member if member else ctx.author
        display = target.display_name if member else (name or ctx.author.display_name)

        row = await self.ship_users.find_one({
            "guild_id": str(ctx.guild.id) if ctx.guild else "",
            "user_id": str(target.id),
        })

        current = int(row.get("current_streak", 0)) if row else 0
        longest = int(row.get("longest_streak", 0)) if row else 0
        total = int(row.get("total_ships", 0)) if row else 0

        view = discord.ui.LayoutView(timeout=60)
        view.add_item(discord.ui.Container(
            discord.ui.TextDisplay(
                f"# 🔥 {discord.utils.escape_markdown(display)}'s Ship Streak\n\n"
                f"**Current:** {current} day{'s' if current != 1 else ''}\n"
                f"**Best:** {longest} day{'s' if longest != 1 else ''}\n"
                f"**Total ships:** {total}"
            )
        ))
        await ctx.send(view=view)

    @commands.hybrid_command(
        name="duochallenge",
        description="Give any two people a fun relationship-neutral challenge 🎯",
    )
    @app_commands.describe(
        user1="First person — mention, name, or text (leave blank = you)",
        user2="Second person — mention, name, or 'random'",
    )
    async def duochallenge(
        self,
        ctx: commands.Context,
        user1: Optional[str] = None,
        user2: Optional[str] = None,
    ):
        m1, n1 = await self._resolve_async(ctx, user1)
        m2, n2 = await self._resolve_async(ctx, user2)

        # Same friendly resolution rules as /ship, but this feature is explicitly
        # relationship-neutral: friends, siblings, partners, teammates, etc.
        if user1 is None and user2 is None:
            m1, n1 = ctx.author, ctx.author.display_name
            rnd = self._random_member(ctx, exclude=ctx.author)
            m2, n2 = (rnd, rnd.display_name) if rnd else (ctx.author, ctx.author.display_name)
        elif user2 is None:
            if n1 == "random":
                m1, n1 = ctx.author, ctx.author.display_name
                rnd = self._random_member(ctx, exclude=ctx.author)
                m2, n2 = (rnd, rnd.display_name) if rnd else (ctx.author, ctx.author.display_name)
            elif m1:
                m2, n2 = m1, n1
                m1, n1 = ctx.author, ctx.author.display_name
            else:
                m2, n2 = None, n1
                m1, n1 = ctx.author, ctx.author.display_name
        else:
            if n1 == "random" and m1 is None:
                rnd = self._random_member(ctx)
                m1, n1 = (rnd, rnd.display_name) if rnd else (ctx.author, ctx.author.display_name)
            if n2 == "random" and m2 is None:
                rnd = self._random_member(ctx, exclude=m1)
                m2, n2 = (rnd, rnd.display_name) if rnd else (ctx.author, ctx.author.display_name)

        if (m1 and m1.bot) or (m2 and m2.bot):
            view = await self.build_error_view(
                "Can't challenge bots",
                "Pick human members for the challenge. 🤖❌",
            )
            return await ctx.send(view=view, ephemeral=True)

        name1 = n1 or (m1.display_name if m1 else "Unknown")
        name2 = n2 or (m2.display_name if m2 else "Unknown")
        title, challenge = random.choice(DUO_CHALLENGES)

        view = discord.ui.LayoutView(timeout=120)
        container = discord.ui.Container()
        container.add_item(discord.ui.TextDisplay(
            f"# 🎯 Duo Challenge\n"
            f"## {discord.utils.escape_markdown(name1)} × {discord.utils.escape_markdown(name2)}"
        ))
        container.add_item(discord.ui.TextDisplay(
            f"### {title}\n\n{challenge}\n\n"
            "-# No relationship required — friends, siblings, partners, teammates, or randoms can use it."
        ))
        view.add_item(container)
        await ctx.send(view=view)


async def setup(bot):
    await bot.add_cog(Ship(bot))
    logger.debug("Loaded Ship")
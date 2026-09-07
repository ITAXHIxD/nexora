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
TIERS = [
    (100, 100, "💞 SOULMATES",     (255, 100, 180), (255, 20,  120), "Literally made for each other. The universe ships it."),
    (85,  99,  "💖 Perfect Match", (255, 130, 160), (220, 50,  130), "Off-the-charts chemistry. Do they know yet?"),
    (70,  84,  "💕 Great Vibes",   (240, 100, 140), (200, 60,  120), "Strong pull. Something's definitely there."),
    (55,  69,  "💓 Promising",     (210, 140, 160), (180, 80,  130), "Sparks flying. Could go somewhere beautiful."),
    (45,  54,  "💛 Neutral",       (220, 200,  80), (180, 160,  40), "Neither here nor there… yet. Give it time."),
    (30,  44,  "🤍 Lukewarm",      (180, 180, 200), (140, 140, 170), "The vibe is… complicated."),
    (15,  29,  "🖤 Unlikely",      (120, 120, 140), ( 80,  80, 110), "Opposites attract? Not this time."),
    ( 0,  14,  "💔 Disaster",      ( 80,  80,  90), ( 40,  40,  60), "Run. Just run."),
]

FUN_FACTS = [
    "Their star signs are {pct}% compatible.",
    "A fortune teller saw this coming.",
    "Scientists can't explain this result.",
    "The algorithm never lies. Trust it.",
    "Even the bot is rooting for them.",
    "Statistically, this was inevitable.",
    "The multiverse agrees on this one.",
    "Love language match: {pct}% confirmed.",
    "Spotify co-listening sessions incoming.",
    "Side effects may include butterflies.",
]

ROASTS = [
    "Not even the same WiFi network.",
    "They once argued about pineapple on pizza. They still do.",
    "Opposites attract — this is the exception.",
    "Their vibe difference is measurable in light-years.",
]

HYPE = [
    "Someone's about to confess. We can feel it.",
    "The tension is palpable from here.",
    "Bestie-to-lovers arc loading…",
    "The main characters of this server. Obviously.",
]

# ── Duo challenge pool ────────────────────────────────────────────────────────
DUO_CHALLENGES = [
    ("⚡ Sync Check", "Both send the same emoji at the same time."),
    ("🎯 Quick Draw", "Both name a food you would eat right now. No copying."),
    ("🧠 Mind Match", "Count down from 3 and both say a number from 1–10. Same number = success."),
    ("😂 No Laugh", "Send a meme or joke. First person to laugh loses."),
    ("🔤 Letter Lock", "Pick a letter. For 30 seconds, neither person can use a word starting with it."),
    ("🎨 Same Vibe", "Both choose a colour that matches the current vibe. Reveal together."),
    ("🎵 Song Swap", "Each pick one song that fits the other person. Reveal at the same time."),
    ("🤝 Compliment Battle", "Take turns giving genuine compliments. First person to run out loses."),
    ("🕵️ Two Truths", "Each give one true statement and one fake one. The other has to guess."),
    ("⏱️ Speed Round", "You each get 10 seconds to answer the same random question."),
]

# ── Colour helpers ─────────────────────────────────────────────────────────────

def get_tier(pct: int):
    for lo, hi, label, col_a, col_b, desc in TIERS:
        if lo <= pct <= hi:
            return label, col_a, col_b, desc
    return "❓ Unknown", (128,128,128), (64,64,64), "The algorithm is confused."

def lerp_color(a, b, t):
    return tuple(int(a[i] + (b[i]-a[i]) * t) for i in range(3))

def hex_col(rgb): return "#{:02x}{:02x}{:02x}".format(*rgb)

# ── Font ───────────────────────────────────────────────────────────────────────

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

async def fetch_avatar(url: str) -> Optional[Image.Image]:
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(str(url), timeout=aiohttp.ClientTimeout(total=8)) as r:
                if r.status == 200:
                    return Image.open(io.BytesIO(await r.read())).convert("RGBA")
    except Exception as e:
        logger.warning("Avatar download failed: %s", e)
    return None

# ── Main image builder ─────────────────────────────────────────────────────────

async def build_ship_image(
    name1: str, name2: str,
    pct: int,
    col_a: tuple, col_b: tuple,
    member1=None, member2=None,
) -> io.BytesIO:
    W, H = 960, 380
    AVATAR_SIZE = 160

    # ── Background gradient ────────────────────────────────────────────────────
    base = Image.new("RGBA", (W, H))
    bg   = ImageDraw.Draw(base)

    # deep background — darkened mix of both tier colours
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
    # centre heart glow
    for radius in range(80, 20, -10):
        a = int(80 * (1 - radius/80) * (pct/100))
        gd.ellipse([W//2-radius, H//2-radius, W//2+radius, H//2+radius], fill=lerp_color(col_a,col_b,0.5)+(a,))
    base = Image.alpha_composite(base, glow)

    draw = ImageDraw.Draw(base)

    # ── Avatars ────────────────────────────────────────────────────────────────
    # Left avatar
    av1 = await fetch_avatar(member1.display_avatar.url) if member1 else None
    if av1 is None: av1 = text_avatar(name1, AVATAR_SIZE)
    circ1 = make_circle(av1, AVATAR_SIZE)

    # Right avatar
    av2 = await fetch_avatar(member2.display_avatar.url) if member2 else None
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
    draw = ImageDraw.Draw(base)

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
    # outer glow heart
    draw_heart_poly(draw, W//2, H//2 - 10, heart_size+4, (255,255,255), alpha=30)
    draw_heart_poly(draw, W//2, H//2 - 10, heart_size,   heart_col,     alpha=230)

    # corner accent stars (only on high %)
    if pct >= 70:
        for sx, sy in [(60,30),(W-60,30),(60,H-30),(W-60,H-30)]:
            draw_star(draw, sx, sy, 8, (255,255,255), alpha=int(pct*2))

    # ── Percentage text ────────────────────────────────────────────────────────
    f_huge = get_font(88)
    f_med  = get_font(28)
    f_sm   = get_font(20)
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

    # bar labels
    bb = draw.textbbox((0,0), "0%",   font=f_xs); draw.text((bar_x - bb[2]-4,       bar_y-1), "0%",   font=f_xs, fill=(200,200,200,160))
    bb = draw.textbbox((0,0), "100%", font=f_xs); draw.text((bar_x+bar_w+4,          bar_y-1), "100%", font=f_xs, fill=(200,200,200,160))

    # ── Output ─────────────────────────────────────────────────────────────────
    buf = io.BytesIO()
    base.convert("RGB").save(buf, format="PNG", optimize=True)
    buf.seek(0)
    return buf

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

        self.reaction_button.callback = self._react
        self.why_button.callback = self._why
        self.reroll_button.callback = self._reroll
        self.share_button.callback = self._share

        self.actions = discord.ui.ActionRow(
            self.reaction_button,
            self.why_button,
            self.reroll_button,
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
        """(member | None, display_name | None)"""
        if not val: return None, None
        val = val.strip()
        if val.lower() == "random": return None, "random"
        # mention
        m = re.match(r"<@!?(\d+)>$", val)
        if m:
            mem = ctx.guild.get_member(int(m.group(1))) if ctx.guild else None
            if mem: return mem, mem.display_name
        # numeric id
        if val.isdigit() and ctx.guild:
            mem = ctx.guild.get_member(int(val))
            if mem: return mem, mem.display_name
        # name search
        if ctx.guild:
            low = val.lower()
            for mem in ctx.guild.members:
                if not mem.bot and (mem.display_name.lower() == low or mem.name.lower() == low):
                    return mem, mem.display_name
        return None, val

    def _random_member(self, ctx, exclude=None):
        if not ctx.guild: return None
        pool = [m for m in ctx.guild.members if not m.bot and m != exclude]
        return random.choice(pool) if pool else None

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

        m1, n1 = self._resolve(ctx, user1)
        m2, n2 = self._resolve(ctx, user2)

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
        m1, n1 = self._resolve(ctx, user1)
        m2, n2 = self._resolve(ctx, user2)

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
    logger.info("Loaded Ship")
"""
cogs/fun/ship.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Enhanced ship command with:
  • Cinematic gradient ship card image
  • Animated-style glow rings, particle stars, shimmer bar
  • Rich embed with tier badges, ship name, fun facts
  • 🔁 Re-roll and ❤️ Reaction buttons
  • Ships members, plain text names, or "random"
  • Consistent (hash-based) results per pair
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import hashlib
import io
import logging
import math
import os
import random
import re
from datetime import datetime
from typing import Optional, Tuple

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands
from PIL import Image, ImageDraw, ImageFilter, ImageFont

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

# ── View ───────────────────────────────────────────────────────────────────────

class ShipView(discord.ui.View):
    def __init__(self, cog, ctx, member1, member2, name1, name2, id1, id2):
        super().__init__(timeout=120)
        self.cog     = cog
        self.ctx     = ctx
        self.member1 = member1
        self.member2 = member2
        self.name1   = name1
        self.name2   = name2
        self.id1     = id1
        self.id2     = id2
        self.reacts  = set()

    @discord.ui.button(emoji="🔁", label="Re-roll", style=discord.ButtonStyle.grey)
    async def reroll(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # Randomise by adding a salt so each roll differs
        salt = str(random.randint(0, 999999))
        pct  = self.cog.calc_pct(self.id1 + salt, self.id2 + salt)
        embed, file = await self.cog.build_output(
            self.ctx, self.name1, self.name2, pct,
            self.member1, self.member2, rerolled=True
        )
        await interaction.edit_original_response(embed=embed, attachments=[file], view=self)

    @discord.ui.button(emoji="❤️", label="React", style=discord.ButtonStyle.red)
    async def react(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.reacts.add(interaction.user.id)
        button.label = f"❤️ {len(self.reacts)}"
        await interaction.response.edit_message(view=self)

    @discord.ui.button(emoji="🔗", label="Share", style=discord.ButtonStyle.blurple)
    async def share(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message(
            f"💘 **{self.name1} × {self.name2}** have been shipped!\n"
            f"Use `/ship {self.name1} {self.name2}` to see the result!",
            ephemeral=False
        )

# ── Cog ────────────────────────────────────────────────────────────────────────

class Ship(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

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

    async def build_output(self, ctx, name1, name2, pct, m1, m2, rerolled=False):
        tier_label, col_a, col_b, tier_desc = get_tier(pct)
        sname = self.ship_name(name1, name2)
        fact  = self.fun_fact(pct)

        img_buf = await build_ship_image(name1, name2, pct, col_a, col_b, m1, m2)
        file    = discord.File(img_buf, filename="ship.png")

        embed = discord.Embed(
            title=f"💘 {name1}  ×  {name2}",
            color=discord.Color.from_rgb(*lerp_color(col_a, col_b, 0.5)),
            timestamp=datetime.now()
        )
        embed.set_image(url="attachment://ship.png")

        embed.add_field(name="💫 Ship Name",    value=f"**{sname}**",    inline=True)
        embed.add_field(name="📊 Compatibility", value=f"**{pct}%**",    inline=True)
        embed.add_field(name="🏷️ Tier",         value=tier_label,        inline=True)
        embed.add_field(name="✨ Verdict",       value=tier_desc,         inline=False)
        embed.add_field(name="🎲 Fun Fact",      value=f"*{fact}*",       inline=False)

        if rerolled:
            embed.set_footer(text=f"Re-rolled by {ctx.author.display_name} • Results may vary", icon_url=ctx.author.display_avatar.url)
        else:
            embed.set_footer(text=f"Shipped by {ctx.author.display_name} • Results are definitive", icon_url=ctx.author.display_avatar.url)

        return embed, file

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
            return await ctx.send(embed=discord.Embed(description="❌ Can't ship bots!", color=discord.Color.red()), ephemeral=True)

        name1 = n1 or (m1.display_name if m1 else "Unknown")
        name2 = n2 or (m2.display_name if m2 else "Unknown")
        id1   = str(m1.id) if m1 else name1
        id2   = str(m2.id) if m2 else name2

        pct   = self.calc_pct(id1, id2)
        embed, file = await self.build_output(ctx, name1, name2, pct, m1, m2)
        view  = ShipView(self, ctx, m1, m2, name1, name2, id1, id2)
        msg   = await ctx.send(embed=embed, file=file, view=view)


async def setup(bot):
    await bot.add_cog(Ship(bot))
    logger.info("Loaded Ship")
import discord
from discord.ext import commands
from discord import app_commands
import random
import hashlib
from datetime import datetime
import logging
from PIL import Image, ImageDraw, ImageFont
import io
import aiohttp
import math
import os
import re
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class Ship(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

        # Map percentages to emoji
        self.percentage_emojis = {
            (0, 20): "<a:broken_heart:1426882700886802474>",
            (21, 40): "<a:HEART_HEART:1426883262810427422>",
            (41, 49): "<a:Heart:1426883537230893198>",
            (50, 50): "<:heart_heart:1426882982194712718>",
            (51, 60): "<a:Heart:1426883537230893198>",
            (61, 80): "<a:HeartIsHeart:1426883192325017600>",
            (81, 99): "<:gg_heart:1426883051518169290>",
            (100, 100): "<a:heartsg:1426883390040440965>"
        }

        self.messages = {
            (0, 20): [
                "Yikes... Maybe they're better off as enemies? 💔",
                "This ship is sinking... 🚢💦",
                "Not even close... Maybe in another universe? 🌌"
            ],
            (21, 40): [
                "Meh... Just friends? 🤷",
                "There's potential, but not much... 🤔",
                "The spark is barely there... ✨"
            ],
            (41, 49): [
                "Not bad! There's something here... 😊",
                "Could be a good match! 💫",
                "They might have a chance! 🎲"
            ],
            (50, 50): [
                "Halfway there! Sparks are flying 🔥",
                "50%! Things are heating up! 💞"
            ],
            (51, 60): [
                "Getting hotter! Could be a match! 💖",
                "Strong feelings detected! 💫"
            ],
            (61, 80): [
                "Looking good! Strong potential! 💕",
                "This could really work out! 😍",
                "Great chemistry detected! ⚗️✨"
            ],
            (81, 99): [
                "Almost perfect! Love is in the air! 💖",
                "So close to perfection! 💞",
                "Beautiful love story unfolding! 🥰"
            ],
            (100, 100): [
                "Absolutely perfect! Soulmates forever! 💗",
                "100%! True love! Nothing else compares! 💖"
            ]
        }

    # -------------------------
    # Utility & calculation
    # -------------------------
    def calculate_ship_percentage(self, identifier1: str, identifier2: str) -> int:
        """Calculate ship percentage from string identifiers (always strings)."""
        id1, id2 = sorted([str(identifier1), str(identifier2)])
        combined = f"{id1}:{id2}"
        hash_value = hashlib.md5(combined.encode()).hexdigest()
        return int(hash_value[:8], 16) % 101

    def get_emoji_for_percentage(self, percentage: int) -> str:
        for (min_val, max_val), emoji in self.percentage_emojis.items():
            if min_val <= percentage <= max_val:
                return emoji
        return "💫"

    def get_love_message(self, percentage: int) -> str:
        for (min_val, max_val), messages in self.messages.items():
            if min_val <= percentage <= max_val:
                return random.choice(messages)
        return "Love is mysterious... 💫"

    def create_ship_name(self, name1: str, name2: str) -> str:
        mid1 = len(name1) // 2
        mid2 = len(name2) // 2
        return (name1[:mid1] + name2[mid2:]).title()

    def get_color_from_percentage(self, percentage: int) -> tuple:
        if percentage <= 20:
            return (100, 100, 120)
        elif percentage <= 40:
            return (200, 100, 50)
        elif percentage <= 60:
            return (220, 180, 50)
        elif percentage <= 80:
            return (230, 120, 150)
        else:
            return (200, 50, 120)

    def get_font(self, size: int):
        font_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../DejaVuSans-Bold.ttf"))
        try:
            return ImageFont.truetype(font_path, size)
        except Exception:
            return ImageFont.load_default()

    # -------------------------
    # Avatar / image helpers
    # -------------------------
    async def download_avatar(self, url: str) -> Optional[Image.Image]:
        """Download avatar from url; return PIL Image or None on failure."""
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(str(url)) as resp:
                    if resp.status == 200:
                        data = await resp.read()
                        return Image.open(io.BytesIO(data)).convert('RGBA')
        except Exception as e:
            logger.exception("Failed to download avatar: %s", e)
        return None

    def make_circle(self, img: Image.Image, size: int) -> Image.Image:
        img = img.resize((size, size), getattr(Image, "Resampling", Image).LANCZOS)
        mask = Image.new('L', (size, size), 0)
        draw = ImageDraw.Draw(mask)
        draw.ellipse((0, 0, size, size), fill=255)
        output = Image.new('RGBA', (size, size), (0, 0, 0, 0))
        output.paste(img, (0, 0))
        output.putalpha(mask)
        return output

    def draw_heart(self, draw: ImageDraw.Draw, x: int, y: int, size: int, color: tuple):
        points = []
        for angle in range(0, 360, 2):
            rad = math.radians(angle)
            heart_x = size * (16 * math.sin(rad) ** 3)
            heart_y = -size * (13 * math.cos(rad) - 5 * math.cos(2 * rad) - 2 * math.cos(3 * rad) - math.cos(4 * rad))
            points.append((x + heart_x, y + heart_y))
        draw.polygon(points, fill=color)

    def create_text_avatar(self, text: str, size: int = 180) -> Image.Image:
        """Create a colored avatar with text initial"""
        text_hash = hashlib.md5(text.encode()).hexdigest()
        r = int(text_hash[:2], 16)
        g = int(text_hash[2:4], 16)
        b = int(text_hash[4:6], 16)

        img = Image.new('RGBA', (size, size), (r, g, b, 255))
        draw = ImageDraw.Draw(img)

        initial = text[0].upper() if text else "?"
        font = self.get_font(size // 2)

        bbox = draw.textbbox((0, 0), initial, font=font)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        position = ((size - text_width) // 2 - bbox[0], (size - text_height) // 2 - bbox[1])
        draw.text(position, initial, font=font, fill=(255, 255, 255))

        return img

    async def create_ship_image(
        self,
        name1: str,
        name2: str,
        member1: Optional[discord.Member],
        member2: Optional[discord.Member],
        percentage: int
    ) -> io.BytesIO:
        """Create the ship image. We accept member objects optionally but rely on name strings for text."""
        width, height = 900, 350
        bg_color = self.get_color_from_percentage(percentage)
        img = Image.new('RGB', (width, height), bg_color)
        draw = ImageDraw.Draw(img)

        # subtle vertical gradient
        for y in range(height):
            progress = y / height
            r = int(bg_color[0] + (255 - bg_color[0]) * progress * 0.3)
            g = int(bg_color[1] + (255 - bg_color[1]) * progress * 0.3)
            b = int(bg_color[2] + (255 - bg_color[2]) * progress * 0.3)
            draw.line([(0, y), (width, y)], fill=(r, g, b))

        avatar_size = 180

        # avatar1: prefer member1 avatar if present, else text avatar
        avatar1_img = None
        if member1:
            try:
                avatar1_img = await self.download_avatar(member1.display_avatar.url)
            except Exception:
                avatar1_img = None
        if avatar1_img is None:
            avatar1_img = self.create_text_avatar(name1, avatar_size)

        circle1 = self.make_circle(avatar1_img, avatar_size)
        border_size = avatar_size + 10
        border = Image.new('RGBA', (border_size, border_size), (0, 0, 0, 0))
        border_draw = ImageDraw.Draw(border)
        border_draw.ellipse((0, 0, border_size, border_size), fill=(255, 255, 255, 255))
        img.paste(border, (70 - 5, 85 - 5), border)
        img.paste(circle1, (70, 85), circle1)

        # avatar2: prefer member2 avatar if present, else text avatar
        avatar2_img = None
        if member2:
            try:
                avatar2_img = await self.download_avatar(member2.display_avatar.url)
            except Exception:
                avatar2_img = None
        if avatar2_img is None:
            avatar2_img = self.create_text_avatar(name2, avatar_size)

        circle2 = self.make_circle(avatar2_img, avatar_size)
        border2 = Image.new('RGBA', (border_size, border_size), (0, 0, 0, 0))
        border_draw2 = ImageDraw.Draw(border2)
        border_draw2.ellipse((0, 0, border_size, border_size), fill=(255, 255, 255, 255))
        img.paste(border2, (650 - 5, 85 - 5), border2)
        img.paste(circle2, (650, 85), circle2)

        # heart and percentage text
        heart_size = 5 + int(percentage * 0.15)
        self.draw_heart(draw, width // 2, height // 2, heart_size, (255, 100, 150))

        font_large = self.get_font(100)
        font_small = self.get_font(42)

        percentage_text = f"{percentage}%"
        bbox = draw.textbbox((0, 0), percentage_text, font=font_large)
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        text_x = (width - text_width) // 2
        text_y = (height - text_height) // 2 - 20
        for dx in range(-3, 4):
            for dy in range(-3, 4):
                if dx or dy:
                    draw.text((text_x + dx, text_y + dy), percentage_text, font=font_large, fill=(0, 0, 0, 180))
        draw.text((text_x, text_y), percentage_text, font=font_large, fill=(255, 255, 255))

        # names
        display_name_1 = (member1.display_name if member1 else name1)[:12]
        display_name_2 = (member2.display_name if member2 else name2)[:12]

        bbox1 = draw.textbbox((0, 0), display_name_1, font=font_small)
        bbox2 = draw.textbbox((0, 0), display_name_2, font=font_small)
        name1_width = bbox1[2] - bbox1[0]
        name2_width = bbox2[2] - bbox2[0]
        name1_x = 160 - name1_width // 2
        name2_x = 740 - name2_width // 2
        name_y = 285
        for dx in range(-2, 3):
            for dy in range(-2, 3):
                if dx or dy:
                    draw.text((name1_x + dx, name_y + dy), display_name_1, font=font_small, fill=(0, 0, 0, 180))
                    draw.text((name2_x + dx, name_y + dy), display_name_2, font=font_small, fill=(0, 0, 0, 180))
        draw.text((name1_x, name_y), display_name_1, font=font_small, fill=(255, 255, 255))
        draw.text((name2_x, name_y), display_name_2, font=font_small, fill=(255, 255, 255))

        # sparkles for high %
        if percentage >= 80:
            sparkle_positions = [(150, 50), (750, 50), (150, 300), (750, 300)]
            for pos in sparkle_positions:
                draw.line([(pos[0] - 10, pos[1]), (pos[0] + 10, pos[1])], fill=(255, 255, 255), width=3)
                draw.line([(pos[0], pos[1] - 10), (pos[0], pos[1] + 10)], fill=(255, 255, 255), width=3)

        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer

    # -------------------------
    # Helpers for resolving input
    # -------------------------
    def _parse_member_or_text(self, ctx: commands.Context, value: Optional[str]) -> Tuple[Optional[discord.Member], Optional[str]]:
        """
        Try to resolve `value` to a Member in the guild.
        Returns (member_or_None, text_or_None).
        - If value is None: return (None, None)
        - If value is a mention or ID or exact name/nick -> return (Member, Member.display_name)
        - Otherwise return (None, original_string)
        Special: if value == "random" (case-insensitive) -> returns (None, "random")
        """
        if value is None:
            return None, None

        value = value.strip()
        if value.lower() == "random":
            return None, "random"

        # mention like <@!123> or <@123>
        mention_match = re.match(r"<@!?(\d+)>$", value)
        if mention_match:
            m_id = int(mention_match.group(1))
            member = ctx.guild.get_member(m_id) if ctx.guild else None
            if member:
                return member, member.display_name

        # pure ID
        if value.isdigit():
            member = ctx.guild.get_member(int(value)) if ctx.guild else None
            if member:
                return member, member.display_name

        # try exact name or nick (case-insensitive)
        lower = value.lower()
        if ctx.guild:
            for m in ctx.guild.members:
                if m.bot:
                    continue
                if m.display_name.lower() == lower or m.name.lower() == lower:
                    return m, m.display_name

        # not found as a Member -> treat as plain text
        return None, value

    def _get_random_member(self, ctx: commands.Context) -> Optional[discord.Member]:
        if not ctx.guild:
            return None
        members = [m for m in ctx.guild.members if not m.bot and m != ctx.author]
        return random.choice(members) if members else None

    # -------------------------
    # Command
    # -------------------------
    @commands.hybrid_command(name="ship", description="Ship two users together and see their love compatibility!")
    @app_commands.describe(
        user1="First user to ship (mention, ID, name, or plain text). Leave empty to default to you.",
        user2="Second user to ship (mention, ID, name, or plain text). Leave empty to pick a random member.",
    )
    async def ship(
        self,
        ctx: commands.Context,
        user1: Optional[str] = None,
        user2: Optional[str] = None
    ):
        await ctx.defer()

        # Resolve inputs
        member1, name1_txt = self._parse_member_or_text(ctx, user1)
        member2, name2_txt = self._parse_member_or_text(ctx, user2)

        # CASE: no args -> ship author with random member
        if (member1 is None and name1_txt is None) and (member2 is None and name2_txt is None):
            rand = self._get_random_member(ctx)
            member1 = ctx.author
            member2 = rand or ctx.author
            name1_txt = None
            name2_txt = None

        # If only one arg provided (user1 present)
        elif (member2 is None and name2_txt is None):
            # if user1 was "random"
            if name1_txt == "random":
                rand = self._get_random_member(ctx)
                member1 = ctx.author
                member2 = rand or ctx.author
                name1_txt = None
                name2_txt = None
            else:
                # if user1 resolved to member -> ship author with that member
                if member1:
                    member2 = member1
                    member1 = ctx.author
                    name2_txt = None
                else:
                    # user1 is plain text -> ship author with that text
                    member1 = ctx.author
                    name2_txt = name1_txt
                    name1_txt = None
                    member2 = None

        # If only second arg provided (unlikely since it's positional), handle symmetry:
        elif (member1 is None and name1_txt is None):
            if name2_txt == "random":
                rand = self._get_random_member(ctx)
                member1 = ctx.author
                member2 = rand or ctx.author
                name1_txt = None
                name2_txt = None
            else:
                if member2:
                    # ship author with member2
                    member1 = ctx.author
                    name1_txt = None
                else:
                    # ship author with the text provided in user2
                    member1 = ctx.author
                    name1_txt = None
                    # name2_txt remains text

        # If both provided: keep them as-is
        # (member1/member2 may be Member or None, and name1_txt/name2_txt may be text or "random")
        # Handle any "random" tokens on either slot
        if name1_txt == "random" and (member1 is None):
            rand = self._get_random_member(ctx)
            member1 = rand or ctx.author
            name1_txt = None
        if name2_txt == "random" and (member2 is None):
            rand = self._get_random_member(ctx)
            member2 = rand or ctx.author
            name2_txt = None

        # Final composed display names and hashing identifiers
        final_name1 = member1.display_name if member1 else (name1_txt or "Unknown")
        final_name2 = member2.display_name if member2 else (name2_txt or "Unknown")

        # Prevent shipping bots only if either resolved member is a bot
        if (member1 and member1.bot) or (member2 and member2.bot):
            await ctx.send("❌ Can't ship bots!", ephemeral=True)
            return

        # stable ids for hashing
        id1 = str(member1.id) if member1 else final_name1
        id2 = str(member2.id) if member2 else final_name2

        percentage = self.calculate_ship_percentage(id1, id2)
        ship_name = self.create_ship_name(final_name1, final_name2)
        message = self.get_love_message(percentage)
        emoji = self.get_emoji_for_percentage(percentage)

        # create the image using name strings and optional member objects for avatars
        try:
            ship_image = await self.create_ship_image(final_name1, final_name2, member1, member2, percentage)
        except Exception as e:
            logger.exception("Failed to create ship image: %s", e)
            await ctx.send("❌ Failed to generate ship image.", ephemeral=True)
            return

        file = discord.File(ship_image, filename="ship.png")
        color = self.get_color_from_percentage(percentage)
        embed_title = f"{final_name1} {emoji} {final_name2}"

        embed = discord.Embed(
            title=embed_title,
            description=f"**{ship_name}**\n{message}",
            color=discord.Color.from_rgb(*color),
            timestamp=datetime.now()
        )
        embed.set_image(url="attachment://ship.png")
        embed.set_footer(text=f"Shipped by {ctx.author.display_name}", icon_url=ctx.author.display_avatar.url)

        await ctx.send(embed=embed, file=file)


async def setup(bot):
    await bot.add_cog(Ship(bot))

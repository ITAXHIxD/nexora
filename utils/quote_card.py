"""
utils/quote_card.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
High-fidelity Quote Card Generator for Nexora using Pillow (PIL).
Inspired by the "Make it a Quote" dark atmospheric aesthetic:
  • High-quality TrueType font selection (Segoe UI / Arial / DejaVu Sans).
  • Pixel-measured text wrapping and dynamic vertical centering.
  • Atmospheric horizontal avatar fade into deep dark charcoal background.
  • Clean typography, crisp attribution, and discreet branding watermark.
  • Zero unnecessary borders, no blurry stretching, and no redundant elements.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import io
import logging
import os
from typing import List, Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

logger = logging.getLogger(__name__)

# Primary font candidates in priority order
BOLD_FONTS = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DejaVuSans-Bold.ttf"),
]

REGULAR_FONTS = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DejaVuSans-Bold.ttf"),
]


def _get_font(size: int = 24, bold: bool = False) -> ImageFont.FreeTypeFont:
    """Load the best available TrueType font at the specified size."""
    candidates = BOLD_FONTS if bold else REGULAR_FONTS
    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default(size=size)


def _wrap_text_pixels(
    text: str, font: ImageFont.FreeTypeFont, max_width_px: int, draw: ImageDraw.ImageDraw
) -> List[str]:
    """Wrap text lines based on exact rendered pixel width."""
    lines: List[str] = []
    paragraphs = text.strip().split("\n")
    for para in paragraphs:
        words = para.strip().split()
        if not words:
            lines.append("")
            continue
        curr_line: List[str] = []
        for word in words:
            test_line = " ".join(curr_line + [word])
            bbox = draw.textbbox((0, 0), test_line, font=font)
            w = bbox[2] - bbox[0]
            if w <= max_width_px:
                curr_line.append(word)
            else:
                if curr_line:
                    lines.append(" ".join(curr_line))
                    curr_line = [word]
                else:
                    lines.append(word)
                    curr_line = []
        if curr_line:
            lines.append(" ".join(curr_line))
    return lines


def generate_quote_card(
    author_name: str,
    author_handle: str,
    text: str,
    avatar_bytes: Optional[bytes] = None,
    channel_name: str = "",
    timestamp_str: str = "",
) -> Optional[io.BytesIO]:
    """
    Generate an atmospheric, dark-themed quote card for text-only quotes.
    Returns io.BytesIO containing optimized PNG bytes, or None on failure.
    """
    try:
        clean_text = (text or "").strip()
        if not clean_text:
            clean_text = "..."

        width = 960
        left_w = 380
        right_w = width - left_w - 60  # ~520px content area
        text_x = left_w + 30

        # Adaptive typography sizing based on length
        char_len = len(clean_text)
        if char_len <= 80:
            quote_size = 32
            line_spacing = 10
        elif char_len <= 220:
            quote_size = 26
            line_spacing = 8
        else:
            quote_size = 22
            line_spacing = 6

        font_quote = _get_font(quote_size, bold=False)
        font_author = _get_font(21, bold=True)
        font_handle = _get_font(15, bold=False)
        font_meta = _get_font(12, bold=False)

        # Measure text with a dummy canvas
        dummy_img = Image.new("RGBA", (10, 10))
        dummy_draw = ImageDraw.Draw(dummy_img)
        lines = _wrap_text_pixels(clean_text, font_quote, right_w, dummy_draw)

        # Limit lines to prevent overflow on massive messages
        if len(lines) > 8:
            lines = lines[:8]
            lines[-1] = lines[-1].rstrip("., ") + "…"

        # Measure line heights
        line_heights: List[int] = []
        for line in lines:
            if not line:
                line_heights.append(quote_size // 2)
            else:
                bbox = dummy_draw.textbbox((0, 0), line, font=font_quote)
                line_heights.append(max(quote_size, bbox[3] - bbox[1]))

        total_quote_h = sum(line_heights) + max(0, len(lines) - 1) * line_spacing
        author_block_h = 24 + 4 + 18  # Name (24) + gap (4) + handle (18)
        gap = 22
        content_total_h = total_quote_h + gap + author_block_h

        # Dynamic card height with comfortable margins
        card_h = max(340, min(560, content_total_h + 100))

        # Deep, sleek dark background (charcoal-black #0b0c10)
        card = Image.new("RGBA", (width, card_h), (11, 12, 16, 255))

        # Left section: Atmospheric avatar blend
        if avatar_bytes:
            try:
                with Image.open(io.BytesIO(avatar_bytes)) as av_raw:
                    av_rgb = av_raw.convert("RGBA")
                    src_w, src_h = av_rgb.size
                    scale = max(left_w / src_w, card_h / src_h)
                    new_w = int(src_w * scale)
                    new_h = int(src_h * scale)
                    av_resized = av_rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)

                    # Center crop to left_w x card_h
                    crop_x = max(0, (new_w - left_w) // 2)
                    crop_y = max(0, (new_h - card_h) // 2)
                    av_cropped = av_resized.crop((crop_x, crop_y, crop_x + left_w, crop_y + card_h))

                    # Cinematic contrast & subtle tone
                    enhancer = ImageEnhance.Brightness(av_cropped)
                    av_cropped = enhancer.enhance(0.90)

                    # Smooth horizontal alpha gradient mask fading out into pure dark
                    mask = Image.new("L", (left_w, card_h), 255)
                    m_draw = ImageDraw.Draw(mask)
                    fade_start = int(left_w * 0.40)
                    fade_range = left_w - fade_start
                    for x in range(fade_start, left_w):
                        pct = (x - fade_start) / float(fade_range)
                        alpha = int(255 * (1.0 - (pct ** 1.35)))
                        m_draw.line([(x, 0), (x, card_h)], fill=max(0, min(255, alpha)))

                    card.paste(av_cropped, (0, 0), mask)
            except Exception as av_err:
                logger.debug("Avatar processing failed for quote card: %s", av_err)

        draw = ImageDraw.Draw(card)

        # Discreet 1px card boundary
        draw.rounded_rectangle(
            [(0, 0), (width - 1, card_h - 1)],
            radius=12,
            outline=(34, 37, 46, 255),
            width=1,
        )

        # Position right content vertically centered
        start_y = max(38, (card_h - content_total_h) // 2 - 8)

        # Draw quote text lines
        curr_y = start_y
        for i, line in enumerate(lines):
            if line:
                draw.text((text_x, curr_y), line, fill=(245, 246, 250, 255), font=font_quote)
                curr_y += line_heights[i] + line_spacing
            else:
                curr_y += quote_size // 2 + line_spacing

        # Draw author attribution
        curr_y += gap
        author_display = f"- {author_name}" if author_name else "- Anonymous"
        draw.text((text_x, curr_y), author_display, fill=(225, 228, 235, 255), font=font_author)

        curr_y += 24 + 4
        handle_display = f"@{author_handle}" if author_handle else ""
        if handle_display:
            draw.text((text_x, curr_y), handle_display, fill=(132, 138, 152, 255), font=font_handle)

        # Watermark bottom-right
        draw.text(
            (width - 130, card_h - 26),
            "NEXORA Quotes",
            fill=(65, 70, 85, 255),
            font=font_meta,
        )

        # Channel & Date context bottom-left of text column
        meta_items = []
        if channel_name:
            meta_items.append(f"#{channel_name}")
        if timestamp_str:
            meta_items.append(timestamp_str)
        if meta_items:
            draw.text(
                (text_x, card_h - 26),
                " • ".join(meta_items),
                fill=(65, 70, 85, 255),
                font=font_meta,
            )

        out = io.BytesIO()
        card.save(out, format="PNG", optimize=True)
        out.seek(0)
        return out

    except Exception as exc:
        logger.error("Failed to generate quote card image: %s", exc, exc_info=True)
        return None

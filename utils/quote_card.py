"""
utils/quote_card.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
High-fidelity Quote Card Generator for Nexora using Pillow (PIL).
Inspired by the "Make it a Quote" dark atmospheric aesthetic,
elevated with smooth gradients, smart typography, and cinematic fading.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import io
import logging
import textwrap
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

CARD_WIDTH = 1050
MIN_HEIGHT = 440
MAX_HEIGHT = 650


def _load_font(size: int) -> ImageFont.FreeTypeFont:
    """Load default FreeType font at specified size."""
    try:
        return ImageFont.load_default(size=size)
    except Exception:
        return ImageFont.load_default()


def _wrap_text(text: str, max_width_chars: int = 34) -> str:
    """Cleanly wrap text into lines with word boundaries."""
    lines = []
    paragraphs = text.strip().split("\n")
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        wrapped = textwrap.wrap(para, width=max_width_chars)
        lines.extend(wrapped)
        if len(lines) >= 8:
            break
    if len(lines) > 8:
        lines = lines[:8]
        lines[-1] = lines[-1].rstrip(". ") + "…"
    return "\n".join(lines)


def generate_quote_card(
    author_name: str,
    author_handle: str,
    text: str,
    avatar_bytes: Optional[bytes] = None,
    image_bytes: Optional[bytes] = None,
    channel_name: str = "",
    timestamp_str: str = "",
) -> Optional[io.BytesIO]:
    """
    Generate a sleek, dark atmospheric quote card resembling the reference screenshot.
    Returns io.BytesIO containing PNG bytes, or None on failure.
    """
    try:
        clean_text = (text or "").strip()
        if not clean_text:
            clean_text = "[Shared an attachment]"

        # Wrap text and calculate dimensions
        wrapped_text = _wrap_text(clean_text, max_width_chars=32)
        line_count = len(wrapped_text.split("\n"))

        # Dynamic card height
        card_height = max(MIN_HEIGHT, min(MAX_HEIGHT, 340 + line_count * 38))

        # Base background
        card = Image.new("RGBA", (CARD_WIDTH, card_height), (12, 13, 18, 255))

        # Background visual: Prefer attached image if present, else author avatar
        visual_bytes = image_bytes or avatar_bytes
        left_width = 460
        if visual_bytes:
            try:
                with Image.open(io.BytesIO(visual_bytes)) as src_img:
                    src_rgb = src_img.convert("RGBA")

                    # If it's an avatar and not an attachment, we can also give it a subtle circular accent
                    # Fit and crop to fill left_width x card_height
                    aspect_src = src_rgb.width / src_rgb.height
                    target_aspect = left_width / card_height

                    if aspect_src > target_aspect:
                        # Wider than target
                        new_h = card_height
                        new_w = int(card_height * aspect_src)
                    else:
                        new_w = left_width
                        new_h = int(left_width / aspect_src)

                    resized = src_rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)
                    # Center crop
                    x_offset = max(0, (new_w - left_width) // 2)
                    y_offset = max(0, (new_h - card_height) // 2)
                    cropped = resized.crop((x_offset, y_offset, x_offset + left_width, y_offset + card_height))

                    # Cinematic soft contrast enhancement
                    enhancer = ImageEnhance.Brightness(cropped)
                    cropped = enhancer.enhance(0.92)

                    # Smooth horizontal alpha mask (left is visible, right fades into black)
                    mask = Image.new("L", (left_width, card_height), 255)
                    mask_draw = ImageDraw.Draw(mask)
                    fade_start = int(left_width * 0.45)
                    fade_range = left_width - fade_start
                    for x in range(fade_start, left_width):
                        alpha = int(255 * (1.0 - ((x - fade_start) / float(fade_range)) ** 1.3))
                        mask_draw.line([(x, 0), (x, card_height)], fill=max(0, min(255, alpha)))

                    # Paste visual with mask
                    card.paste(cropped, (0, 0), mask)
            except Exception as img_err:
                logger.debug("Could not process visual bytes for quote card: %s", img_err)

        # Draw card border and details
        draw = ImageDraw.Draw(card)

        # Outer subtle rounded border
        draw.rounded_rectangle(
            [(1, 1), (CARD_WIDTH - 2, card_height - 2)],
            radius=16,
            outline=(38, 42, 54, 255),
            width=2,
        )

        # Subtle elegant watermark quote mark behind text
        quote_mark_font = _load_font(120)
        draw.text((left_width - 20, 30), "“", fill=(88, 101, 242, 35), font=quote_mark_font)

        # Font configuration
        font_quote = _load_font(34 if line_count <= 4 else 28)
        font_author = _load_font(23)
        font_handle = _load_font(17)
        font_watermark = _load_font(13)

        # Right side content layout
        text_x = left_width + 15
        text_y = 65

        # Render Quote Text
        draw.text(
            (text_x, text_y),
            wrapped_text,
            fill=(245, 246, 250, 255),
            font=font_quote,
            spacing=10,
        )

        # Calculate bounding box of quote text to position attribution
        bbox = draw.textbbox((text_x, text_y), wrapped_text, font=font_quote, spacing=10)
        author_y = bbox[3] + 30

        # Author Name & Handle
        display_author = f"- {author_name}" if author_name else "- Anonymous"
        draw.text((text_x, author_y), display_author, fill=(235, 237, 242, 255), font=font_author)

        handle_display = f"@{author_handle}" if author_handle else ""
        if handle_display:
            draw.text(
                (text_x, author_y + 30),
                handle_display,
                fill=(140, 145, 160, 255),
                font=font_handle,
            )

        # Footer Watermark (Bottom right)
        watermark_text = "NEXORA QUOTES"
        draw.text(
            (CARD_WIDTH - 150, card_height - 30),
            watermark_text,
            fill=(80, 85, 100, 200),
            font=font_watermark,
        )

        # Footer Channel / Date context (Bottom left of text area)
        footer_parts = []
        if channel_name:
            footer_parts.append(f"#{channel_name}")
        if timestamp_str:
            footer_parts.append(timestamp_str)
        if footer_parts:
            context_text = " • ".join(footer_parts)
            draw.text(
                (text_x, card_height - 30),
                context_text,
                fill=(75, 80, 95, 200),
                font=font_watermark,
            )

        out = io.BytesIO()
        card.save(out, format="PNG", optimize=True)
        out.seek(0)
        return out

    except Exception as exc:
        logger.error("Failed to generate quote card image: %s", exc, exc_info=True)
        return None

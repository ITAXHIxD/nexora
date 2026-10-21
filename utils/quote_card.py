"""
utils/quote_card.py
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
High-fidelity Quote Card Generator for Nexora using Pillow (PIL).
Inspired by the "Make it a Quote" dark atmospheric aesthetic:
  • High-quality TrueType font selection (Segoe UI / Arial / DejaVu Sans).
  • Pixel-measured text wrapping and dynamic vertical centering.
  • Atmospheric horizontal avatar fade into deep dark charcoal background.
  • compose_image_quote(): Intelligent composition for image-based quotes
    preserving full aspect ratio, clarity, and handling portrait/landscape/square.
  • Zero distortion, no blurry stretching, and no redundant borders.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

import io
import logging
import os
from typing import List, Optional

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

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
    Uses standard 16:9 proportions (960x540) matching modern Discord quote cards.
    Returns io.BytesIO containing optimized PNG bytes, or None on failure.
    """
    try:
        clean_text = (text or "").strip()
        if not clean_text:
            clean_text = "..."

        width = 960
        card_h = 540  # Standard 16:9 aspect ratio
        left_w = 430  # Prominent portrait avatar area
        right_w = width - left_w - 60  # ~470px content area
        text_x = left_w + 30

        # Adaptive typography sizing based on length
        char_len = len(clean_text)
        if char_len <= 90:
            quote_size = 32
            line_spacing = 12
        elif char_len <= 220:
            quote_size = 28
            line_spacing = 10
        else:
            quote_size = 23
            line_spacing = 7

        font_quote = _get_font(quote_size, bold=False)
        font_author = _get_font(22, bold=True)
        font_handle = _get_font(16, bold=False)
        font_meta = _get_font(11, bold=False)

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

        # Dynamic height expansion only if content genuinely exceeds 16:9 canvas
        if content_total_h + 100 > card_h:
            card_h = min(680, content_total_h + 100)

        # Deep, sleek dark background (charcoal-black #0b0c10)
        card = Image.new("RGBA", (width, card_h), (11, 12, 16, 255))

        # Left section: Atmospheric avatar blend with full vertical presence
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

                    # Cinematic contrast & tone
                    enhancer = ImageEnhance.Brightness(av_cropped)
                    av_cropped = enhancer.enhance(0.92)

                    # Smooth horizontal alpha gradient mask fading out into pure dark
                    mask = Image.new("L", (left_w, card_h), 255)
                    m_draw = ImageDraw.Draw(mask)
                    fade_start = int(left_w * 0.40)
                    fade_range = left_w - fade_start
                    for x in range(fade_start, left_w):
                        pct = (x - fade_start) / float(fade_range)
                        alpha = int(255 * (1.0 - (pct ** 1.4)))
                        m_draw.line([(x, 0), (x, card_h)], fill=max(0, min(255, alpha)))

                    card.paste(av_cropped, (0, 0), mask)
            except Exception as av_err:
                logger.debug("Avatar processing failed for quote card: %s", av_err)

        draw = ImageDraw.Draw(card)

        # Position right content vertically centered in the generous 16:9 canvas
        start_y = max(38, (card_h - content_total_h) // 2)

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
        draw.text((text_x, curr_y), author_display, fill=(228, 230, 238, 255), font=font_author)

        curr_y += 24 + 4
        handle_display = f"@{author_handle}" if author_handle else ""
        if handle_display:
            draw.text((text_x, curr_y), handle_display, fill=(135, 140, 155, 255), font=font_handle)

        # Discreet branding watermark bottom-right (clean, no bottom-left clutter)
        wm_text = "NEXORA Quotes"
        wm_bbox = draw.textbbox((0, 0), wm_text, font=font_meta)
        wm_w = wm_bbox[2] - wm_bbox[0]
        wm_h = wm_bbox[3] - wm_bbox[1]
        draw.text(
            (width - wm_w - 16, card_h - wm_h - 14),
            wm_text,
            fill=(70, 75, 90, 255),
            font=font_meta,
        )

        # Apply rounded corner alpha mask to eliminate sharp corners
        corner_mask = Image.new("L", (width, card_h), 0)
        c_draw = ImageDraw.Draw(corner_mask)
        c_draw.rounded_rectangle(
            [(0, 0), (width - 1, card_h - 1)],
            radius=12,
            fill=255,
        )
        card.putalpha(corner_mask)

        # Clean 1px perimeter border
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle(
            [(0, 0), (width - 1, card_h - 1)],
            radius=12,
            outline=(36, 40, 52, 255),
            width=1,
        )

        out = io.BytesIO()
        card.save(out, format="PNG", optimize=True)
        out.seek(0)
        return out

    except Exception as exc:
        logger.error("Failed to generate quote card image: %s", exc, exc_info=True)
        return None


def compose_image_quote(
    image_bytes: bytes,
    target_max_w: int = 960,
    target_max_h: int = 720,
) -> Optional[io.BytesIO]:
    """
    Intelligently compose an image-based quote into a polished Discord card.
    Preserves 100% of the image's original aspect ratio, clarity, and content.
    Returns io.BytesIO PNG bytes, or None for animated GIFs / unsupported formats.
    """
    if not image_bytes:
        return None
    try:
        Image.MAX_IMAGE_PIXELS = 50_000_000
        with Image.open(io.BytesIO(image_bytes)) as src_raw:
            # Check animated images: return None so Discord plays the animated GIF natively
            if getattr(src_raw, "is_animated", False) or getattr(src_raw, "n_frames", 1) > 1:
                return None

            src_rgb = src_raw.convert("RGBA")
            orig_w, orig_h = src_rgb.size
            if orig_w <= 0 or orig_h <= 0 or orig_w > 8000 or orig_h > 8000:
                return None

            aspect = orig_w / float(orig_h)

            # Fit scaling: preserve aspect ratio, never distort or stretch
            scale = min(target_max_w / float(orig_w), target_max_h / float(orig_h))
            # For small images, avoid blurry over-upscaling
            if orig_w < target_max_w and orig_h < target_max_h:
                scale = min(1.35, scale)

            new_w = max(1, int(orig_w * scale))
            new_h = max(1, int(orig_h * scale))
            resized = src_rgb.resize((new_w, new_h), Image.Resampling.LANCZOS)

            # Composition decision based on aspect ratio:
            # For landscape, square, and standard portrait (aspect >= 0.60):
            # The original image is prominent and fills the embed width directly.
            # Avoid redundant padding, nested borders, and awkward margins.
            if aspect >= 0.60:
                canvas_w = new_w
                canvas_h = new_h
                canvas = resized
            else:
                # Very narrow / extreme tall image (aspect < 0.60):
                # Provide a balanced canvas width with an atmospheric ambient blur
                # background so it doesn't look like an awkwardly spindly strip in Discord.
                canvas_w = max(new_w, min(720, int(new_h * 0.95)))
                canvas_h = new_h
                canvas = Image.new("RGBA", (canvas_w, canvas_h), (11, 12, 16, 255))

                # Ambient blurred background
                bg_scale = max(canvas_w / float(orig_w), canvas_h / float(orig_h))
                bg_w = max(1, int(orig_w * bg_scale))
                bg_h = max(1, int(orig_h * bg_scale))
                bg_resized = src_rgb.resize((bg_w, bg_h), Image.Resampling.BILINEAR)
                crop_x = max(0, (bg_w - canvas_w) // 2)
                crop_y = max(0, (bg_h - canvas_h) // 2)
                bg_cropped = bg_resized.crop((crop_x, crop_y, crop_x + canvas_w, crop_y + canvas_h))
                bg_blur = bg_cropped.filter(ImageFilter.GaussianBlur(28))

                # Dark dimming layer over background blur
                dim = Image.new("RGBA", (canvas_w, canvas_h), (8, 9, 12, 185))
                bg_blur.paste(dim, (0, 0), dim)
                canvas.paste(bg_blur, (0, 0))

                # Center foreground image cleanly
                fg_x = (canvas_w - new_w) // 2
                fg_y = (canvas_h - new_h) // 2
                canvas.paste(resized, (fg_x, fg_y), resized if resized.mode == "RGBA" else None)

            # Apply rounded corner mask to eliminate sharp corners
            if canvas.mode != "RGBA":
                canvas = canvas.convert("RGBA")
            corner_mask = Image.new("L", (canvas.width, canvas.height), 0)
            c_draw = ImageDraw.Draw(corner_mask)
            c_draw.rounded_rectangle(
                [(0, 0), (canvas.width - 1, canvas.height - 1)],
                radius=10,
                fill=255,
            )
            canvas.putalpha(corner_mask)

            # Draw clean rounded border along the perimeter
            draw = ImageDraw.Draw(canvas)
            draw.rounded_rectangle(
                [(0, 0), (canvas.width - 1, canvas.height - 1)],
                radius=10,
                outline=(42, 45, 56, 255),
                width=1,
            )

            # Subtle tasteful NEXORA branding watermark in bottom-right corner
            font_wm = _get_font(11, bold=False)
            wm_text = "NEXORA Quotes"
            wm_bbox = draw.textbbox((0, 0), wm_text, font=font_wm)
            wm_w = wm_bbox[2] - wm_bbox[0]
            wm_h = wm_bbox[3] - wm_bbox[1]
            wm_x = canvas.width - wm_w - 14
            wm_y = canvas.height - wm_h - 10

            # Soft shadow + subtle silver text for contrast on any background
            draw.text((wm_x + 1, wm_y + 1), wm_text, fill=(0, 0, 0, 150), font=font_wm)
            draw.text((wm_x, wm_y), wm_text, fill=(215, 220, 235, 190), font=font_wm)

            out = io.BytesIO()
            # If canvas exceeds Discord 8MB limit, compress safely to JPEG
            canvas.save(out, format="PNG", optimize=True)
            if out.getbuffer().nbytes > 8 * 1024 * 1024:
                out = io.BytesIO()
                canvas.convert("RGB").save(out, format="JPEG", quality=90, optimize=True)

            out.seek(0)
            return out

    except Exception as exc:
        logger.error("Failed to compose image quote card: %s", exc, exc_info=True)
        return None

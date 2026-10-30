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
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

logger = logging.getLogger(__name__)

# Primary font candidates in priority order
EMOJI_FONTS = [
    "C:/Windows/Fonts/seguiemj.ttf",
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DejaVuSans.ttf"),
]

BOLD_FONTS = [
    "C:/Windows/Fonts/segoeuib.ttf",
    "C:/Windows/Fonts/arialbd.ttf",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DejaVuSans-Bold.ttf"),
]

ITALIC_FONTS = [
    "C:/Windows/Fonts/segoeuii.ttf",
    "C:/Windows/Fonts/ariali.ttf",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DejaVuSans-Oblique.ttf"),
]

REGULAR_FONTS = [
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "DejaVuSans.ttf"),
]


def _get_font(
    size: int = 24,
    bold: bool = False,
    italic: bool = False,
    emoji: bool = False,
) -> ImageFont.FreeTypeFont:
    """Load the best available TrueType font at the specified size."""
    if emoji:
        candidates = EMOJI_FONTS
    elif italic:
        candidates = ITALIC_FONTS
    elif bold:
        candidates = BOLD_FONTS
    else:
        candidates = REGULAR_FONTS

    for path in candidates:
        if os.path.exists(path):
            try:
                return ImageFont.truetype(path, size)
            except Exception:
                pass
    return ImageFont.load_default(size=size)


def _is_color_font(font: ImageFont.FreeTypeFont) -> bool:
    """Check if font is a Windows color emoji font (seguiemj)."""
    font_path = getattr(font, "path", "")
    if isinstance(font_path, str) and "seguiemj" in font_path.lower():
        return True
    return False


CUSTOM_EMOJI_RE = re.compile(r"<(a)?:([a-zA-Z0-9_~]+):(\d+)>")
URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)


def strip_urls_from_text(text: str) -> str:
    """Ignore and strip URLs (including gif, image, and attachment links) from quote text."""
    if not text:
        return ""
    no_urls = URL_RE.sub("", text)
    cleaned_lines = []
    for line in no_urls.split("\n"):
        line = re.sub(r"[ \t]+", " ", line).strip()
        if line:
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines).strip()


def _paste_avatar(
    card: Image.Image,
    avatar_bytes: bytes,
    left_w: int,
    card_h: int,
) -> None:
    """Render and paste the atmospheric grayscale avatar fading into pure black."""
    try:
        with Image.open(io.BytesIO(avatar_bytes)) as av_raw:
            av_gray = av_raw.convert("L").convert("RGBA")
            enhancer = ImageEnhance.Contrast(av_gray)
            av_gray = enhancer.enhance(1.15)
            brightness = ImageEnhance.Brightness(av_gray)
            av_gray = brightness.enhance(0.95)

            src_w, src_h = av_gray.size
            scale = max(left_w / src_w, card_h / src_h)
            new_w = int(src_w * scale)
            new_h = int(src_h * scale)
            av_resized = av_gray.resize((new_w, new_h), Image.Resampling.LANCZOS)

            crop_x = max(0, (new_w - left_w) // 2)
            crop_y = max(0, (new_h - card_h) // 2)
            av_cropped = av_resized.crop((crop_x, crop_y, crop_x + left_w, crop_y + card_h))

            mask = Image.new("L", (left_w, card_h), 255)
            fade_start = int(left_w * 0.35)
            fade_w = left_w - fade_start
            for x in range(left_w):
                if x < fade_start:
                    alpha_val = 255
                else:
                    pct = (x - fade_start) / float(fade_w)
                    alpha_val = int(255 * 0.5 * (1.0 + math.cos(math.pi * pct)))
                for y in range(card_h):
                    mask.putpixel((x, y), max(0, min(255, alpha_val)))

            card.paste(av_cropped, (0, 0), mask)
    except Exception as av_err:
        logger.debug("Avatar processing failed for quote card: %s", av_err)


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
    watermark: str = "Make it a Quote#6660",
    custom_emojis: Optional[Dict[str, Union[bytes, Image.Image]]] = None,
) -> Optional[io.BytesIO]:
    """
    Generate an atmospheric, dark-themed quote card matching 'Make it a Quote'.
    Features:
      • 16:9 canvas (960x540) with deep pitch-black background (0, 0, 0).
      • Grayscale avatar on left with smooth horizontal cosine fade into black.
      • Horizontally and vertically centered quote text + attribution on right.
      • Full emoji support: native Unicode color emojis and Discord custom emojis.
      • Ignores and strips raw URLs (GIF links, attachment links, website URLs).
      • Subtle watermark bottom-right.
    """
    try:
        # Strip all raw URLs (including gif links, attachment links)
        clean_text = strip_urls_from_text(text or "")
        if not clean_text:
            clean_text = "..."

        # Pre-process loaded custom emojis into RGBA PIL Images
        loaded_emojis: Dict[str, Image.Image] = {}
        if custom_emojis:
            for k, v in custom_emojis.items():
                if isinstance(v, Image.Image):
                    loaded_emojis[k] = v.convert("RGBA")
                elif isinstance(v, (bytes, bytearray)):
                    try:
                        loaded_emojis[k] = Image.open(io.BytesIO(v)).convert("RGBA")
                    except Exception:
                        pass

        width = 960
        card_h = 540  # Standard 16:9 aspect ratio
        left_w = int(width * 0.44)  # ~422px

        # Pure solid black background
        card = Image.new("RGBA", (width, card_h), (0, 0, 0, 255))

        # 1. Left section: Grayscale avatar with smooth horizontal cosine fade
        if avatar_bytes:
            _paste_avatar(card, avatar_bytes, left_w, card_h)

        draw = ImageDraw.Draw(card)

        # 2. Right section: Text & Attribution layout
        if avatar_bytes:
            right_start_x = int(width * 0.44)
            right_end_x = width - 48
        else:
            right_start_x = int(width * 0.10)
            right_end_x = width - int(width * 0.10)

        right_cx = right_start_x + (right_end_x - right_start_x) // 2
        max_text_w = right_end_x - right_start_x

        dummy_img = Image.new("RGBA", (10, 10))
        dummy_draw = ImageDraw.Draw(dummy_img)

        font_author = _get_font(21, italic=True)
        font_handle = _get_font(15, bold=False)
        font_meta = _get_font(12, bold=False)

        author_str = f"- {author_name}" if author_name else "- Anonymous"
        author_bbox = dummy_draw.textbbox((0, 0), author_str, font=font_author)
        author_w = author_bbox[2] - author_bbox[0]
        author_h = author_bbox[3] - author_bbox[1]

        handle_str = f"@{author_handle}" if author_handle else ""
        if handle_str:
            handle_bbox = dummy_draw.textbbox((0, 0), handle_str, font=font_handle)
            handle_w = handle_bbox[2] - handle_bbox[0]
            handle_h = handle_bbox[3] - handle_bbox[1]
        else:
            handle_w, handle_h = 0, 0

        gap_author_handle = 5
        author_block_h = author_h + (gap_author_handle + handle_h if handle_str else 0)

        # Check if message consists exclusively of custom emojis (1 to 5 emojis)
        emoji_matches = list(CUSTOM_EMOJI_RE.finditer(clean_text))
        remaining_after_emojis = CUSTOM_EMOJI_RE.sub("", clean_text).strip()
        is_only_custom_emojis = (len(emoji_matches) > 0 and not remaining_after_emojis)

        if is_only_custom_emojis and len(emoji_matches) <= 5:
            # ── JUMBO CUSTOM EMOJI DISPLAY (LIKE DISCORD CHAT) ──
            if len(emoji_matches) == 1:
                em_size = 110
            elif len(emoji_matches) <= 3:
                em_size = 80
            else:
                em_size = 64

            em_spacing = 14
            total_em_w = len(emoji_matches) * em_size + (len(emoji_matches) - 1) * em_spacing
            gap_emoji_author = 28
            content_total_h = em_size + gap_emoji_author + author_block_h

            if content_total_h + 90 > card_h:
                card_h = content_total_h + 90
                card = Image.new("RGBA", (width, card_h), (0, 0, 0, 255))
                if avatar_bytes:
                    _paste_avatar(card, avatar_bytes, left_w, card_h)
                draw = ImageDraw.Draw(card)

            start_y = max(36, (card_h - content_total_h) // 2)
            start_em_x = right_cx - total_em_w // 2
            curr_x = start_em_x

            for m in emoji_matches:
                eid = m.group(3)
                ename = m.group(2)
                em_img = loaded_emojis.get(eid)
                if em_img:
                    em_resized = em_img.resize((em_size, em_size), Image.Resampling.LANCZOS)
                    card.paste(em_resized, (curr_x, start_y), em_resized)
                else:
                    fb_font = _get_font(28)
                    draw.text((curr_x, start_y), f":{ename}:", font=fb_font, fill=(255, 255, 255, 255))
                curr_x += em_size + em_spacing

            curr_y = start_y + em_size + gap_emoji_author
            author_x = right_cx - author_w // 2
            draw.text((author_x, curr_y), author_str, font=font_author, fill=(215, 218, 225, 255))
            if handle_str:
                curr_y += author_h + gap_author_handle
                handle_x = right_cx - handle_w // 2
                draw.text((handle_x, curr_y), handle_str, font=font_handle, fill=(125, 130, 142, 255))

        else:
            # ── TEXT + INLINE EMOJI DISPLAY ──
            char_len = len(clean_text)
            if char_len <= 60:
                quote_size = 40
                line_spacing = 14
            elif char_len <= 140:
                quote_size = 32
                line_spacing = 12
            elif char_len <= 250:
                quote_size = 26
                line_spacing = 10
            else:
                quote_size = 20
                line_spacing = 8

            font_quote = _get_font(quote_size, emoji=True)
            inline_em_size = int(quote_size * 1.05)

            sp_bbox = dummy_draw.textbbox((0, 0), " ", font=font_quote)
            sp_w = sp_bbox[2] - sp_bbox[0]

            paragraphs = clean_text.split("\n")
            lines: List[List[Tuple[str, Any, int]]] = []

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                tokens: List[Tuple[str, Any, int]] = []
                last_idx = 0
                for m in CUSTOM_EMOJI_RE.finditer(para):
                    st, end = m.span()
                    if st > last_idx:
                        chunk = para[last_idx:st]
                        words = chunk.split()
                        for idx, w in enumerate(words):
                            w_bbox = dummy_draw.textbbox((0, 0), w, font=font_quote)
                            tokens.append(("text", w, w_bbox[2] - w_bbox[0]))
                            tokens.append(("space", " ", sp_w))
                    eid = m.group(3)
                    ename = m.group(2)
                    em_img = loaded_emojis.get(eid)
                    if em_img:
                        tokens.append(("emoji", em_img, inline_em_size))
                    else:
                        fb_str = f":{ename}:"
                        fb_bbox = dummy_draw.textbbox((0, 0), fb_str, font=font_quote)
                        tokens.append(("text", fb_str, fb_bbox[2] - fb_bbox[0]))
                    tokens.append(("space", " ", sp_w))
                    last_idx = end

                if last_idx < len(para):
                    chunk = para[last_idx:]
                    words = chunk.split()
                    for w in words:
                        w_bbox = dummy_draw.textbbox((0, 0), w, font=font_quote)
                        tokens.append(("text", w, w_bbox[2] - w_bbox[0]))
                        tokens.append(("space", " ", sp_w))

                if tokens and tokens[-1][0] == "space":
                    tokens.pop()

                curr_line: List[Tuple[str, Any, int]] = []
                curr_line_w = 0

                for tok in tokens:
                    tok_type, tok_val, tok_w = tok
                    if tok_type == "space" and not curr_line:
                        continue

                    if curr_line_w + tok_w <= max_text_w:
                        curr_line.append(tok)
                        curr_line_w += tok_w
                    else:
                        if curr_line:
                            if curr_line[-1][0] == "space":
                                curr_line_w -= curr_line[-1][2]
                                curr_line.pop()
                            lines.append(curr_line)
                        if tok_type != "space":
                            curr_line = [tok]
                            curr_line_w = tok_w
                        else:
                            curr_line = []
                            curr_line_w = 0

                if curr_line:
                    if curr_line[-1][0] == "space":
                        curr_line.pop()
                    lines.append(curr_line)

            if not lines:
                lines = [[("text", "...", 30)]]

            if len(lines) > 8:
                lines = lines[:8]

            line_h = max(quote_size, inline_em_size)
            total_quote_h = len(lines) * line_h + max(0, len(lines) - 1) * line_spacing
            gap_quote_author = 24
            content_total_h = total_quote_h + gap_quote_author + author_block_h

            # Dynamic height expansion if content genuinely exceeds 16:9 canvas
            if content_total_h + 90 > card_h:
                card_h = content_total_h + 90
                card = Image.new("RGBA", (width, card_h), (0, 0, 0, 255))
                if avatar_bytes:
                    _paste_avatar(card, avatar_bytes, left_w, card_h)
                draw = ImageDraw.Draw(card)

            start_y = max(36, (card_h - content_total_h) // 2)

            # Draw lines (CENTER-ALIGNED)
            curr_y = start_y
            for line in lines:
                line_w = sum(t[2] for t in line)
                line_x = right_cx - line_w // 2
                curr_x = line_x
                for tok_type, tok_val, tok_w in line:
                    if tok_type == "text":
                        draw.text(
                            (curr_x, curr_y),
                            tok_val,
                            font=font_quote,
                            fill=(255, 255, 255, 255),
                            embedded_color=_is_color_font(font_quote),
                        )
                    elif tok_type == "emoji":
                        em_resized = tok_val.resize((inline_em_size, inline_em_size), Image.Resampling.LANCZOS)
                        em_y = curr_y + (line_h - inline_em_size) // 2
                        card.paste(em_resized, (curr_x, em_y), em_resized)
                    curr_x += tok_w
                curr_y += line_h + line_spacing

            curr_y += gap_quote_author - line_spacing
            author_x = right_cx - author_w // 2
            draw.text((author_x, curr_y), author_str, font=font_author, fill=(215, 218, 225, 255))

            if handle_str:
                curr_y += author_h + gap_author_handle
                handle_x = right_cx - handle_w // 2
                draw.text((handle_x, curr_y), handle_str, font=font_handle, fill=(125, 130, 142, 255))

        # 5. Subtle Branding Watermark bottom-right
        wm_text = watermark or "Make it a Quote#6660"
        wm_bbox = draw.textbbox((0, 0), wm_text, font=font_meta)
        wm_w = wm_bbox[2] - wm_bbox[0]
        wm_h = wm_bbox[3] - wm_bbox[1]
        draw.text(
            (width - wm_w - 20, card_h - wm_h - 14),
            wm_text,
            fill=(75, 78, 88, 255),
            font=font_meta,
        )

        # 6. Rounded corner alpha mask
        corner_mask = Image.new("L", (width, card_h), 0)
        c_draw = ImageDraw.Draw(corner_mask)
        c_draw.rounded_rectangle(
            [(0, 0), (width - 1, card_h - 1)],
            radius=12,
            fill=255,
        )
        card.putalpha(corner_mask)

        # 7. Clean perimeter outline
        draw = ImageDraw.Draw(card)
        draw.rounded_rectangle(
            [(0, 0), (width - 1, card_h - 1)],
            radius=12,
            outline=(24, 25, 28, 255),
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

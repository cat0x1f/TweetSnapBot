import io
from pathlib import Path
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from config import SessionConfig
from fxtwitter import FxTwitterClient, TweetData, TweetMedia


CANVAS_WIDTH = 1200
CARD_PADDING = 44
AVATAR_SIZE = 96
MEDIA_HEIGHT = 560
LINE_SPACING = 14
MEDIA_GAP = 12
FONTS_DIR = Path(__file__).resolve().parent / "fonts"


def _load_font(size: int, bold: bool = False, emoji: bool = False) -> ImageFont.ImageFont:
    candidates = [FONTS_DIR / "Emoji.ttf"] if emoji else [FONTS_DIR / "SourceHanSans.ttf"]
    for path in candidates:
        try:
            font = ImageFont.truetype(str(path), size=size)
            if path.name == "SourceHanSans.ttf":
                _set_font_weight(font, "Medium" if not bold else "Bold")
            return font
        except OSError:
            continue
    return ImageFont.load_default()


def _set_font_weight(font: ImageFont.FreeTypeFont, variation_name: str) -> None:
    try:
        font.set_variation_by_name(variation_name)
        return
    except Exception:
        pass

    try:
        axes = font.get_variation_axes()
    except Exception:
        return

    if not axes:
        return

    weight_axis = axes[0]
    weight_map = {
        "Medium": 500,
        "Bold": 700,
    }
    try:
        font.set_variation_by_axes([weight_map.get(variation_name, weight_axis["default"])])
    except Exception:
        return


def _theme_colors(config: SessionConfig) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]:
    if config.theme.lower() == "dark":
        return (22, 24, 28), (255, 255, 255), (139, 152, 165), (47, 51, 54)
    return (255, 255, 255), (15, 20, 25), (83, 100, 113), (207, 217, 222)


def _is_emoji(char: str) -> bool:
    codepoint = ord(char)
    return (
        0x1F300 <= codepoint <= 0x1FAFF
        or 0x2600 <= codepoint <= 0x27BF
        or 0xFE00 <= codepoint <= 0xFE0F
        or 0x1F1E6 <= codepoint <= 0x1F1FF
    )


def _pick_font(
    text_font: ImageFont.ImageFont,
    emoji_font: ImageFont.ImageFont,
    char: str,
) -> ImageFont.ImageFont:
    if _is_emoji(char):
        return emoji_font
    return text_font


def _layout_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    text_font: ImageFont.ImageFont,
    emoji_font: ImageFont.ImageFont,
    width: int,
) -> List[List[Tuple[str, ImageFont.ImageFont, float]]]:
    lines: List[List[Tuple[str, ImageFont.ImageFont, float]]] = []
    for raw_line in (text or "").splitlines() or [""]:
        current: List[Tuple[str, ImageFont.ImageFont, float]] = []
        current_width = 0.0
        for char in raw_line:
            font = _pick_font(text_font, emoji_font, char)
            char_width = draw.textlength(char, font=font)
            if current and current_width + char_width > width:
                lines.append(current)
                current = [(char, font, char_width)]
                current_width = char_width
            else:
                current.append((char, font, char_width))
                current_width += char_width
        lines.append(current)
    return lines


def _measure_text_block(
    draw: ImageDraw.ImageDraw,
    text: str,
    text_font: ImageFont.ImageFont,
    emoji_font: ImageFont.ImageFont,
    width: int,
) -> Tuple[List[List[Tuple[str, ImageFont.ImageFont, float]]], int]:
    lines = _layout_text(draw, text, text_font, emoji_font, width)
    line_height = max(text_font.size, emoji_font.size)
    line_count = max(1, len(lines))
    return lines, line_count * line_height + max(0, line_count - 1) * LINE_SPACING


def _draw_rich_text(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    lines: List[List[Tuple[str, ImageFont.ImageFont, float]]],
    fill,
) -> int:
    cursor_y = y
    for line in lines:
        cursor_x = x
        line_ascent = 0
        line_descent = 0
        metrics: List[Tuple[int, int]] = []
        for _, font, _ in line:
            try:
                ascent, descent = font.getmetrics()
            except Exception:
                ascent, descent = font.size, 0
            metrics.append((ascent, descent))
            line_ascent = max(line_ascent, ascent)
            line_descent = max(line_descent, descent)

        for (char, font, char_width), (ascent, _) in zip(line, metrics):
            char_y = cursor_y + (line_ascent - ascent)
            draw.text((cursor_x, char_y), char, font=font, fill=fill)
            cursor_x += char_width
        line_height = line_ascent + line_descent
        cursor_y += line_height + LINE_SPACING
    if not lines:
        return 0
    return cursor_y - y - LINE_SPACING


def _download_image(client: FxTwitterClient, url: Optional[str], size: Optional[Tuple[int, int]] = None) -> Optional[Image.Image]:
    if not url:
        return None
    try:
        image = Image.open(io.BytesIO(client.download_bytes(url))).convert("RGB")
        if size:
            image = ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)
        return image
    except Exception:
        return None


def _draw_stats(draw: ImageDraw.ImageDraw, tweet: TweetData, font: ImageFont.ImageFont, start_x: int, y: int, color) -> int:
    stats = [
        f"Reply {tweet.replies}",
        f"RT {tweet.retweets}",
        f"Like {tweet.likes}",
    ]
    if tweet.views:
        stats.append(f"View {tweet.views}")

    cursor_x = start_x
    for item in stats:
        draw.text((cursor_x, y), item, font=font, fill=color)
        cursor_x += draw.textlength(item, font=font) + 28
    return y + font.size + 4


def _pick_media_url(media: TweetMedia) -> Optional[str]:
    return media.url or media.thumbnail_url


def _media_block_height(media_count: int) -> int:
    if media_count <= 0:
        return 0
    if media_count == 1:
        return MEDIA_HEIGHT
    return MEDIA_HEIGHT + 80


def _build_media_collage(
    client: FxTwitterClient,
    media_items: List[TweetMedia],
    width: int,
    height: int,
    border_color,
) -> Optional[Image.Image]:
    images: List[Image.Image] = []
    for media in media_items[:4]:
        image = _download_image(client, _pick_media_url(media))
        if image is not None:
            images.append(image)

    if not images:
        return None

    canvas = Image.new("RGB", (width, height), border_color)
    count = len(images)

    if count == 1:
        return ImageOps.fit(images[0], (width, height), method=Image.Resampling.LANCZOS)

    if count == 2:
        tile_width = (width - MEDIA_GAP) // 2
        slots = [
            (0, 0, tile_width, height),
            (tile_width + MEDIA_GAP, 0, tile_width, height),
        ]
    else:
        tile_width = (width - MEDIA_GAP) // 2
        tile_height = (height - MEDIA_GAP) // 2
        slots = [
            (0, 0, tile_width, tile_height),
            (tile_width + MEDIA_GAP, 0, tile_width, tile_height),
            (0, tile_height + MEDIA_GAP, tile_width, tile_height),
            (tile_width + MEDIA_GAP, tile_height + MEDIA_GAP, tile_width, tile_height),
        ]

    for image, (x, y, w, h) in zip(images, slots):
        tile = ImageOps.fit(image, (w, h), method=Image.Resampling.LANCZOS)
        canvas.paste(tile, (x, y))

    return canvas


def render_tweet_card(tweet: TweetData, client: FxTwitterClient, config: SessionConfig) -> bytes:
    background_color, primary_color, secondary_color, border_color = _theme_colors(config)
    bold_font = _load_font(40, bold=False)
    body_font = _load_font(36)
    emoji_font = _load_font(42, emoji=True)
    meta_font = _load_font(28)

    probe = Image.new("RGB", (CANVAS_WIDTH, 1200), background_color)
    probe_draw = ImageDraw.Draw(probe)

    text_width = CANVAS_WIDTH - CARD_PADDING * 2
    text_lines, text_height = _measure_text_block(
        probe_draw,
        tweet.text or tweet.url,
        body_font,
        emoji_font,
        text_width,
    )

    total_height = CARD_PADDING * 2 + AVATAR_SIZE + 32 + text_height + 32
    media_height = _media_block_height(len(tweet.media))
    if media_height:
        total_height += media_height + 32
    if config.show_timestamp and tweet.created_at:
        total_height += meta_font.size + 24
    if config.show_stats:
        total_height += meta_font.size + 20

    canvas = Image.new("RGB", (CANVAS_WIDTH, total_height), background_color)
    draw = ImageDraw.Draw(canvas)
    draw.rectangle(
        (0, 0, CANVAS_WIDTH - 1, total_height - 1),
        outline=border_color,
        width=2,
        fill=background_color,
    )

    avatar = _download_image(client, tweet.author.avatar_url, (AVATAR_SIZE, AVATAR_SIZE))
    if avatar is None:
        avatar = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), border_color)
    canvas.paste(avatar, (CARD_PADDING, CARD_PADDING))

    header_x = CARD_PADDING + AVATAR_SIZE + 24
    draw.text((header_x, CARD_PADDING + 4), tweet.author.name or "Unknown", font=bold_font, fill=primary_color)
    handle = f"@{tweet.author.screen_name}" if tweet.author.screen_name else ""
    if handle:
        draw.text((header_x, CARD_PADDING + 54), handle, font=meta_font, fill=secondary_color)

    cursor_y = CARD_PADDING + AVATAR_SIZE + 32
    rendered_text_height = _draw_rich_text(
        draw,
        CARD_PADDING,
        cursor_y,
        text_lines,
        primary_color,
    )
    cursor_y += rendered_text_height + 32

    if media_height:
        media_image = _build_media_collage(
            client,
            tweet.media,
            CANVAS_WIDTH - CARD_PADDING * 2,
            media_height,
            border_color,
        )
        if media_image:
            canvas.paste(media_image, (CARD_PADDING, cursor_y))
            draw.rectangle(
                (
                    CARD_PADDING,
                    cursor_y,
                    CANVAS_WIDTH - CARD_PADDING,
                    cursor_y + media_height,
                ),
                outline=border_color,
                width=2,
            )
        cursor_y += media_height + 32

    if config.show_timestamp and tweet.created_at:
        draw.text((CARD_PADDING, cursor_y), tweet.created_at, font=meta_font, fill=secondary_color)
        cursor_y += meta_font.size + 24

    if config.show_stats:
        cursor_y = _draw_stats(draw, tweet, meta_font, CARD_PADDING, cursor_y, secondary_color)

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()

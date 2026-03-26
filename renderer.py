import io
import unicodedata
from pathlib import Path
from typing import List, Optional, Tuple

import qrcode
from PIL import Image, ImageDraw, ImageFont, ImageOps

from config import RenderConfig
from fxtwitter import FxTwitterClient, TweetData, TweetMedia


CANVAS_WIDTH = 1200
CARD_PADDING = 44
AVATAR_SIZE = 96
MEDIA_HEIGHT = 560
LINE_SPACING = 8
MEDIA_GAP = 12
QUOTE_MEDIA_HEIGHT = 240
FONTS_DIR = Path(__file__).resolve().parent / "fonts"
EXTREME_ASPECT_RATIO = 5.0
QR_SIZE = 88
POST_MEDIA_SPACING = 20
BOTTOM_PADDING = 20


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


def _theme_colors(config: RenderConfig) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]:
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


def _is_regional_indicator(char: str) -> bool:
    codepoint = ord(char)
    return 0x1F1E6 <= codepoint <= 0x1F1FF


def _is_skin_tone_modifier(char: str) -> bool:
    codepoint = ord(char)
    return 0x1F3FB <= codepoint <= 0x1F3FF


def _is_variation_selector(char: str) -> bool:
    codepoint = ord(char)
    return 0xFE00 <= codepoint <= 0xFE0F or 0xE0100 <= codepoint <= 0xE01EF


def _is_keycap_combiner(char: str) -> bool:
    return ord(char) == 0x20E3


def _should_use_emoji_font(segment: str) -> bool:
    return any(_is_emoji(char) for char in segment)


def _segment_text(text: str) -> List[str]:
    clusters: List[str] = []
    i = 0
    while i < len(text):
        cluster = text[i]
        i += 1

        while i < len(text) and (_is_variation_selector(text[i]) or unicodedata.combining(text[i])):
            cluster += text[i]
            i += 1

        if i < len(text) and _is_skin_tone_modifier(text[i]):
            cluster += text[i]
            i += 1
            while i < len(text) and (_is_variation_selector(text[i]) or unicodedata.combining(text[i])):
                cluster += text[i]
                i += 1

        if i < len(text) and _is_keycap_combiner(text[i]):
            cluster += text[i]
            i += 1

        if _is_regional_indicator(cluster[0]) and i < len(text) and _is_regional_indicator(text[i]):
            cluster += text[i]
            i += 1

        while i < len(text) and ord(text[i]) == 0x200D:
            cluster += text[i]
            i += 1
            if i >= len(text):
                break
            cluster += text[i]
            i += 1
            while i < len(text) and (_is_variation_selector(text[i]) or unicodedata.combining(text[i])):
                cluster += text[i]
                i += 1
            if i < len(text) and _is_skin_tone_modifier(text[i]):
                cluster += text[i]
                i += 1
                while i < len(text) and (_is_variation_selector(text[i]) or unicodedata.combining(text[i])):
                    cluster += text[i]
                    i += 1

        clusters.append(cluster)

    return clusters


def _pick_font(
    text_font: ImageFont.ImageFont,
    emoji_font: ImageFont.ImageFont,
    segment: str,
) -> ImageFont.ImageFont:
    if _should_use_emoji_font(segment):
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
        for segment in _segment_text(raw_line):
            font = _pick_font(text_font, emoji_font, segment)
            segment_width = draw.textlength(segment, font=font)
            if current and current_width + segment_width > width:
                lines.append(current)
                current = [(segment, font, segment_width)]
                current_width = segment_width
            else:
                current.append((segment, font, segment_width))
                current_width += segment_width
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
    return lines, _measure_lines_height(lines, text_font)


def _font_line_height(font: ImageFont.ImageFont) -> int:
    try:
        ascent, descent = font.getmetrics()
        return ascent + descent
    except Exception:
        return getattr(font, "size", 0) or 0


def _measure_lines_height(
    lines: List[List[Tuple[str, ImageFont.ImageFont, float]]],
    fallback_font: ImageFont.ImageFont,
) -> int:
    if not lines:
        return _font_line_height(fallback_font)

    total = 0
    for line in lines:
        if not line:
            total += _font_line_height(fallback_font)
            continue
        line_height = max(_font_line_height(font) for _, font, _ in line)
        total += line_height
    total += max(0, len(lines) - 1) * LINE_SPACING
    return total




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


def _fit_media_image(image: Image.Image, size: Tuple[int, int], background_color) -> Image.Image:
    target_width, target_height = size
    source_width, source_height = image.size
    if not source_width or not source_height:
        return Image.new("RGB", size, background_color)

    image_ratio = max(source_width / source_height, source_height / source_width)
    if image_ratio >= EXTREME_ASPECT_RATIO:
        return ImageOps.fit(image, size, method=Image.Resampling.LANCZOS)

    canvas = Image.new("RGB", size, background_color)
    contained = ImageOps.contain(image, size, method=Image.Resampling.LANCZOS)
    offset_x = (target_width - contained.width) // 2
    offset_y = (target_height - contained.height) // 2
    canvas.paste(contained, (offset_x, offset_y))
    return canvas


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


def _quote_media_block_height(media_count: int) -> int:
    if media_count <= 0:
        return 0
    if media_count == 1:
        return QUOTE_MEDIA_HEIGHT
    return QUOTE_MEDIA_HEIGHT + 56


def _single_media_target_height(
    media: TweetMedia,
    target_width: int,
    fallback_height: int,
) -> int:
    if not media.width or not media.height or media.width <= 0 or media.height <= 0:
        return fallback_height
    return max(1, int(target_width * (media.height / media.width)))


def _build_media_collage(
    client: FxTwitterClient,
    media_items: List[TweetMedia],
    width: int,
    height: int,
    border_color,
    background_color,
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
        return _fit_media_image(images[0], (width, height), background_color)

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
        tile = _fit_media_image(image, (w, h), background_color)
        canvas.paste(tile, (x, y))

    return canvas


def _measure_quote_block(
    draw: ImageDraw.ImageDraw,
    quote: TweetData,
    text_font: ImageFont.ImageFont,
    emoji_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    width: int,
) -> Tuple[List[List[Tuple[str, ImageFont.ImageFont, float]]], int, int]:
    quote_lines, quote_text_height = _measure_text_block(
        draw,
        quote.text or quote.url,
        text_font,
        emoji_font,
        width - 32,
    )
    media_height = 0
    if quote.media:
        if len(quote.media) == 1:
            media_height = _single_media_target_height(
                quote.media[0],
                width - 32,
                QUOTE_MEDIA_HEIGHT,
            )
        else:
            media_height = _quote_media_block_height(len(quote.media))
    total_height = 24 + meta_font.size + 14 + quote_text_height + 20
    if media_height:
        total_height += media_height + 20
    return quote_lines, quote_text_height, total_height


def _draw_quote_block(
    canvas: Image.Image,
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    width: int,
    quote: TweetData,
    client: FxTwitterClient,
    text_font: ImageFont.ImageFont,
    emoji_font: ImageFont.ImageFont,
    meta_font: ImageFont.ImageFont,
    primary_color,
    secondary_color,
    border_color,
    background_color,
) -> int:
    quote_lines, quote_text_height, total_height = _measure_quote_block(
        draw,
        quote,
        text_font,
        emoji_font,
        meta_font,
        width,
    )
    draw.rectangle(
        (x, y, x + width, y + total_height),
        outline=border_color,
        width=2,
        fill=background_color,
    )

    cursor_y = y + 16
    title = quote.author.name or "Unknown"
    if quote.author.screen_name:
        title = f"{title} @{quote.author.screen_name}"
    draw.text((x + 16, cursor_y), title, font=meta_font, fill=primary_color)
    cursor_y += meta_font.size + 14

    text_height = _draw_rich_text(
        draw,
        x + 16,
        cursor_y,
        quote_lines,
        primary_color,
    )
    cursor_y += text_height + 20

    media_height = 0
    if quote.media:
        if len(quote.media) == 1:
            media_height = _single_media_target_height(
                quote.media[0],
                width - 32,
                QUOTE_MEDIA_HEIGHT,
            )
        else:
            media_height = _quote_media_block_height(len(quote.media))
    if media_height:
        media_image = _build_media_collage(
            client,
            quote.media,
            width - 32,
            media_height,
            border_color,
            background_color,
        )
        if media_image:
            canvas.paste(media_image, (x + 16, cursor_y))
            draw.rectangle(
                (x + 16, cursor_y, x + 16 + width - 32, cursor_y + media_height),
                outline=border_color,
                width=2,
            )
            cursor_y += media_height + 20

    return total_height


def _build_qr_code(data: str, size: int, background_color) -> Image.Image:
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
    )
    qr.add_data(data)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    return ImageOps.fit(image, (size, size), method=Image.Resampling.NEAREST)


def render_tweet_card(tweet: TweetData, client: FxTwitterClient, config: RenderConfig) -> bytes:
    background_color, primary_color, secondary_color, border_color = _theme_colors(config)
    bold_font = _load_font(40, bold=False)
    body_font = _load_font(36)
    emoji_font = _load_font(36, emoji=True)
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

    total_height = CARD_PADDING + AVATAR_SIZE + 32 + text_height + 32
    media_height = 0
    if tweet.media:
        if len(tweet.media) == 1:
            media_height = _single_media_target_height(
                tweet.media[0],
                CANVAS_WIDTH - CARD_PADDING * 2,
                MEDIA_HEIGHT,
            )
        else:
            media_height = _media_block_height(len(tweet.media))
    place_quote_at_bottom = bool(tweet.quote and media_height)
    if media_height:
        total_height += media_height + POST_MEDIA_SPACING
    footer_text_height = 0
    if config.show_timestamp and tweet.created_at:
        footer_text_height += meta_font.size + 24
    if config.show_stats:
        footer_text_height += meta_font.size + 20
    quote_height = 0
    if tweet.quote:
        _, _, quote_height = _measure_quote_block(
            probe_draw,
            tweet.quote,
            _load_font(30),
            _load_font(30, emoji=True),
            _load_font(24),
            text_width,
        )
        total_height += quote_height + 24
    total_height += max(footer_text_height, QR_SIZE)
    total_height += BOTTOM_PADDING

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

    if tweet.quote and not place_quote_at_bottom:
        quote_height = _draw_quote_block(
            canvas,
            draw,
            CARD_PADDING,
            cursor_y,
            CANVAS_WIDTH - CARD_PADDING * 2,
            tweet.quote,
            client,
            _load_font(30),
            _load_font(30, emoji=True),
            _load_font(24),
            primary_color,
            secondary_color,
            border_color,
            background_color,
        )
        cursor_y += quote_height + 24

    if media_height:
        media_image = _build_media_collage(
            client,
            tweet.media,
            CANVAS_WIDTH - CARD_PADDING * 2,
            media_height,
            border_color,
            background_color,
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
        cursor_y += media_height + POST_MEDIA_SPACING

    if tweet.quote and place_quote_at_bottom:
        quote_height = _draw_quote_block(
            canvas,
            draw,
            CARD_PADDING,
            cursor_y,
            CANVAS_WIDTH - CARD_PADDING * 2,
            tweet.quote,
            client,
            _load_font(30),
            _load_font(30, emoji=True),
            _load_font(24),
            primary_color,
            secondary_color,
            border_color,
            background_color,
        )
        cursor_y += quote_height + 24

    timestamp_y: Optional[int] = None
    if config.show_timestamp and tweet.created_at:
        timestamp_y = cursor_y
        draw.text((CARD_PADDING, cursor_y), tweet.created_at, font=meta_font, fill=secondary_color)
        cursor_y += meta_font.size + 24

    if config.show_stats:
        cursor_y = _draw_stats(draw, tweet, meta_font, CARD_PADDING, cursor_y, secondary_color)

    qr_image = _build_qr_code(tweet.url, QR_SIZE, background_color)
    qr_x = CANVAS_WIDTH - CARD_PADDING - QR_SIZE
    qr_y = timestamp_y if timestamp_y is not None else total_height - BOTTOM_PADDING - QR_SIZE
    canvas.paste(qr_image, (qr_x, qr_y))

    content_bottom = max(cursor_y, qr_y + QR_SIZE)
    final_height = min(total_height, max(content_bottom + BOTTOM_PADDING, 1))
    if final_height < total_height:
        canvas = canvas.crop((0, 0, CANVAS_WIDTH, final_height))
        draw = ImageDraw.Draw(canvas)
        draw.rectangle(
            (0, 0, CANVAS_WIDTH - 1, final_height - 1),
            outline=border_color,
            width=2,
        )

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()

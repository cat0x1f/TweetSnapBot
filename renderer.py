import io
import textwrap
from typing import Optional, Tuple

from PIL import Image, ImageDraw, ImageFont, ImageOps

from config import SessionConfig
from fxtwitter import FxTwitterClient, TweetData


CANVAS_WIDTH = 900
CARD_PADDING = 32
AVATAR_SIZE = 72
MEDIA_HEIGHT = 420
LINE_SPACING = 10


def _load_font(size: int, bold: bool = False) -> ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
        "/System/Library/Fonts/Supplemental/Helvetica.ttc",
        "/System/Library/Fonts/SFNS.ttf",
    ]
    if bold:
        candidates = [
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
            "/System/Library/Fonts/Supplemental/Helvetica Bold.ttf",
        ] + candidates

    for path in candidates:
        try:
            return ImageFont.truetype(path, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _theme_colors(config: SessionConfig) -> Tuple[Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int], Tuple[int, int, int]]:
    if config.theme.lower() == "dark":
        return (22, 24, 28), (255, 255, 255), (139, 152, 165), (47, 51, 54)
    return (255, 255, 255), (15, 20, 25), (83, 100, 113), (207, 217, 222)


def _measure_text_block(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> Tuple[str, int]:
    approx_chars = max(10, int(width / max(8, font.size * 0.58)))
    wrapped = textwrap.fill(text, width=approx_chars)
    box = draw.multiline_textbbox((0, 0), wrapped, font=font, spacing=LINE_SPACING)
    return wrapped, box[3] - box[1]


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


def render_tweet_card(tweet: TweetData, client: FxTwitterClient, config: SessionConfig) -> bytes:
    background_color, primary_color, secondary_color, border_color = _theme_colors(config)
    bold_font = _load_font(30, bold=True)
    body_font = _load_font(28)
    meta_font = _load_font(22)

    probe = Image.new("RGB", (CANVAS_WIDTH, 1200), background_color)
    probe_draw = ImageDraw.Draw(probe)

    text_width = CANVAS_WIDTH - CARD_PADDING * 2
    wrapped_text, text_height = _measure_text_block(probe_draw, tweet.text or tweet.url, body_font, text_width)

    total_height = CARD_PADDING * 2 + AVATAR_SIZE + 24 + text_height + 24
    if tweet.media:
        total_height += MEDIA_HEIGHT + 24
    if config.show_timestamp and tweet.created_at:
        total_height += meta_font.size + 20
    if config.show_stats:
        total_height += meta_font.size + 16

    canvas = Image.new("RGB", (CANVAS_WIDTH, total_height), background_color)
    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle(
        (0, 0, CANVAS_WIDTH - 1, total_height - 1),
        radius=config.border_radius or 24,
        outline=border_color,
        width=2,
        fill=background_color,
    )

    avatar = _download_image(client, tweet.author.avatar_url, (AVATAR_SIZE, AVATAR_SIZE))
    if avatar is None:
        avatar = Image.new("RGB", (AVATAR_SIZE, AVATAR_SIZE), border_color)
    avatar_mask = Image.new("L", (AVATAR_SIZE, AVATAR_SIZE), 0)
    ImageDraw.Draw(avatar_mask).ellipse((0, 0, AVATAR_SIZE, AVATAR_SIZE), fill=255)
    canvas.paste(avatar, (CARD_PADDING, CARD_PADDING), avatar_mask)

    header_x = CARD_PADDING + AVATAR_SIZE + 20
    draw.text((header_x, CARD_PADDING + 2), tweet.author.name or "Unknown", font=bold_font, fill=primary_color)
    handle = f"@{tweet.author.screen_name}" if tweet.author.screen_name else ""
    if handle:
        draw.text((header_x, CARD_PADDING + 40), handle, font=meta_font, fill=secondary_color)

    cursor_y = CARD_PADDING + AVATAR_SIZE + 24
    draw.multiline_text(
        (CARD_PADDING, cursor_y),
        wrapped_text,
        font=body_font,
        fill=primary_color,
        spacing=LINE_SPACING,
    )
    cursor_y += text_height + 24

    if tweet.media:
        media = tweet.media[0]
        media_image = _download_image(client, media.thumbnail_url or media.url, (CANVAS_WIDTH - CARD_PADDING * 2, MEDIA_HEIGHT))
        if media_image:
            canvas.paste(media_image, (CARD_PADDING, cursor_y))
            draw.rounded_rectangle(
                (
                    CARD_PADDING,
                    cursor_y,
                    CANVAS_WIDTH - CARD_PADDING,
                    cursor_y + MEDIA_HEIGHT,
                ),
                radius=24,
                outline=border_color,
                width=2,
            )
        cursor_y += MEDIA_HEIGHT + 24

    if config.show_timestamp and tweet.created_at:
        draw.text((CARD_PADDING, cursor_y), tweet.created_at, font=meta_font, fill=secondary_color)
        cursor_y += meta_font.size + 20

    if config.show_stats:
        cursor_y = _draw_stats(draw, tweet, meta_font, CARD_PADDING, cursor_y, secondary_color)

    output = io.BytesIO()
    canvas.save(output, format="PNG")
    return output.getvalue()

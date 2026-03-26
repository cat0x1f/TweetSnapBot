import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, List, Optional


LOGGER = logging.getLogger(__name__)
DEFAULT_CAPTION_TEMPLATE = (
    "From: {user_name} ({user_id})\n"
    "Tweet: {tweet_url}"
)


@dataclass
class RenderConfig:
    targets: List[int]
    theme: str = "light"
    logo: str = "x"
    format: str = "png"
    show_full_text: bool = True
    show_stats: bool = True
    show_timestamp: bool = True
    show_views: bool = True
    container_background: Optional[str] = None
    container_padding: Optional[int] = None
    border_radius: Optional[int] = None
    background_image: Optional[str] = None


@dataclass
class Settings:
    bot_token: str
    fxtwitter_api_base: str = "https://api.fxtwitter.com"
    log_level: str = "INFO"
    admin_user_ids: List[int] = field(default_factory=list)
    render_config: RenderConfig = field(default_factory=lambda: RenderConfig(targets=[]))
    caption_template: str = DEFAULT_CAPTION_TEMPLATE


def parse_bool(value: Any, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def parse_optional_int(value: Any) -> Optional[int]:
    if value in (None, ""):
        return None
    return int(value)


def load_json_env(name: str, default: Any) -> Any:
    raw = os.getenv(name, "").strip()
    if not raw:
        return default

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {name}: {exc}") from exc


def load_targets() -> List[int]:
    raw = load_json_env("TARGETS", [])
    if not isinstance(raw, list) or not raw:
        raise ValueError("TARGETS must be a non-empty JSON array")

    try:
        return [int(str(target)) for target in raw]
    except ValueError as exc:
        raise ValueError("TARGETS contains an invalid chat id") from exc


def load_admin_user_ids() -> List[int]:
    raw = load_json_env("ADMIN_USER_IDS", [])
    if not isinstance(raw, list):
        raise ValueError("ADMIN_USER_IDS must be a JSON array")

    try:
        return [int(str(user_id)) for user_id in raw]
    except ValueError as exc:
        raise ValueError("ADMIN_USER_IDS contains an invalid Telegram user id") from exc


def load_render_config() -> RenderConfig:
    return RenderConfig(
        targets=load_targets(),
        theme=os.getenv("THEME", "light").strip() or "light",
        logo=os.getenv("LOGO", "x").strip() or "x",
        format=os.getenv("FORMAT", "png").strip() or "png",
        show_full_text=parse_bool(os.getenv("SHOW_FULL_TEXT"), True),
        show_stats=parse_bool(os.getenv("SHOW_STATS"), True),
        show_timestamp=parse_bool(os.getenv("SHOW_TIMESTAMP"), True),
        show_views=parse_bool(os.getenv("SHOW_VIEWS"), True),
        container_background=os.getenv("CONTAINER_BACKGROUND") or None,
        container_padding=parse_optional_int(os.getenv("CONTAINER_PADDING")),
        border_radius=parse_optional_int(os.getenv("BORDER_RADIUS")),
        background_image=os.getenv("BACKGROUND_IMAGE") or None,
    )


def load_settings() -> Settings:
    bot_token = os.getenv("BOT_TOKEN", "").strip()
    fxtwitter_api_base = os.getenv("FXTWITTER_API_BASE", "https://api.fxtwitter.com").strip()
    log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
    caption_template = os.getenv("CAPTION_TEMPLATE", "").strip()

    if not bot_token:
        raise ValueError("BOT_TOKEN is required")

    settings = Settings(
        bot_token=bot_token,
        fxtwitter_api_base=fxtwitter_api_base,
        log_level=log_level,
        admin_user_ids=load_admin_user_ids(),
        render_config=load_render_config(),
        caption_template=caption_template or DEFAULT_CAPTION_TEMPLATE,
    )

    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    if not settings.admin_user_ids:
        LOGGER.warning("ADMIN_USER_IDS is empty; nobody can use the bot")

    if not settings.render_config.targets:
        raise ValueError("TARGETS must define at least one chat id")

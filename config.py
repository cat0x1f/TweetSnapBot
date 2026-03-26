import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


LOGGER = logging.getLogger(__name__)
DEFAULT_CAPTION_TEMPLATE = (
    "Session: {session}\n"
    "From: {user_name} ({user_id})\n"
    "Tweet: {tweet_url}"
)


@dataclass
class SessionConfig:
    name: str
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
    user_sessions: Dict[int, List[str]] = field(default_factory=dict)
    sessions: Dict[str, SessionConfig] = field(default_factory=dict)
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


def load_user_sessions() -> Dict[int, List[str]]:
    raw = load_json_env("USER_SESSIONS", {})
    if not isinstance(raw, dict):
        raise ValueError("USER_SESSIONS must be a JSON object")

    parsed: Dict[int, List[str]] = {}
    for user_id, sessions in raw.items():
        try:
            normalized_user_id = int(str(user_id))
        except ValueError as exc:
            raise ValueError(f"Invalid Telegram user id in USER_SESSIONS: {user_id}") from exc

        if not isinstance(sessions, list) or not all(isinstance(item, str) for item in sessions):
            raise ValueError(
                f"USER_SESSIONS[{user_id}] must be an array of session names"
            )

        parsed[normalized_user_id] = [item.strip() for item in sessions if item.strip()]

    return parsed


def load_sessions() -> Dict[str, SessionConfig]:
    raw = load_json_env("SESSIONS", {})
    if not isinstance(raw, dict):
        raise ValueError("SESSIONS must be a JSON object")

    sessions: Dict[str, SessionConfig] = {}
    for name, payload in raw.items():
        if not isinstance(payload, dict):
            raise ValueError(f"SESSIONS[{name}] must be an object")

        targets = payload.get("targets")
        if not isinstance(targets, list) or not targets:
            raise ValueError(f"SESSIONS[{name}].targets must be a non-empty array")

        try:
            normalized_targets = [int(str(target)) for target in targets]
        except ValueError as exc:
            raise ValueError(f"SESSIONS[{name}].targets contains an invalid chat id") from exc

        sessions[name] = SessionConfig(
            name=name,
            targets=normalized_targets,
            theme=str(payload.get("theme", "light")),
            logo=str(payload.get("logo", "x")),
            format=str(payload.get("format", "png")),
            show_full_text=parse_bool(payload.get("show_full_text"), True),
            show_stats=parse_bool(payload.get("show_stats"), True),
            show_timestamp=parse_bool(payload.get("show_timestamp"), True),
            show_views=parse_bool(payload.get("show_views"), True),
            container_background=payload.get("container_background"),
            container_padding=parse_optional_int(payload.get("container_padding")),
            border_radius=parse_optional_int(payload.get("border_radius")),
            background_image=payload.get("background_image"),
        )

    return sessions


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
        user_sessions=load_user_sessions(),
        sessions=load_sessions(),
        caption_template=caption_template or DEFAULT_CAPTION_TEMPLATE,
    )

    validate_settings(settings)
    return settings


def validate_settings(settings: Settings) -> None:
    if not settings.user_sessions:
        LOGGER.warning("USER_SESSIONS is empty; nobody can use the bot")

    if not settings.sessions:
        raise ValueError("SESSIONS must define at least one session")

    session_names = set(settings.sessions.keys())
    for user_id, allowed_sessions in settings.user_sessions.items():
        unknown_sessions = [name for name in allowed_sessions if name not in session_names]
        if unknown_sessions:
            raise ValueError(
                f"USER_SESSIONS[{user_id}] references unknown sessions: {unknown_sessions}"
            )

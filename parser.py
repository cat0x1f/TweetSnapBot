import re
from dataclasses import dataclass
from typing import List, Optional


STATUS_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:x\.com|twitter\.com)/(?P<screen_name>[A-Za-z0-9_]+)/status/(?P<status_id>\d+)",
    re.IGNORECASE,
)


@dataclass
class ParsedRequest:
    session_name: Optional[str]
    tweet_urls: List[str]


def extract_tweet_urls(text: str) -> List[str]:
    return [match.group(0) for match in STATUS_URL_RE.finditer(text or "")]


def extract_status_id(tweet_url: str) -> Optional[str]:
    match = STATUS_URL_RE.search(tweet_url.strip())
    if not match:
        return None
    return match.group("status_id")


def parse_request(text: str) -> ParsedRequest:
    stripped = (text or "").strip()
    if not stripped:
        return ParsedRequest(session_name=None, tweet_urls=[])

    parts = stripped.split()
    session_name: Optional[str] = None

    if parts and not parts[0].startswith("http"):
        session_name = parts[0]

    tweet_urls = extract_tweet_urls(stripped)
    return ParsedRequest(session_name=session_name, tweet_urls=tweet_urls)

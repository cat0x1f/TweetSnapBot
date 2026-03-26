import re
from dataclasses import dataclass
from typing import List, Optional


STATUS_URL_RE = re.compile(
    r"https?://(?:www\.)?(?:x\.com|twitter\.com)/(?P<screen_name>[A-Za-z0-9_]+)/status/(?P<status_id>\d+)",
    re.IGNORECASE,
)


@dataclass
class ParsedRequest:
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
        return ParsedRequest(tweet_urls=[])

    tweet_urls = extract_tweet_urls(stripped)
    return ParsedRequest(tweet_urls=tweet_urls)

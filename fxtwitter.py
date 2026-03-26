from dataclasses import dataclass, field
from typing import Dict, List, Optional

import requests

from parser import STATUS_URL_RE


@dataclass
class TweetMedia:
    url: str
    thumbnail_url: Optional[str] = None
    type: str = "photo"
    width: Optional[int] = None
    height: Optional[int] = None


@dataclass
class TweetAuthor:
    name: str
    screen_name: str
    avatar_url: Optional[str] = None


@dataclass
class TweetData:
    tweet_id: str
    url: str
    text: str
    created_at: str = ""
    likes: int = 0
    replies: int = 0
    retweets: int = 0
    views: int = 0
    author: TweetAuthor = field(default_factory=lambda: TweetAuthor(name="", screen_name=""))
    media: List[TweetMedia] = field(default_factory=list)


class FxTwitterClient:
    def __init__(self, api_base: str, timeout: int = 30) -> None:
        self.api_base = api_base.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/json"})

    def get_tweet(self, tweet_url: str) -> TweetData:
        match = STATUS_URL_RE.search(tweet_url.strip())
        if not match:
            raise ValueError(f"Unsupported tweet url: {tweet_url}")

        screen_name = match.group("screen_name")
        status_id = match.group("status_id")
        response = self.session.get(
            f"{self.api_base}/{screen_name}/status/{status_id}",
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        return self._parse_tweet_data(payload, tweet_url)

    def download_bytes(self, url: str) -> bytes:
        response = self.session.get(url, timeout=self.timeout)
        response.raise_for_status()
        return response.content

    def _parse_tweet_data(self, payload: Dict, tweet_url: str) -> TweetData:
        tweet = payload.get("tweet") or payload
        author_data = tweet.get("author") or {}
        stats = tweet.get("stats") or {}

        media: List[TweetMedia] = self._parse_media(tweet.get("media"))

        author = TweetAuthor(
            name=author_data.get("name") or author_data.get("display_name") or "",
            screen_name=author_data.get("screen_name") or author_data.get("screenName") or "",
            avatar_url=author_data.get("avatar_url") or author_data.get("avatarUrl"),
        )

        return TweetData(
            tweet_id=str(tweet.get("id") or tweet.get("tweet_id") or ""),
            url=tweet.get("url") or tweet_url,
            text=tweet.get("text") or tweet.get("content") or "",
            created_at=str(tweet.get("created_at") or tweet.get("date") or ""),
            likes=int(stats.get("likes") or tweet.get("likes") or 0),
            replies=int(stats.get("replies") or tweet.get("replies") or 0),
            retweets=int(stats.get("retweets") or tweet.get("retweets") or 0),
            views=int(stats.get("views") or tweet.get("views") or 0),
            author=author,
            media=[item for item in media if item.url],
        )

    def _parse_media(self, media_payload) -> List[TweetMedia]:
        if not media_payload:
            return []

        if isinstance(media_payload, list):
            return self._parse_media_items(media_payload)

        if not isinstance(media_payload, dict):
            return []

        ordered = media_payload.get("all")
        if isinstance(ordered, list) and ordered:
            return self._parse_media_items(ordered)

        photos = media_payload.get("photos") or []
        items: List[Dict] = []
        if isinstance(photos, list):
            items.extend(item for item in photos if isinstance(item, dict))

        return self._parse_media_items(items)

    def _parse_media_items(self, media_items: List[Dict]) -> List[TweetMedia]:
        media: List[TweetMedia] = []
        for item in media_items:
            if not isinstance(item, dict):
                continue
            media_type = str(item.get("type") or "photo")
            if "video" in media_type.lower() or "gif" in media_type.lower():
                continue
            media.append(
                TweetMedia(
                    url=(
                        item.get("url")
                        or item.get("source")
                        or item.get("media_url")
                        or item.get("mediaUrl")
                        or item.get("image_url")
                        or item.get("imageUrl")
                        or ""
                    ),
                    thumbnail_url=(
                        item.get("thumbnail_url")
                        or item.get("thumbnailUrl")
                        or item.get("thumb_url")
                        or item.get("thumbUrl")
                    ),
                    type=media_type,
                    width=item.get("width"),
                    height=item.get("height"),
                )
            )
        return media

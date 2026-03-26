import unittest
from unittest.mock import MagicMock, patch

from fxtwitter import FxTwitterClient


class FxTwitterTests(unittest.TestCase):
    @patch("fxtwitter.requests.Session.get")
    def test_get_tweet_uses_path_style_endpoint(self, mock_get) -> None:
        response = MagicMock()
        response.json.return_value = {"tweet": {"id": "123", "author": {}, "media": []}}
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        client = FxTwitterClient("https://api.fxtwitter.com")
        client.get_tweet("https://x.com/example/status/123")

        mock_get.assert_called_once_with(
            "https://api.fxtwitter.com/example/status/123",
            timeout=30,
        )

    def test_parse_tweet_data(self) -> None:
        client = FxTwitterClient("https://api.fxtwitter.com")
        payload = {
            "tweet": {
                "id": "123",
                "url": "https://x.com/example/status/123",
                "text": "中文测试 hello world",
                "created_at": "2026-03-26",
                "author": {
                    "name": "测试用户",
                    "screen_name": "example",
                    "avatar_url": "https://example.com/avatar.jpg",
                },
                "media": [{"url": "https://example.com/image.jpg", "type": "photo"}],
                "stats": {"likes": 3, "replies": 2, "retweets": 1, "views": 10},
            }
        }
        tweet = client._parse_tweet_data(payload, "https://x.com/example/status/123")
        self.assertEqual(tweet.tweet_id, "123")
        self.assertEqual(tweet.author.screen_name, "example")
        self.assertEqual(tweet.media[0].url, "https://example.com/image.jpg")
        self.assertEqual(tweet.views, 10)
        self.assertEqual(tweet.author.name, "测试用户")

    def test_parse_tweet_data_accepts_alternate_media_fields(self) -> None:
        client = FxTwitterClient("https://api.fxtwitter.com")
        payload = {
            "tweet": {
                "id": "456",
                "author": {},
                "media": [
                    {
                        "media_url": "https://example.com/1.jpg",
                        "thumbUrl": "https://example.com/1-thumb.jpg",
                    },
                    {
                        "imageUrl": "https://example.com/2.jpg",
                    },
                ],
            }
        }
        tweet = client._parse_tweet_data(payload, "https://x.com/example/status/456")
        self.assertEqual(len(tweet.media), 2)
        self.assertEqual(tweet.media[0].url, "https://example.com/1.jpg")
        self.assertEqual(tweet.media[0].thumbnail_url, "https://example.com/1-thumb.jpg")
        self.assertEqual(tweet.media[1].url, "https://example.com/2.jpg")

    def test_parse_tweet_data_accepts_wiki_media_object_shape(self) -> None:
        client = FxTwitterClient("https://api.fxtwitter.com")
        payload = {
            "tweet": {
                "id": "789",
                "author": {},
                "media": {
                    "photos": [
                        {"url": "https://example.com/p1.jpg", "type": "photo"},
                        {"url": "https://example.com/p2.jpg", "type": "photo"},
                    ],
                    "videos": [{"url": "https://example.com/video.mp4", "type": "video"}],
                },
            }
        }
        tweet = client._parse_tweet_data(payload, "https://x.com/example/status/789")
        self.assertEqual(len(tweet.media), 2)
        self.assertEqual(tweet.media[0].url, "https://example.com/p1.jpg")
        self.assertEqual(tweet.media[1].url, "https://example.com/p2.jpg")


if __name__ == "__main__":
    unittest.main()

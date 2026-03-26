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
                "text": "hello world",
                "created_at": "2026-03-26",
                "author": {
                    "name": "Example",
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


if __name__ == "__main__":
    unittest.main()

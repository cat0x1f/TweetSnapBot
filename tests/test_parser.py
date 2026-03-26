import unittest

from parser import extract_status_id, parse_request


class ParserTests(unittest.TestCase):
    def test_parse_request_with_explicit_session(self) -> None:
        parsed = parse_request("ops https://x.com/example/status/1234567890")
        self.assertEqual(parsed.session_name, "ops")
        self.assertEqual(parsed.tweet_urls, ["https://x.com/example/status/1234567890"])

    def test_parse_request_without_session(self) -> None:
        parsed = parse_request("https://twitter.com/example/status/1234567890")
        self.assertIsNone(parsed.session_name)
        self.assertEqual(parsed.tweet_urls, ["https://twitter.com/example/status/1234567890"])

    def test_extract_status_id(self) -> None:
        self.assertEqual(
            extract_status_id("https://x.com/example/status/1234567890"),
            "1234567890",
        )


if __name__ == "__main__":
    unittest.main()

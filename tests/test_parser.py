import unittest

from parser import extract_status_id, parse_request


class ParserTests(unittest.TestCase):
    def test_parse_request_extracts_urls_from_message(self) -> None:
        parsed = parse_request("ops https://x.com/example/status/1234567890")
        self.assertEqual(parsed.tweet_urls, ["https://x.com/example/status/1234567890"])

    def test_parse_request_without_urls(self) -> None:
        parsed = parse_request("ops")
        self.assertEqual(parsed.tweet_urls, [])

    def test_parse_request_with_plain_url(self) -> None:
        parsed = parse_request("https://twitter.com/example/status/1234567890")
        self.assertEqual(parsed.tweet_urls, ["https://twitter.com/example/status/1234567890"])

    def test_parse_request_with_fixupx_url(self) -> None:
        parsed = parse_request("https://fixupx.com/example/status/1234567890")
        self.assertEqual(parsed.tweet_urls, ["https://fixupx.com/example/status/1234567890"])

    def test_parse_request_with_fxtwitter_url(self) -> None:
        parsed = parse_request("https://fxtwitter.com/example/status/1234567890?s=20")
        self.assertEqual(parsed.tweet_urls, ["https://fxtwitter.com/example/status/1234567890"])

    def test_parse_request_with_mirror_urls(self) -> None:
        for host in ("vxtwitter.com", "fixvx.com", "twittpr.com", "twittervx.com"):
            with self.subTest(host=host):
                url = f"https://{host}/example/status/1234567890"
                self.assertEqual(parse_request(url).tweet_urls, [url])

    def test_parse_request_with_subdomain_url(self) -> None:
        parsed = parse_request("https://mobile.twitter.com/example/status/1234567890")
        self.assertEqual(
            parsed.tweet_urls,
            ["https://mobile.twitter.com/example/status/1234567890"],
        )

    def test_parse_request_ignores_lookalike_domain(self) -> None:
        parsed = parse_request("https://notx.com/example/status/1234567890")
        self.assertEqual(parsed.tweet_urls, [])

    def test_extract_status_id(self) -> None:
        self.assertEqual(
            extract_status_id("https://x.com/example/status/1234567890"),
            "1234567890",
        )

    def test_extract_status_id_from_fixupx(self) -> None:
        self.assertEqual(
            extract_status_id("https://fixupx.com/example/status/1234567890"),
            "1234567890",
        )


if __name__ == "__main__":
    unittest.main()

import json
import unittest
from unittest.mock import patch

from config import DEFAULT_CAPTION_TEMPLATE, load_sessions, load_settings, load_user_sessions


class ConfigTests(unittest.TestCase):
    def test_load_user_sessions(self) -> None:
        with patch.dict("os.environ", {"USER_SESSIONS": json.dumps({"123": ["default", "ops"]})}):
            self.assertEqual(load_user_sessions(), {123: ["default", "ops"]})

    def test_load_sessions(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "SESSIONS": json.dumps(
                    {
                        "default": {
                            "targets": [123, -1001],
                            "theme": "dark",
                            "format": "png",
                        }
                    }
                )
            },
        ):
            sessions = load_sessions()
            self.assertEqual(sessions["default"].targets, [123, -1001])
            self.assertEqual(sessions["default"].theme, "dark")

    def test_load_settings(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "BOT_TOKEN": "token",
                "USER_SESSIONS": json.dumps({"123": ["default"]}),
                "SESSIONS": json.dumps({"default": {"targets": [123]}}),
            },
        ):
            settings = load_settings()
            self.assertEqual(settings.caption_template, DEFAULT_CAPTION_TEMPLATE)
            self.assertEqual(settings.user_sessions, {123: ["default"]})
            self.assertEqual(settings.fxtwitter_api_base, "https://api.fxtwitter.com")


if __name__ == "__main__":
    unittest.main()

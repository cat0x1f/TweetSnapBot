import json
import unittest
from unittest.mock import patch

from config import DEFAULT_CAPTION_TEMPLATE, load_admin_user_ids, load_render_config, load_settings


class ConfigTests(unittest.TestCase):
    def test_load_admin_user_ids(self) -> None:
        with patch.dict("os.environ", {"ADMIN_USER_IDS": json.dumps([123, 456])}):
            self.assertEqual(load_admin_user_ids(), [123, 456])

    def test_load_render_config(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "TARGETS": json.dumps([123, -1001]),
                "THEME": "dark",
                "FORMAT": "png",
            },
        ):
            render_config = load_render_config()
            self.assertEqual(render_config.targets, [123, -1001])
            self.assertEqual(render_config.theme, "dark")

    def test_load_settings(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "BOT_TOKEN": "token",
                "ADMIN_USER_IDS": json.dumps([123]),
                "TARGETS": json.dumps([123]),
            },
        ):
            settings = load_settings()
            self.assertEqual(settings.caption_template, DEFAULT_CAPTION_TEMPLATE)
            self.assertEqual(settings.admin_user_ids, [123])
            self.assertEqual(settings.render_config.targets, [123])
            self.assertEqual(settings.fxtwitter_api_base, "https://api.fxtwitter.com")


if __name__ == "__main__":
    unittest.main()

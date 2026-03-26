import unittest

from PIL import Image, ImageDraw

from renderer import FONTS_DIR, _is_emoji, _layout_text, _load_font


class FontTests(unittest.TestCase):
    def test_project_fonts_exist(self) -> None:
        self.assertTrue((FONTS_DIR / "SourceHanSans.ttf").exists())
        self.assertTrue((FONTS_DIR / "Emoji.ttf").exists())


class RendererTests(unittest.TestCase):
    def test_wrap_text_supports_chinese_without_spaces(self) -> None:
        image = Image.new("RGB", (400, 200), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        font = _load_font(28)
        emoji_font = _load_font(28, emoji=True)
        lines = _layout_text(draw, "这是一段没有空格的中文文本用于自动换行测试", font, emoji_font, 140)
        self.assertGreater(len(lines), 1)

    def test_layout_text_uses_emoji_font_for_emoji(self) -> None:
        image = Image.new("RGB", (400, 200), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        font = _load_font(28)
        emoji_font = _load_font(28, emoji=True)
        lines = _layout_text(draw, "hello🙂", font, emoji_font, 400)
        self.assertTrue(_is_emoji("🙂"))
        self.assertTrue(any(item[1] is emoji_font for item in lines[0] if item[0] == "🙂"))


if __name__ == "__main__":
    unittest.main()

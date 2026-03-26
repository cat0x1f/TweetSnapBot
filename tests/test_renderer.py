import unittest

from PIL import Image, ImageDraw

from renderer import (
    FONTS_DIR,
    _draw_rich_text,
    _is_emoji,
    _layout_text,
    _load_font,
    _measure_text_block,
    _segment_text,
)


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

    def test_segment_text_keeps_emoji_sequences_together(self) -> None:
        self.assertIn("🧑‍💻", _segment_text("A🧑‍💻B"))
        self.assertIn("🇨🇳", _segment_text("A🇨🇳B"))
        self.assertIn("👍🏻", _segment_text("A👍🏻B"))

    def test_layout_text_handles_long_text(self) -> None:
        image = Image.new("RGB", (400, 200), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        font = _load_font(28)
        emoji_font = _load_font(28, emoji=True)
        lines = _layout_text(draw, "这是一段很长的文本" * 20, font, emoji_font, 120)
        self.assertGreater(len(lines), 3)

    def test_measure_text_block_matches_drawn_height(self) -> None:
        image = Image.new("RGB", (800, 4000), (255, 255, 255))
        draw = ImageDraw.Draw(image)
        font = _load_font(28)
        emoji_font = _load_font(28, emoji=True)
        lines, measured_height = _measure_text_block(
            draw,
            ("超长文本🙂" * 50),
            font,
            emoji_font,
            240,
        )
        drawn_height = _draw_rich_text(draw, 0, 0, lines, (0, 0, 0))
        self.assertGreaterEqual(measured_height, drawn_height)


if __name__ == "__main__":
    unittest.main()

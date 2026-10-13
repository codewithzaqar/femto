import unittest

from femto.theme import (
    load_theme,
    nearest_xterm_256,
    parse_color,
    xterm_256_rgb,
)


class TestParseColor(unittest.TestCase):
    def test_parse_rgb(self):
        self.assertEqual(parse_color("rgb(12,34,56)"), (12, 34, 56))

    def test_parse_hex(self):
        self.assertEqual(parse_color("#0c2238"), (12, 34, 56))
        self.assertEqual(parse_color("#FFFFFF"), (255, 255, 255))

    def test_parse_index(self):
        self.assertEqual(parse_color("index(42)"), 42)
        self.assertEqual(parse_color("42"), 42)

    def test_parse_default(self):
        self.assertIsNone(parse_color("default"))

    def test_reject_invalid_colors(self):
        for value in ("rgb(256,0,0)", "index(256)", "#12345", "#GGGGGG", "not-a-color"):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    parse_color(value)


class TestXtermColors(unittest.TestCase):
    def test_known_palette_colors(self):
        self.assertEqual(xterm_256_rgb(0), (0, 0, 0))
        self.assertEqual(xterm_256_rgb(15), (255, 255, 255))

    def test_nearest_exact_colors(self):
        self.assertEqual(nearest_xterm_256((0, 0, 0)), 16)
        self.assertEqual(nearest_xterm_256((255, 255, 255)), 231)

    def test_reject_invalid_index(self):
        with self.assertRaises(ValueError):
            xterm_256_rgb(256)


class TestLoadTheme(unittest.TestCase):
    def test_all_builtin_themes_load(self):
        for name in (
            "default",
            "solarized-dark",
            "solarized-light",
            "default-light",
            "high-contrast",
        ):
            with self.subTest(theme=name):
                theme = load_theme(name)
                self.assertEqual(len(theme), 10)
                self.assertIn("status_bar", theme)
                self.assertIn("keyword", theme)

    def test_reject_invalid_theme_name(self):
        with self.assertRaises(ValueError):
            load_theme("../default")


if __name__ == "__main__":
    unittest.main()


class TestRendererColorFallback(unittest.TestCase):
    def test_eight_color_terminal_uses_supported_color_indices(self):
        from unittest.mock import patch
        from femto.renderer import Renderer

        renderer = Renderer.__new__(Renderer)
        renderer.config = type("ConfigStub", (), {"theme": "default"})()

        with (
            patch("femto.renderer.curses.start_color"),
            patch("femto.renderer.curses.use_default_colors"),
            patch("femto.renderer.curses.can_change_color", return_value=False),
            patch("femto.renderer.curses.COLORS", 8, create=True),
            patch("femto.renderer.curses.COLOR_PAIRS", 256, create=True),
            patch("femto.renderer.curses.init_pair") as init_pair,
            patch("femto.renderer.curses.color_pair", side_effect=lambda n: n),
        ):
            renderer.setup_colors()

        self.assertEqual(init_pair.call_count, 10)
        for call in init_pair.call_args_list:
            _, foreground, background = call.args
            for color in (foreground, background):
                self.assertTrue(color == -1 or 0 <= color < 8)

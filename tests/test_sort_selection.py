"""Regression tests for sort-selection mark handling."""

import unittest

from femto.app import Application
from femto.keys import Key


class TestSortSelectionConsumption(unittest.TestCase):
    def test_sort_consumes_mark_and_allows_consecutive_sort(self):
        app = Application(None)
        app.config.auto_indent = False
        app.buffer.lines = ["b", "A", "c"]

        app.cursor.set_pos(0, 0, app.buffer.get_line_length, app.buffer.max_y)
        app._handle_normal(Key.CTRL_B, 24, 80)
        app.cursor.set_pos(0, 2, app.buffer.get_line_length, app.buffer.max_y)
        app._handle_normal(Key.ALT_S, 24, 80)

        self.assertEqual(app.buffer.lines, ["A", "b", "c"])
        self.assertFalse(app.selection.active)

        app.buffer.lines = ["b", "A", "c"]
        app.cursor.set_pos(0, 0, app.buffer.get_line_length, app.buffer.max_y)
        app._handle_normal(Key.CTRL_B, 24, 80)
        self.assertTrue(app.selection.active)
        app.cursor.set_pos(0, 2, app.buffer.get_line_length, app.buffer.max_y)
        app._handle_normal(Key.ALT_SHIFT_S, 24, 80)

        self.assertEqual(app.buffer.lines, ["A", "b", "c"])
        self.assertFalse(app.selection.active)


if __name__ == "__main__":
    unittest.main()

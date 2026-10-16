"""
Unit tests for column/rectangular selection.
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from femto.buffer import Buffer
from femto.clipboard import Selection
from femto.config import Config


class TestColumnSelection(unittest.TestCase):
    def setUp(self):
        self.buf = Buffer(Config())
        self.buf.lines = ["hello world", "foo   bar", "abc   xyz"]
        self.sel = Selection()

    def test_toggle_column_mode(self):
        self.sel.toggle(0, 0, column_mode=True)
        self.assertTrue(self.sel.active)
        self.assertTrue(self.sel.column_mode)
        
        # Toggle again should clear
        self.sel.toggle(5, 2, column_mode=True)
        self.assertFalse(self.sel.active)
        self.assertFalse(self.sel.column_mode)

    def test_column_bounds_normalized(self):
        self.sel.toggle(6, 0, column_mode=True)
        bounds = self.sel.bounds(self.buf, 2, 2)
        
        # Column mode: columns always min-to-max
        (sx, sy), (ex, ey) = bounds
        self.assertEqual(sx, 2)
        self.assertEqual(ex, 6)
        self.assertEqual(sy, 0)
        self.assertEqual(ey, 2)

    def test_extract_rectangle(self):
        self.sel.toggle(0, 0, column_mode=True)
        bounds = self.sel.bounds(self.buf, 5, 2)
        text = self.sel.extract(self.buf, bounds)
        
        # 3 lines, 5 chars each
        self.assertEqual(text, "hello\nfoo  \nabc  ")

    def test_delete_rectangle(self):
        self.sel.toggle(0, 0, column_mode=True)
        bounds = self.sel.bounds(self.buf, 5, 2)
        nx, ny = self.sel.delete_range(self.buf, bounds)
        
        # 5 chars removed from each line (indices 0-4)
        self.assertEqual(self.buf.lines, [" world", " bar", " xyz"])
        self.assertEqual((nx, ny), (0, 0))

    def test_linear_mode_preserved(self):
        # Normal (linear) selection should still work
        self.sel.toggle(0, 0, column_mode=False)
        self.assertFalse(self.sel.column_mode)
        
        bounds = self.sel.bounds(self.buf, 5, 1)
        text = self.sel.extract(self.buf, bounds)
        
        # Linear extraction across two lines
        self.assertEqual(text, "hello world\nfoo  ")


if __name__ == "__main__":
    unittest.main()

"""
Unit tests for whitespace hygiene features.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from femto.buffer import Buffer
from femto.config import Config

try:
    from femto.app import Application
    HAVE_APP = True
except Exception:
    HAVE_APP = False


@unittest.skipUnless(HAVE_APP, "curses not importable on this machine")
class TestWhitespaceHygiene(unittest.TestCase):
    def test_trim_trailing_whitespace(self):
        app = Application(None)
        app.buffer.lines = ["hello   ", "world\t\t", "clean"]
        app.cursor.set_pos(8, 0, app.buffer.get_line_length, app.buffer.max_y)
        
        trimmed = app._trim_trailing_whitespace()
        
        self.assertTrue(trimmed)
        self.assertEqual(app.buffer.lines, ["hello", "world", "clean"])
        # Cursor should clamp to end of line if it was in the trimmed space
        self.assertEqual(app.cursor.x, 5) 

    def test_trim_does_nothing_if_clean(self):
        app = Application(None)
        app.buffer.lines = ["hello", "world"]
        
        trimmed = app._trim_trailing_whitespace()
        
        self.assertFalse(trimmed)
        self.assertEqual(app.buffer.lines, ["hello", "world"])

    def test_save_with_trim_on_save_flag(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "test.txt")
            with open(path, "w") as f:
                f.write("hello   \nworld\t\n")
                
            cfg = Config()
            cfg.trim_on_save = True
            
            app = Application(None, initial_files=[path])
            app.config = cfg
            app._save()
            
            with open(path, "r") as f:
                content = f.read()
                
            self.assertEqual(content, "hello\nworld\n")


if __name__ == "__main__":
    unittest.main()

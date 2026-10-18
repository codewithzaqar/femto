"""
Unit tests for snippet expansion.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from femto.snippets import Snippet, load_snippets, snippets_for_file

try:
    from femto.app import Application
    HAVE_APP = True
except Exception:
    HAVE_APP = False


class TestSnippetParsing(unittest.TestCase):
    def test_plain_text_replaces_stops(self):
        s = Snippet("if", "if ${1:condition}:\\n    ${2:pass}")
        self.assertEqual(s.plain_text(), "if condition:\n    pass")

    def test_stop_positions(self):
        s = Snippet("if", "if ${1:condition}:\\n    ${2:pass}")
        self.assertEqual(s.stop_positions(), [(3, 9), (18, 4)])

    def test_load_defaults(self):
        snippets = load_snippets(os.path.join(tempfile.gettempdir(),
                                              "nonexistent-snippets.ini"))
        self.assertIn("python", snippets)
        self.assertIn("if", snippets["python"])

    def test_custom_ini(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "snippets.ini")
            with open(path, "w") as f:
                f.write("[python]\nmyloop = while ${1:True}:\\n    ${2:pass}\n")
            snippets = load_snippets(path)
            self.assertIn("myloop", snippets["python"])

    def test_snippets_for_file_merges_global(self):
        snippets = load_snippets(os.path.join(tempfile.gettempdir(),
                                              "nonexistent-snippets.ini"))
        merged = snippets_for_file(snippets, "test.py")
        self.assertIn("if", merged)      # python section
        self.assertIn("todo", merged)    # global section


@unittest.skipUnless(HAVE_APP, "curses not importable on this machine")
class TestSnippetExpansion(unittest.TestCase):
    def test_expand_if_snippet(self):
        app = Application(None)
        app.buffer.filename = "test.py"
        app.buffer.lines = ["if"]
        app.cursor.set_pos(2, 0, app.buffer.get_line_length, app.buffer.max_y)

        self.assertTrue(app._try_expand_snippet())
        self.assertEqual(app.buffer.lines, ["if condition:", "    pass"])
        self.assertIsNotNone(app.snippet_state)
        # Placeholder "condition" is selected
        self.assertTrue(app.selection.active)

        # Typing replaces the placeholder
        app._handle_normal("x", 24, 80)
        self.assertEqual(app.buffer.lines[0], "if x:")

    def test_tab_moves_between_stops(self):
        app = Application(None)
        app.buffer.filename = "test.py"
        app.buffer.lines = ["def"]
        app.cursor.set_pos(3, 0, app.buffer.get_line_length, app.buffer.max_y)

        app._try_expand_snippet()
        self.assertEqual(app.snippet_state['index'], 0)
        app._snippet_next()
        self.assertEqual(app.snippet_state['index'], 1)
        app._snippet_next()
        self.assertEqual(app.snippet_state['index'], 2)
        app._snippet_next()   # past last stop -> exits snippet mode
        self.assertIsNone(app.snippet_state)

    def test_no_trigger_does_not_expand(self):
        app = Application(None)
        app.buffer.filename = "test.py"
        app.buffer.lines = ["hello"]
        app.cursor.set_pos(5, 0, app.buffer.get_line_length, app.buffer.max_y)
        self.assertFalse(app._try_expand_snippet())


if __name__ == "__main__":
    unittest.main()

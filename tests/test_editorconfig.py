"""EditorConfig integration tests."""

import os
import tempfile
import unittest

from femto.app import Application
from femto.config import Config
from femto.documents import Document


def write_file(path, content):
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(content)


class TestEditorConfig(unittest.TestCase):
    def test_matching_glob_applies_file_settings(self):
        with tempfile.TemporaryDirectory() as td:
            nested = os.path.join(td, "src", "pkg")
            os.makedirs(nested)
            write_file(
                os.path.join(td, ".editorconfig"),
                "root = true\n"
                "\n"
                "[*.py]\n"
                "indent_size = 2\n"
                "end_of_line = crlf\n"
                "insert_final_newline = false\n"
                "\n"
                "[*.js]\n"
                "indent_size = 8\n",
            )

            path = os.path.join(nested, "example.py")
            write_file(path, "pass")
            config = Config().for_file(path)

            self.assertEqual(config.tab_size, 2)
            self.assertEqual(config.line_ending, "crlf")
            self.assertFalse(config.final_newline)

    def test_nearest_editorconfig_wins(self):
        with tempfile.TemporaryDirectory() as td:
            child = os.path.join(td, "child")
            os.makedirs(child)
            write_file(
                os.path.join(td, ".editorconfig"),
                "[*.py]\nindent_size = 2\n",
            )
            write_file(
                os.path.join(child, ".editorconfig"),
                "[*.py]\nindent_size = 6\n",
            )

            path = os.path.join(child, "example.py")
            write_file(path, "pass")

            self.assertEqual(Config().for_file(path).tab_size, 6)

    def test_root_stops_parent_lookup(self):
        with tempfile.TemporaryDirectory() as td:
            child = os.path.join(td, "child")
            os.makedirs(child)
            write_file(
                os.path.join(td, ".editorconfig"),
                "[*.py]\nindent_size = 2\n",
            )
            write_file(
                os.path.join(child, ".editorconfig"),
                "root = true\n[*.py]\nend_of_line = crlf\n",
            )

            path = os.path.join(child, "example.py")
            write_file(path, "pass")

            base = Config()
            base.tab_size = 7
            config = base.for_file(path)

            self.assertEqual(config.tab_size, 7)
            self.assertEqual(config.line_ending, "crlf")

    def test_document_saves_with_file_settings(self):
        with tempfile.TemporaryDirectory() as td:
            write_file(
                os.path.join(td, ".editorconfig"),
                "root = true\n"
                "[*.py]\n"
                "end_of_line = crlf\n"
                "insert_final_newline = false\n",
            )

            path = os.path.join(td, "example.py")
            write_file(path, "one\ntwo")

            doc = Document(Config(), path)
            self.assertTrue(doc.buffer.save())

            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"one\r\ntwo")

    def test_auto_indent_uses_file_indent_size(self):
        with tempfile.TemporaryDirectory() as td:
            write_file(
                os.path.join(td, ".editorconfig"),
                "root = true\n[*.py]\nindent_style = space\nindent_size = 2\n",
            )

            path = os.path.join(td, "example.py")
            write_file(path, "if True:")

            app = Application(None, initial_files=[path])
            app.cursor.set_pos(
                len("if True:"),
                0,
                app.buffer.get_line_length,
                app.buffer.max_y,
            )
            app._handle_normal(10, 24, 80)

            self.assertEqual(app.buffer.lines, ["if True:", "  "])


if __name__ == "__main__":
    unittest.main()

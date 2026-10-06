"""
Regression test-suite for Femto (stdlib unittest, headless-safe).

Run from the project root with either:
    python -m unittest discover -s tests -v
    python tests/test_femto.py
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from femto.buffer import Buffer, detect_newline, resolve_newline
from femto.clipboard import Clipboard, Selection
from femto.config import Config
from femto.cursor import Cursor
from femto.documents import Document
from femto.history import History
from femto.keys import Key, alt
from femto.layout import (
    chunk_line,
    col_to_index,
    get_logical_from_visual,
    get_logical_from_visual_point,
    get_visual_position,
    line_row_count,
)
from femto.search import SearchOptions, find_in_line, find_next

try:
    from femto.app import Application
    HAVE_APP = True
except Exception:
    HAVE_APP = False


class TestBuffer(unittest.TestCase):
    def setUp(self):
        self.buf = Buffer(Config())

    def test_insert_and_delete(self):
        self.buf.insert_char(0, 0, "a")
        self.buf.insert_char(1, 0, "b")
        self.assertEqual(self.buf.lines[0], "ab")
        self.buf.delete_char(0, 0)
        self.assertEqual(self.buf.lines[0], "b")

    def test_backspace_merges_lines(self):
        self.buf.lines = ["foo", "bar"]
        x, y = self.buf.backspace(0, 1)
        self.assertEqual((x, y), (3, 0))
        self.assertEqual(self.buf.lines, ["foobar"])

    def test_tab_uses_config_size(self):
        cfg = Config()
        cfg.tab_size = 2
        buf = Buffer(cfg)
        new_x = buf.insert_tab(0, 0)
        self.assertEqual(new_x, 2)
        self.assertEqual(buf.lines[0], "  ")

    def test_word_navigation(self):
        self.buf.lines = ["hello world foo"]
        self.assertEqual(self.buf.get_next_word_pos(0, 0), 6)
        self.assertEqual(self.buf.get_prev_word_pos(0, 11), 6)

    def test_search_wraps(self):
        self.buf.lines = ["abc", "xxx", "abc"]
        self.assertEqual(self.buf.find_text("abc", 0, 0), (0, 0))
        self.assertEqual(self.buf.find_text("abc", 1, 0), (0, 2))

    def test_save_load_roundtrip(self):
        with tempfile.NamedTemporaryFile("w", suffix=".txt",
                                         delete=False) as fh:
            path = fh.name
        try:
            self.buf.lines = ["one", "two"]
            self.buf.filename = path
            self.assertTrue(self.buf.save())
            other = Buffer(Config())
            other.load_file(path)
            self.assertEqual(other.lines, ["one", "two"])
        finally:
            os.unlink(path)


class TestHistoryMemory(unittest.TestCase):
    def test_undo_redo(self):
        h = History()
        h.push(["a"], 1, 0)
        lines, x, y = h.undo(["ab"], 2, 0)
        self.assertEqual((lines, x, y), (["a"], 1, 0))
        lines, x, y = h.redo(["a"], 1, 0)
        self.assertEqual((lines, x, y), (["ab"], 2, 0))

    def test_new_edit_clears_redo(self):
        h = History()
        h.push(["a"], 1, 0)
        h.undo(["ab"], 2, 0)
        h.push(["a"], 1, 0)
        self.assertFalse(h.can_redo)

    def test_interning_bounds_memory(self):
        h = History()
        big = ["line %d" % i for i in range(5000)]
        for _ in range(50):
            h.push(big, 0, 0)
        # Identical lines intern to the same IDs: tab stays tiny
        self.assertLess(len(h._ids), 5001)
        self.assertEqual(len(h.undo_stack[-1][2]), 5000)


class TestLayout(unittest.TestCase):
    def test_row_count(self):
        self.assertEqual(line_row_count(0, 10), 1)
        self.assertEqual(line_row_count(10, 10), 1)
        self.assertEqual(line_row_count(11, 10), 2)

    def test_visual_position_wrap(self):
        lines = ["0123456789ABCDE"]
        vx, vy = get_visual_position(12, 0, lines, 10)
        self.assertEqual((vx, vy), (2, 1))

    def test_visual_position_line_end_wrap(self):
        lines = ["0123456789"]
        vx, vy = get_visual_position(10, 0, lines, 10)
        self.assertEqual((vx, vy), (0, 1))

    def test_logical_from_visual_roundtrip(self):
        lines = ["0123456789ABCDE", "short", ""]
        for y in range(len(lines)):
            vx, vy = get_visual_position(0, y, lines, 10)
            self.assertEqual(get_logical_from_visual(vy, lines, 10), y)

    def test_chunk_line(self):
        self.assertEqual(chunk_line("", 5), [""])
        self.assertEqual(chunk_line("abcdefg", 3), ["abc", "def", "g"])


class TestCursorScroll(unittest.TestCase):
    def test_smooth_scroll_clamps(self):
        c = Cursor()
        c.update_scroll(0, 0, 20, 80, 3)
        self.assertEqual(c.scroll_y, 0)
        c.update_scroll(50, 0, 20, 80, 3)
        self.assertGreater(c.scroll_y, 0)
        self.assertLessEqual(50, c.scroll_y + 20 - 1)

    def test_hard_wrap_horizontal(self):
        c = Cursor()
        c.update_scroll(0, 100, 20, 80, 3, soft_wrap=False)
        self.assertGreater(c.scroll_x, 0)
        self.assertLessEqual(100, c.scroll_x + 80 - 1)


class TestConfig(unittest.TestCase):
    def test_parse(self):
        with tempfile.NamedTemporaryFile("w", suffix="rc",
                                         delete=False) as fh:
            fh.write(
                "# comment\n"
                "tab_size = 8\n"
                "soft_wrap = false\n"
                "line_ending = crlf\n"
                "final_newline = false\n"
                "auto_indent = false\n"
                "mouse = true\n"
            )
            path = fh.name
        try:
            cfg = Config()
            cfg._parse(path)
            self.assertEqual(cfg.tab_size, 8)
            self.assertFalse(cfg.soft_wrap)
            self.assertEqual(cfg.line_ending, "crlf")
            self.assertFalse(cfg.final_newline)
            self.assertFalse(cfg.auto_indent)
            self.assertTrue(cfg.mouse)
        finally:
            os.unlink(path)


class TestSelectionClipboard(unittest.TestCase):
    def setUp(self):
        self.buf = Buffer(Config())
        self.buf.lines = ["hello world", "second line", "third"]
        self.sel = Selection()
        self.clip = Clipboard()

    def test_extract_multiline(self):
        self.sel.toggle(5, 0)
        bounds = self.sel.bounds(self.buf, 6, 1)
        self.assertEqual(self.sel.extract(self.buf, bounds),
                         " world\nsecond")

    def test_delete_range(self):
        self.sel.toggle(5, 0)
        bounds = self.sel.bounds(self.buf, 6, 1)
        nx, ny = self.sel.delete_range(self.buf, bounds)
        self.assertEqual(self.buf.lines, ["hello line", "third"])
        self.assertEqual((nx, ny), (5, 0))

    def test_bounds_clamped_after_shrink(self):
        self.sel.toggle(10, 2)
        self.buf.lines = ["ab"]
        bounds = self.sel.bounds(self.buf, 0, 0)
        self.assertEqual(bounds, ((0, 0), (2, 0)))

    def test_paste_single_line(self):
        self.clip.store("AB")
        x, y = self.clip.paste_into(self.buf, 5, 0)
        self.assertEqual(self.buf.lines[0], "helloAB world")
        self.assertEqual((x, y), (7, 0))

    def test_paste_multiline(self):
        self.clip.store("L1\nL2")
        x, y = self.clip.paste_into(self.buf, 0, 2)
        self.assertEqual(self.buf.lines[2:4], ["L1", "L2third"])
        self.assertEqual((x, y), (2, 3))


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.buf = Buffer(Config())
        self.buf.lines = ["Hello WORLD", "world peace", "wrap up"]

    def test_plain_case_sensitive(self):
        self.assertEqual(find_next(self.buf, "world", SearchOptions(), 0, 0),
                         (0, 1, 5))

    def test_ignore_case(self):
        opt = SearchOptions(ignore_case=True)
        self.assertEqual(find_next(self.buf, "world", opt, 0, 0), (6, 0, 5))

    def test_regex(self):
        opt = SearchOptions(regex=True)
        self.assertEqual(find_next(self.buf, r"w.rld", opt, 0, 0), (0, 1, 5))

    def test_invalid_regex_returns_none(self):
        self.assertIsNone(find_in_line("abc", "(", SearchOptions(regex=True)))

    def test_no_wrap_stops_at_eof(self):
        self.assertIsNone(
            find_next(self.buf, "Hello", SearchOptions(), 0, 1, wrap=False))

    def test_zero_length_regex_match(self):
        self.assertEqual(
            find_in_line("abc", "x*", SearchOptions(regex=True), 0), (0, 0))

    def test_flag_label(self):
        self.assertEqual(SearchOptions(True, True).flag_label(), " [ir]")
        self.assertEqual(SearchOptions().flag_label(), "")


class TestMouseMapping(unittest.TestCase):
    def test_col_to_index_ascii(self):
        self.assertEqual(col_to_index("hello", 3), 3)
        self.assertEqual(col_to_index("hello", 99), 5)

    def test_col_to_index_wide(self):
        self.assertEqual(col_to_index("漢字", 0), 0)
        self.assertEqual(col_to_index("漢字", 2), 1)
        self.assertEqual(col_to_index("漢字", 3), 1)

    def test_visual_point_roundtrip(self):
        lines = ["0123456789ABCDE"]
        x, y = get_logical_from_visual_point(1, 2, lines, 10)
        self.assertEqual((x, y), (12, 0))

    def test_visual_point_beyond_eof(self):
        x, y = get_logical_from_visual_point(99, 99, ["ab", "cd"], 80)
        self.assertEqual((x, y), (2, 1))

    def test_visual_point_hard_wrap_identity(self):
        self.assertEqual(
            get_logical_from_visual_point(4, 7, ["ab"], 80, soft_wrap=False),
            (7, 4))


class TestMultiBuffer(unittest.TestCase):
    def test_documents_isolated(self):
        cfg = Config()
        d1 = Document(cfg)
        d2 = Document(cfg)
        d1.buffer.insert_char(0, 0, "x")
        d1.cursor.x = 1
        d1.history.push(["x"], 1, 0)
        self.assertEqual(d2.buffer.lines, [""])
        self.assertEqual(d2.cursor.x, 0)
        self.assertFalse(d2.history.can_undo)

    def test_atomic_save_and_backup(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "out.txt")
            cfg = Config()
            cfg.make_backup = True
            d = Document(cfg, path)
            d.buffer.lines = ["one"]
            self.assertTrue(d.buffer.save())
            d.buffer.lines = ["two"]
            self.assertTrue(d.buffer.save())
            with open(path) as f:
                self.assertEqual(f.read(), "two\n")
            with open(path + "~") as f:
                self.assertEqual(f.read(), "one\n")
            self.assertFalse(os.path.exists(path + ".femto-tmp"))

    def test_revision_bumps_on_edit(self):
        d = Document(Config())
        r0 = d.buffer.revision
        d.buffer.insert_char(0, 0, "a")
        self.assertEqual(d.buffer.revision, r0 + 1)

    def test_highlight_cache_stable(self):
        from femto.highlight import get_spans
        self.assertEqual(get_spans("def f(): pass"),
                         get_spans("def f(): pass"))


class TestNewlineHelpers(unittest.TestCase):
    def test_detect_crlf(self):
        self.assertEqual(detect_newline("hello\r\nworld\r\n"), "\r\n")

    def test_detect_lf(self):
        self.assertEqual(detect_newline("hello\nworld\n"), "\n")

    def test_detect_cr(self):
        self.assertEqual(detect_newline("hello\rworld\r"), "\r")

    def test_detect_mixed_prefers_crlf(self):
        self.assertEqual(detect_newline("a\r\nb\nc\r\n"), "\r\n")

    def test_detect_empty_defaults_lf(self):
        self.assertEqual(detect_newline(""), "\n")

    def test_resolve_override(self):
        cfg = Config()
        cfg.line_ending = "lf"
        self.assertEqual(resolve_newline(cfg, "\r\n"), "\n")
        cfg.line_ending = "crlf"
        self.assertEqual(resolve_newline(cfg, "\n"), "\r\n")
        cfg.line_ending = "cr"
        self.assertEqual(resolve_newline(cfg, "\n"), "\r")
        cfg.line_ending = "auto"
        self.assertEqual(resolve_newline(cfg, "\r\n"), "\r\n")


class TestIOFidelity(unittest.TestCase):
    def test_crlf_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "crlf.txt")
            with open(path, "w", newline="") as f:
                f.write("hello\r\nworld\r\n")
            buf = Buffer(Config())
            buf.load_file(path)
            self.assertEqual(buf.lines, ["hello", "world"])
            self.assertEqual(buf.line_ending, "\r\n")
            buf.insert_char(5, 0, "!")
            buf.save()
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"hello!\r\nworld\r\n")

    def test_final_newline_added(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "nofinal.txt")
            with open(path, "w", newline="") as f:
                f.write("hello")
            cfg = Config()
            cfg.final_newline = True
            buf = Buffer(cfg)
            buf.load_file(path)
            buf.save()
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"hello\n")

    def test_final_newline_disabled(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "nofinal2.txt")
            with open(path, "w", newline="") as f:
                f.write("hello")
            cfg = Config()
            cfg.final_newline = False
            buf = Buffer(cfg)
            buf.load_file(path)
            buf.save()
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"hello")

    def test_line_ending_override(self):
        with tempfile.TemporaryDirectory() as td:
            path = os.path.join(td, "override.txt")
            with open(path, "w", newline="") as f:
                f.write("hello\r\nworld\r\n")
            cfg = Config()
            cfg.line_ending = "lf"
            buf = Buffer(cfg)
            buf.load_file(path)
            buf.save()
            with open(path, "rb") as f:
                self.assertEqual(f.read(), b"hello\nworld\n")


@unittest.skipUnless(HAVE_APP, "curses not importable on this machine")
class TestAutoIndentApp(unittest.TestCase):
    ENTER = 10

    def _app(self):
        return Application(None)

    def _press_enter(self, app):
        app._handle_normal(self.ENTER, 24, 80)

    def test_enter_copies_indent(self):
        app = self._app()
        app.buffer.filename = "notes.txt"
        app.buffer.lines = ["    hello"]
        app.cursor.set_pos(9, 0, app.buffer.get_line_length, app.buffer.max_y)
        self._press_enter(app)
        self.assertEqual(app.buffer.lines, ["    hello", "    "])
        self.assertEqual(app.cursor.x, 4)

    def test_enter_python_colon(self):
        app = self._app()
        app.buffer.filename = "x.py"
        app.buffer.lines = ["def foo():"]
        app.cursor.set_pos(10, 0, app.buffer.get_line_length, app.buffer.max_y)
        self._press_enter(app)
        self.assertEqual(app.buffer.lines, ["def foo():", "    "])
        self.assertEqual(app.cursor.x, 4)

    def test_enter_python_nested_colon(self):
        app = self._app()
        app.buffer.filename = "x.py"
        app.buffer.lines = ["    def foo():"]
        app.cursor.set_pos(14, 0, app.buffer.get_line_length, app.buffer.max_y)
        self._press_enter(app)
        self.assertEqual(app.buffer.lines, ["    def foo():", "        "])
        self.assertEqual(app.cursor.x, 8)

    def test_enter_ignores_inline_comment(self):
        app = self._app()
        app.buffer.filename = "x.py"
        app.buffer.lines = ["def foo():  # hi"]
        app.cursor.set_pos(16, 0, app.buffer.get_line_length, app.buffer.max_y)
        self._press_enter(app)
        self.assertEqual(app.buffer.lines, ["def foo():  # hi", "    "])

    def test_enter_auto_indent_disabled(self):
        app = self._app()
        app.config.auto_indent = False
        app.buffer.lines = ["    hello"]
        app.cursor.set_pos(9, 0, app.buffer.get_line_length, app.buffer.max_y)
        self._press_enter(app)
        self.assertEqual(app.buffer.lines, ["    hello", ""])
        self.assertEqual(app.cursor.x, 0)


class TestLineOperations(unittest.TestCase):
    def setUp(self):
        self.buf = Buffer(Config())

    def test_duplicate_line(self):
        self.buf.lines = ["alpha", "beta"]
        new_y = self.buf.duplicate_line(0)
        self.assertEqual(new_y, 1)
        self.assertEqual(self.buf.lines, ["alpha", "alpha", "beta"])
        self.assertTrue(self.buf.modified)

    def test_duplicate_line_single_line_buffer(self):
        self.buf.lines = ["only"]
        new_y = self.buf.duplicate_line(0)
        self.assertEqual(new_y, 1)
        self.assertEqual(self.buf.lines, ["only", "only"])

    def test_duplicate_line_clamps_y(self):
        self.buf.lines = ["line"]
        new_y = self.buf.duplicate_line(99)
        self.assertEqual(new_y, 1)
        self.assertEqual(self.buf.lines, ["line", "line"])

    def test_transpose_line(self):
        self.buf.lines = ["first", "second", "third"]
        new_y = self.buf.transpose_line(1)
        self.assertEqual(new_y, 0)
        self.assertEqual(self.buf.lines, ["second", "first", "third"])
        self.assertTrue(self.buf.modified)

    def test_transpose_line_at_top_clamps_safely(self):
        self.buf.lines = ["first", "second"]
        new_y = self.buf.transpose_line(0)
        self.assertEqual(new_y, 0)
        self.assertEqual(self.buf.lines, ["first", "second"])

    def test_transpose_line_single_line_clamps_safely(self):
        self.buf.lines = ["only"]
        new_y = self.buf.transpose_line(0)
        self.assertEqual(new_y, 0)
        self.assertEqual(self.buf.lines, ["only"])

    def test_sort_lines_lexicographic(self):
        self.buf.lines = ["gamma", "alpha", "beta"]
        count = self.buf.sort_lines(0, 2, case_sensitive=True)
        self.assertEqual(count, 3)
        self.assertEqual(self.buf.lines, ["alpha", "beta", "gamma"])
        self.assertTrue(self.buf.modified)

    def test_sort_lines_case_insensitive(self):
        self.buf.lines = ["b", "A", "a", "B"]
        count = self.buf.sort_lines(0, 3, case_sensitive=False)
        self.assertEqual(count, 4)
        self.assertEqual(self.buf.lines, ["A", "a", "B", "b"])

    def test_sort_lines_clamps_safely(self):
        self.buf.lines = ["one"]
        count = self.buf.sort_lines(0, 0)
        self.assertEqual(count, 0)
        self.assertEqual(self.buf.lines, ["one"])

    def test_transform_case_single_line(self):
        self.buf.lines = ["hello world"]
        self.buf.transform_case(((0, 0), (5, 0)), upper=True)
        self.assertEqual(self.buf.lines, ["HELLO world"])
        self.buf.transform_case(((0, 0), (5, 0)), upper=False)
        self.assertEqual(self.buf.lines, ["hello world"])

    def test_transform_case_multi_line(self):
        self.buf.lines = ["hello", "brave", "world"]
        self.buf.transform_case(((2, 0), (3, 2)), upper=True)
        self.assertEqual(self.buf.lines, ["heLLO", "BRAVE", "WORld"])

    def test_transform_case_empty_selection_clamps_safely(self):
        self.buf.lines = ["unchanged"]
        self.buf.transform_case(((2, 0), (2, 0)), upper=True)
        self.assertEqual(self.buf.lines, ["unchanged"])

    def test_insert_text_single_and_multi_line(self):
        self.buf.lines = ["ac"]
        pos = self.buf.insert_text(1, 0, "b")
        self.assertEqual(pos, (2, 0))
        self.assertEqual(self.buf.lines, ["abc"])

        pos = self.buf.insert_text(2, 0, "1\n2")
        self.assertEqual(pos, (1, 1))
        self.assertEqual(self.buf.lines, ["ab1", "2c"])


@unittest.skipUnless(HAVE_APP, "Application unavailable")
class TestLineOperationsAppIntegration(unittest.TestCase):
    def _app(self):
        app = Application(None)
        app.config.auto_indent = False
        return app

    def test_app_alt_d_duplicates_current_line_with_undo(self):
        app = self._app()
        app.buffer.lines = ["line1", "line2"]
        app.cursor.set_pos(2, 0, app.buffer.get_line_length, app.buffer.max_y)

        app._handle_normal(Key.ALT_D, 24, 80)
        self.assertEqual(app.buffer.lines, ["line1", "line1", "line2"])
        self.assertEqual((app.cursor.x, app.cursor.y), (2, 1))
        self.assertEqual(app.message, "Duplicated line.")

        # Undo snapshot
        app._handle_normal(Key.CTRL_Z, 24, 80)
        self.assertEqual(app.buffer.lines, ["line1", "line2"])

        # Redo
        app._handle_normal(Key.CTRL_Y, 24, 80)
        self.assertEqual(app.buffer.lines, ["line1", "line1", "line2"])

    def test_app_alt_d_duplicates_selection_with_undo(self):
        app = self._app()
        app.buffer.lines = ["hello world"]
        app.cursor.set_pos(0, 0, app.buffer.get_line_length, app.buffer.max_y)
        app._handle_normal(Key.CTRL_B, 24, 80)  # Mark at (0, 0)
        app.cursor.set_pos(5, 0, app.buffer.get_line_length, app.buffer.max_y)

        app._handle_normal(Key.ALT_D, 24, 80)
        self.assertEqual(app.buffer.lines, ["hellohello world"])
        self.assertEqual(app.message, "Duplicated selection.")

        app._handle_normal(Key.CTRL_Z, 24, 80)
        self.assertEqual(app.buffer.lines, ["hello world"])

    def test_app_alt_t_transposes_line_with_undo(self):
        app = self._app()
        app.buffer.lines = ["first", "second"]
        app.cursor.set_pos(1, 1, app.buffer.get_line_length, app.buffer.max_y)

        app._handle_normal(Key.ALT_T, 24, 80)
        self.assertEqual(app.buffer.lines, ["second", "first"])
        self.assertEqual(app.cursor.y, 0)
        self.assertEqual(app.message, "Transposed line.")

        # At top of file (y=0), transpose is safe no-op
        app._handle_normal(Key.ALT_T, 24, 80)
        self.assertEqual(app.buffer.lines, ["second", "first"])

        # Undo
        app._handle_normal(Key.CTRL_Z, 24, 80)
        self.assertEqual(app.buffer.lines, ["first", "second"])

    def test_app_alt_s_and_alt_shift_s_sorts_selection(self):
        app = self._app()
        app.buffer.lines = ["banana", "Apple", "cherry"]
        app.cursor.set_pos(0, 0, app.buffer.get_line_length, app.buffer.max_y)
        app._handle_normal(Key.CTRL_B, 24, 80)
        app.cursor.set_pos(6, 2, app.buffer.get_line_length, app.buffer.max_y)

        # Alt+S (case-sensitive)
        app._handle_normal(Key.ALT_S, 24, 80)
        self.assertEqual(app.buffer.lines, ["Apple", "banana", "cherry"])
        self.assertEqual(app.message, "Sorted 3 lines.")

        # Undo
        app._handle_normal(Key.CTRL_Z, 24, 80)
        self.assertEqual(app.buffer.lines, ["banana", "Apple", "cherry"])

        # Alt+Shift+S (case-insensitive)
        app.buffer.lines = ["b", "A", "c"]
        app.cursor.set_pos(0, 0, app.buffer.get_line_length, app.buffer.max_y)
        app._handle_normal(Key.CTRL_B, 24, 80)
        app.cursor.set_pos(1, 2, app.buffer.get_line_length, app.buffer.max_y)

        app._handle_normal(Key.ALT_SHIFT_S, 24, 80)
        self.assertEqual(app.buffer.lines, ["A", "b", "c"])
        self.assertEqual(app.message, "Sorted 3 lines.")

    def test_app_alt_u_and_alt_l_transform_case_with_undo(self):
        app = self._app()
        app.buffer.lines = ["quick brown fox"]
        app.cursor.set_pos(6, 0, app.buffer.get_line_length, app.buffer.max_y)
        app._handle_normal(Key.CTRL_B, 24, 80)
        app.cursor.set_pos(11, 0, app.buffer.get_line_length, app.buffer.max_y)

        # Alt+U -> uppercase
        app._handle_normal(Key.ALT_U, 24, 80)
        self.assertEqual(app.buffer.lines, ["quick BROWN fox"])
        self.assertEqual(app.message, "Uppercase.")

        # Alt+L -> lowercase
        app._handle_normal(Key.ALT_L, 24, 80)
        self.assertEqual(app.buffer.lines, ["quick brown fox"])
        self.assertEqual(app.message, "Lowercase.")

        # Undo
        app._handle_normal(Key.CTRL_Z, 24, 80)
        self.assertEqual(app.buffer.lines, ["quick BROWN fox"])
        app._handle_normal(Key.CTRL_Z, 24, 80)
        self.assertEqual(app.buffer.lines, ["quick brown fox"])

    def test_app_clamps_safely_without_selection(self):
        app = self._app()
        app.buffer.lines = ["hello"]
        app.cursor.set_pos(0, 0, app.buffer.get_line_length, app.buffer.max_y)

        app._handle_normal(Key.ALT_S, 24, 80)
        self.assertEqual(app.message, "No selection to sort.")
        self.assertEqual(app.buffer.lines, ["hello"])

        app._handle_normal(Key.ALT_U, 24, 80)
        self.assertEqual(app.message, "No selection.")
        self.assertEqual(app.buffer.lines, ["hello"])

        app._handle_normal(Key.ALT_L, 24, 80)
        self.assertEqual(app.message, "No selection.")
        self.assertEqual(app.buffer.lines, ["hello"])


if __name__ == "__main__":
    unittest.main()

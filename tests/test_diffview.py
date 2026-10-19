"""
Unit tests for the side-by-side diff viewer.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from femto.diffview import compute_diff, count_diffs, next_diff, prev_diff

try:
    from femto.app import Application, Mode
    HAVE_APP = True
except Exception:
    HAVE_APP = False


class TestComputeDiff(unittest.TestCase):
    def test_equal_files(self):
        rows = compute_diff(["a", "b"], ["a", "b"])
        self.assertEqual([r[2] for r in rows], ["same", "same"])

    def test_added_line(self):
        rows = compute_diff(["a"], ["a", "b"])
        kinds = [r[2] for r in rows]
        self.assertIn("added", kinds)
        added = [r for r in rows if r[2] == "added"][0]
        self.assertIsNone(added[0])
        self.assertEqual(added[1], 1)

    def test_removed_line(self):
        rows = compute_diff(["a", "b"], ["a"])
        removed = [r for r in rows if r[2] == "removed"]
        self.assertEqual(len(removed), 1)
        self.assertIsNone(removed[0][1])

    def test_changed_line(self):
        rows = compute_diff(["a", "b"], ["a", "B"])
        self.assertIn("changed", [r[2] for r in rows])

    def test_count_diffs(self):
        rows = compute_diff(["a", "b"], ["a", "B"])
        self.assertEqual(count_diffs(rows), 1)

    def test_next_prev_diff(self):
        rows = compute_diff(["a", "b", "c"], ["a", "B", "c"])
        self.assertEqual(next_diff(rows, 0), 1)
        self.assertEqual(next_diff(rows, 1), 1)   # clamped at last diff
        self.assertEqual(prev_diff(rows, 2), 1)
        self.assertEqual(prev_diff(rows, 1), 1)   # clamped


@unittest.skipUnless(HAVE_APP, "curses not importable on this machine")
class TestDiffMode(unittest.TestCase):
    def test_diff_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            right = os.path.join(td, "b.txt")
            with open(right, "w") as f:
                f.write("one\ntwo\nthree\n")

            app = Application(None)
            app.buffer.filename = os.path.join(td, "a.txt")
            app.buffer.lines = ["one", "TWO", "three"]

            app._start_diff()
            self.assertEqual(app.mode, Mode.DIFF_PICK)

            app.prompt.text = right
            app._commit_prompt()
            self.assertEqual(app.mode, Mode.DIFF)
            self.assertIn("changed", [r[2] for r in app.diff_state['rows']])

            # n jumps to the difference
            app._handle_diff(ord('n'), 24, 80)
            self.assertEqual(app.diff_state['rows'][app.diff_state['current']][2],
                             "changed")

            # q closes
            app._handle_diff(ord('q'), 24, 80)
            self.assertEqual(app.mode, Mode.NORMAL)
            self.assertIsNone(app.diff_state)

    def test_diff_missing_file(self):
        app = Application(None)
        app._start_diff()
        app.prompt.text = "/nonexistent/file.txt"
        app._commit_prompt()
        self.assertEqual(app.mode, Mode.NORMAL)
        self.assertIn("No such file", app.message)


if __name__ == "__main__":
    unittest.main()

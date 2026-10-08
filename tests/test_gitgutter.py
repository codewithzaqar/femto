"""
Unit tests for git gutter markers.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from femto.gitgutter import get_git_diff_markers


class TestGitGutter(unittest.TestCase):
    def test_non_git_directory_returns_empty(self):
        with tempfile.TemporaryDirectory() as td:
            filepath = os.path.join(td, "test.txt")
            with open(filepath, 'w') as f:
                f.write("hello\n")
            
            markers = get_git_diff_markers(filepath)
            self.assertEqual(markers, {})

    def test_nonexistent_file_returns_empty(self):
        markers = get_git_diff_markers("/nonexistent/file.txt")
        self.assertEqual(markers, {})

    def test_none_filepath_returns_empty(self):
        markers = get_git_diff_markers(None)
        self.assertEqual(markers, {})


if __name__ == "__main__":
    unittest.main()

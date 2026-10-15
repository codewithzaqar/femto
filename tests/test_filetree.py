"""
Unit tests for file tree browser.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from femto.filetree import FileTree, should_ignore, load_gitignore


class TestFileTree(unittest.TestCase):
    def test_build_tree_basic(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "subdir"))
            with open(os.path.join(td, "file1.txt"), 'w') as f:
                f.write("test")
            with open(os.path.join(td, "subdir", "file2.py"), 'w') as f:
                f.write("test")

            tree = FileTree(td)

            # Root level: subdir + file1.txt (subdir collapsed by default)
            self.assertEqual(len(tree.entries), 2)
            names = [entry[0] for entry in tree.entries]
            self.assertIn("subdir", names)
            self.assertIn("file1.txt", names)

    def test_expansion_shows_children(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "subdir"))
            with open(os.path.join(td, "subdir", "file2.py"), 'w') as f:
                f.write("test")

            tree = FileTree(td)
            tree.expanded.add(os.path.join(td, "subdir"))
            tree.refresh()

            names = [entry[0] for entry in tree.entries]
            self.assertIn("subdir", names)
            self.assertIn("file2.py", names)

    def test_toggle_expand_via_method(self):
        with tempfile.TemporaryDirectory() as td:
            os.makedirs(os.path.join(td, "subdir"))
            with open(os.path.join(td, "subdir", "inner.txt"), 'w') as f:
                f.write("x")

            tree = FileTree(td)
            tree.current = 0
            self.assertTrue(tree.get_current_is_dir())

            tree.toggle_expand()
            names = [e[0] for e in tree.entries]
            self.assertIn("inner.txt", names)

            tree.toggle_expand()
            names = [e[0] for e in tree.entries]
            self.assertNotIn("inner.txt", names)

    def test_should_ignore_git_directory(self):
        self.assertTrue(should_ignore(".git", True, set()))

    def test_should_ignore_pycache(self):
        self.assertTrue(should_ignore("__pycache__", True, set()))

    def test_should_not_ignore_normal_file(self):
        self.assertFalse(should_ignore("test.py", False, set()))

    def test_load_gitignore(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, ".gitignore"), 'w') as f:
                f.write("*.log\nbuild/\n# comment\n")

            patterns = load_gitignore(td)

            self.assertIn("*.log", patterns)
            self.assertIn("build/", patterns)
            self.assertNotIn("# comment", patterns)

    def test_filetree_navigation(self):
        with tempfile.TemporaryDirectory() as td:
            for i in range(10):
                with open(os.path.join(td, f"file{i}.txt"), 'w') as f:
                    f.write("test")

            tree = FileTree(td)

            self.assertEqual(tree.current, 0)
            tree.move_down()
            self.assertEqual(tree.current, 1)
            tree.move_up()
            self.assertEqual(tree.current, 0)

    def test_get_current_path(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "a.txt"), 'w') as f:
                f.write("x")

            tree = FileTree(td)
            self.assertEqual(tree.get_current_path(), os.path.join(td, "a.txt"))
            self.assertFalse(tree.get_current_is_dir())


if __name__ == "__main__":
    unittest.main()

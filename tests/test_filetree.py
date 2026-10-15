"""
Unit tests for file tree browser.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from femto.filetree import FileTree, build_tree, should_ignore, load_gitignore


class TestFileTree(unittest.TestCase):
    def test_build_tree_basic(self):
        with tempfile.TemporaryDirectory() as td:
            # Create test structure
            os.makedirs(os.path.join(td, "subdir"))
            with open(os.path.join(td, "file1.txt"), 'w') as f:
                f.write("test")
            with open(os.path.join(td, "subdir", "file2.py"), 'w') as f:
                f.write("test")
            
            tree = build_tree(td)
            
            # Should have subdir and file1.txt at root level
            self.assertEqual(len(tree), 2)
            names = [entry[0] for entry in tree]
            self.assertIn("subdir", names)
            self.assertIn("file1.txt", names)
    
    def test_should_ignore_git_directory(self):
        self.assertTrue(should_ignore(".git", True, set()))
    
    def test_should_ignore_pycache(self):
        self.assertTrue(should_ignore("__pycache__", True, set()))
    
    def test_should_not_ignore_normal_file(self):
        self.assertFalse(should_ignore("test.py", False, set()))
    
    def test_load_gitignore(self):
        with tempfile.TemporaryDirectory() as td:
            gitignore_path = os.path.join(td, ".gitignore")
            with open(gitignore_path, 'w') as f:
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


if __name__ == "__main__":
    unittest.main()

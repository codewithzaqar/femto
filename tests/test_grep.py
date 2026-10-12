"""
Unit tests for project-wide grep.
"""

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from femto.grep import grep_directory


class TestGrep(unittest.TestCase):
    def test_grep_finds_matches(self):
        with tempfile.TemporaryDirectory() as td:
            # Create test files
            with open(os.path.join(td, "test1.py"), 'w') as f:
                f.write("hello world\nfoo bar\nhello again\n")
            with open(os.path.join(td, "test2.py"), 'w') as f:
                f.write("no matches here\n")
            
            results = grep_directory(td, "hello")
            self.assertEqual(len(results), 2)
            self.assertEqual(results[0][1], 1)  # line 1
            self.assertEqual(results[1][1], 3)  # line 3
    
    def test_grep_case_insensitive(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "test.py"), 'w') as f:
                f.write("Hello World\nhello world\nHELLO WORLD\n")
            
            results = grep_directory(td, "hello", ignore_case=True)
            self.assertEqual(len(results), 3)
    
    def test_grep_skips_git_directory(self):
        with tempfile.TemporaryDirectory() as td:
            # Create .git directory
            git_dir = os.path.join(td, ".git")
            os.makedirs(git_dir)
            with open(os.path.join(git_dir, "config"), 'w') as f:
                f.write("hello world\n")
            
            # Create normal file
            with open(os.path.join(td, "test.py"), 'w') as f:
                f.write("hello world\n")
            
            results = grep_directory(td, "hello")
            self.assertEqual(len(results), 1)
            self.assertNotIn(".git", results[0][0])
    
    def test_grep_max_results(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "test.py"), 'w') as f:
                for i in range(100):
                    f.write(f"hello line {i}\n")
            
            results = grep_directory(td, "hello", max_results=10)
            self.assertEqual(len(results), 10)
    
    def test_grep_invalid_regex(self):
        with tempfile.TemporaryDirectory() as td:
            with open(os.path.join(td, "test.py"), 'w') as f:
                f.write("test\n")
            
            results = grep_directory(td, "[invalid")
            self.assertEqual(results, [])


if __name__ == "__main__":
    unittest.main()

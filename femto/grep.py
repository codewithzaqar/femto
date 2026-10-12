"""
Project-wide grep for Femto (stdlib only)

Walks a dirctory tree, searches files for a pattern, and returns
structed results. Respects common ignore patterns (.git, __pycache__).
"""

import os
import re


# Directories to skip during grep
IGNORE_DIRS = {'.git', '__pycache__', '.pytest_cache', 'node_modules',
        '.venv', 'venv', 'env', '.tox', '.mypy_cache'}

# File extensions to search (None = all text files)
DEFAULT_EXTENSIONS = {'.py', '.txt', '.md', '.rst', '.json', '.yaml', '.yml',
            '.toml', '.ini', '.cfg', '.conf', '.sh', '.bash',
            '.js', '.ts', '.jsx', '.tsx', '.html', '.css', '.scss',
            '.c', '.cpp', '.h', '.hpp', '.java', '.go', '.rs'}


def grep_directory(root_dir, pattern, ignore_case=False, max_results=500):
    """Search for pattern in all text files under root_dir.

    Args:
        root_dir: Directory to search
        pattern: Regex pattern to search for
        ignore_case: Case-insensitive search
        max_results: Stop after this many matches

    Returns:
        List of (filepath, line_numbers, line_text) tuples
    """
    if not os.path.isdir(root_dir):
        return []

    flags = re.IGNORECASE if ignore_case else 0
    try:
        regex = re.compile(pattern, flags)
    except re.error:
        return []

    results = []

    for dirpath, dirnames, filenames in os.walk(root_dir):
        # Filter out ignored dirctories
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]

        for filename in filenames:
            filepath = os.path.join(dirpath, filename)
            rel_path = os.path.relpath(filepath, root_dir)

            # Skip binary files and non-default extensions
            ext = os.path.splitext(filename)[1].lower()
            if ext not in DEFAULT_EXTENSIONS and ext != '':
                continue

            try:
                with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                    for line_num, line in enumerate(f, 1):
                        if regex.search(line):
                            results.append((rel_path, line_num, line.rstrip()))
                            if len(results) >= max_results:
                                return results
            except (OSError, UnicodeDecodeError):
                continue

    return results

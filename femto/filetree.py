"""
File tree browser for Femto (stdlib only).

Builds a navigable tree from the current directory, respecting .gitignore
patterns and common ignore directories.
"""

import os


# Directories to always skip
DEFAULT_IGNORE = {'.git', '__pycache__', '.pytest_cache', 'node_modules',
                  '.venv', 'venv', 'env', '.tox', '.mypy_cache', '.idea',
                  '.vscode', '__pypackages__', '.DS_Store'}


def load_gitignore(root_dir):
    """Load patterns from .gitignore file."""
    gitignore_path = os.path.join(root_dir, '.gitignore')
    patterns = set()
    if os.path.exists(gitignore_path):
        try:
            with open(gitignore_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        patterns.add(line)
        except OSError:
            pass
    return patterns


def should_ignore(name, is_dir, gitignore_patterns):
    """Check if a file/directory should be ignored."""
    if name in DEFAULT_IGNORE:
        return True
    if name.startswith('.') and is_dir:
        return True
    # Simple pattern matching (not full gitignore spec)
    for pattern in gitignore_patterns:
        if pattern.startswith('!'):
            continue  # Skip negation patterns for simplicity
        if pattern.endswith('/'):
            if is_dir and name == pattern.rstrip('/'):
                return True
        else:
            if name == pattern or (pattern.startswith('*.') and name.endswith(pattern[1:])):
                return True
    return False


class FileTree:
    """Navigable file tree state."""
    
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.gitignore_patterns = load_gitignore(root_dir)
        self.expanded = set()  # Set of paths that are expanded
        self.entries = []
        self.current = -1
        self.scroll_y = 0
        self.refresh()
    
    def refresh(self):
        """Rebuild the tree based on expansion state."""
        self.entries = []
        self._walk(self.root_dir, 0)
        
        # Ensure current is valid
        if not self.entries:
            self.current = -1
        else:
            if self.current < 0:
                self.current = 0
            elif self.current >= len(self.entries):
                self.current = len(self.entries) - 1
    
    def _walk(self, current_dir, depth):
        """Recursively walk directory, respecting expanded state."""
        try:
            entries = sorted(os.listdir(current_dir))
        except OSError:
            return
        
        # Separate dirs and files, dirs first
        dirs = []
        files = []
        for entry in entries:
            full_path = os.path.join(current_dir, entry)
            is_dir = os.path.isdir(full_path)
            
            if should_ignore(entry, is_dir, self.gitignore_patterns):
                continue
            
            if is_dir:
                dirs.append((entry, full_path))
            else:
                files.append((entry, full_path))
        
        # Add directories
        for name, path in dirs:
            self.entries.append((name, path, True, depth))
            
            # Only recurse into expanded directories
            if path in self.expanded:
                self._walk(path, depth + 1)
        
        # Add files
        for name, path in files:
            self.entries.append((name, path, False, depth))
    
    def move_up(self):
        if self.current > 0:
            self.current -= 1
    
    def move_down(self):
        if self.current < len(self.entries) - 1:
            self.current += 1
    
    def toggle_expand(self):
        """Toggle expansion of current directory."""
        if not self.entries or self.current < 0:
            return
        
        name, path, is_dir, depth = self.entries[self.current]
        if is_dir:
            if path in self.expanded:
                self.expanded.remove(path)
            else:
                self.expanded.add(path)
            self.refresh()
    
    def get_current_path(self):
        """Get the path of the current entry."""
        if self.entries and 0 <= self.current < len(self.entries):
            return self.entries[self.current][1]
        return None
    
    def get_current_is_dir(self):
        """Check if current entry is a directory."""
        if self.entries and 0 <= self.current < len(self.entries):
            return self.entries[self.current][2]
        return False
    
    def get_visible_entries(self, height):
        """Get entries visible in the viewport."""
        if not self.entries:
            return []
        
        # Adjust scroll
        if self.current < self.scroll_y:
            self.scroll_y = self.current
        elif self.current >= self.scroll_y + height:
            self.scroll_y = self.current - height + 1
        
        return self.entries[self.scroll_y:self.scroll_y + height]

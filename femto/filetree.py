"""
File tree browser for Femto (stdlib only).

Builds a navigable tree from the current directory, respecting .gitignore
patterns and common ignore directories.
"""

import os


# Directories to always skip
DEFAULT_IGNORE = {'.git','__pycache__','.pytest_cache','node_modules',
        '.venv','venv','env','.tox','.mypy_cache','.idea',
        '.vscode','__pypackages__','.DS_Store'}


def load_gitignore(root_dir):
    """Load patterns from .gitgnore file."""
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
            continue # Skip negation patterns for simplicity
        if pattern.endswith('/'):
            if is_dir and name == pattern.rstrip('/'):
                return True
        else:
            if name == pattern or (pattern.startswith('*.') and name.endswith(pattern[1:])):
                return True
    return False


def build_tree(root_dir, gitignore_patterns=None):
    """Build a tree structure from root_dir.
    
    Returns:
        List of (name, path, is_dir, depth, children) tuples
    """
    if gitignore_patterns is None:
        gitignore_patterns = load_gitignore(root_dir)
    
    tree = []
    
    def walk(current_dir, depth=0):
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
            
            if should_ignore(entry, is_dir, gitignore_patterns):
                continue
                
            if is_dir:
                dirs.append((entry, full_path))
            else:
                files.append((entry, full_path))
                
        # Add directories
        for name, path in dirs:
            tree.append((name, path, True, depth, []))
            # Recursively add children (but don't expand by default)
            # In a real implementation, we'd track expanded state
            
        # Add files
        for name, path in files:
            tree.append((name, path, False, depth, []))
    
    walk(root_dir)
    return tree


class FileTree:
    """Navigable file tree state."""
    
    def __init__(self, root_dir):
        self.root_dir = root_dir
        self.gitignore_patterns = load_gitignore(root_dir)
        self.entries = build_tree(root_dir, self.gitignore_patterns)
        self.current = 0 if self.entries else -1
        self.expanded = set() # Set of paths that are expanded
        self.scroll_y = 0
        
    def refresh(self):
        """Rebuild the tree."""
        self.entries = build_tree(self.root_dir, self.gitignore_patterns)
        if self.current >= len(self.entries):
            self.current = max(0, len(self.entries) - 1)
            
    def move_up(self):
        if self.current > 0:
            self.current -= 1
            
    def move_down(self):
        if self.current < len(self.entries) - 1:
            self.current += 1
            
    def toggle_expand(self):
        """Toggle expansion of current directory."""
        if not self.entries:
            return
            
        name, path, is_dir, depth, _ = self.entries[self.current]
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

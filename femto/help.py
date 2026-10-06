"""
Help screen state and keybindings catalog for Femto.

HelpView owns the help-screen scroll offset and the catalog.
KEYBINDINGS is exposed at module level so the renderer can fall back
to it when app.py passes None (defensive rendering).
"""

KEYBINDINGS = {
    "File": [
        ("^X", "Exit (prompt to save modified buffers)"),
        ("^S", "Save (Save-As when unnamed)"),
        ("F1", "This help screen"),
    ],
    "Editing": [
        ("Enter", "New line (auto-indent on)"),
        ("Backspace", "Delete char before cursor"),
        ("Del", "Delete char at cursor"),
        ("Tab", "Indent / complete path in Save-As"),
        ("Shift+Tab", "Unindent"),
        ("^Z / ^Y", "Undo / Redo"),
        ("Alt+D", "Duplicate line or selection below"),
        ("Alt+T", "Transpose line with line above"),
        ("Alt+S", "Sort selected lines (Alt+Shift+S case-insensitive)"),
        ("Alt+U / Alt+L", "Uppercase / lowercase selection"),
    ],
    "Navigation": [
        ("Arrows", "Move cursor"),
        ("^Left / ^Right", "Previous / next word"),
        ("Home / End", "Start / end of line"),
        ("PgUp / PgDn", "Page up / down"),
        ("^T", "Go to line"),
    ],
    "Clipboard & Selection": [
        ("^B", "Set / clear mark"),
        ("^K", "Cut line or selection"),
        ("^P", "Copy line or selection"),
        ("^U", "Paste clipboard"),
    ],
    "Search & Replace": [
        ("^W", "Search / find next"),
        ("^\\", "Replace flow"),
        ("^O", "Toggle case-insensitive (in prompt)"),
        ("^R", "Toggle regex (in prompt)"),
    ],
    "Buffers & View": [
        ("^F / ^L", "Next / previous buffer"),
        ("^N", "Toggle line numbers"),
        ("^D", "Toggle mouse support"),
    ],
    "Mouse": [
        ("Wheel", "Scroll viewport"),
        ("Click", "Move cursor to point"),
    ],
}


class HelpView:
    """Owns help-screen scroll state and the keybindings catalog."""
    
    def __init__(self, offset=0):
        self.offset = offset
        self.keybindings = KEYBINDINGS
    
    def move(self, action, screen_rows, screen_cols):
        """Scroll based on action string, clamping to content bounds.
        
        Args:
            action: "up", "down", "page_up", or "page_down"
            screen_rows: visible rows in the viewport
            screen_cols: visible columns (unused, but part of the API)
        
        Returns:
            The new clamped offset value.
        """
        # Estimate total content lines: categories + bindings + spacing
        total_lines = 0
        for category, bindings in self.keybindings.items():
            total_lines += 1  # category header
            total_lines += len(bindings)
            total_lines += 1  # blank line after category
        
        visible_lines = max(1, screen_rows - 2)  # header + footer
        max_scroll = max(0, total_lines - visible_lines)
        
        # Map action strings to scroll deltas
        if action == "up":
            dy = -1
        elif action == "down":
            dy = 1
        elif action == "page_up":
            dy = -(screen_rows - 2)
        elif action == "page_down":
            dy = screen_rows - 2
        else:
            dy = 0
        
        self.offset = max(0, min(self.offset + dy, max_scroll))
        return self.offset
    
    def reset(self):
        """Reset offset to top when entering help mode."""
        return 0

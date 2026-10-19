"""
Side-by-side diff engine for Femto (stdlib only).

Uses difflib.SequenceMatcher to align two line lists into display rows
(left_index | None, right_index | None, kind) where kind is one of
'same', 'changed', 'added', 'removed'.
"""

import difflib


def compute_diff(left, right):
    """Align two line lists into side-by-side rows."""
    sm = difflib.SequenceMatcher(None, left, right)
    rows = []
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == 'equal':
            for k in range(i2 - i1):
                rows.append((i1 + k, j1 + 1, 'same'))
        elif tag == 'replace':
            n = min(i2 - i1, j2 - j1)
            for k in range(n):
                rows.append((i1 + k, j1 + k, 'changed'))
            for k in range(n, i2 - i1):
                rows.append((i1 + k, None, 'removed'))
            for k in range(n, j2 - j1):
                rows.append((None, j1 + k, 'added'))
        elif tag == 'delete':
            for k in range(i1, i2):
                rows.append((k, None, 'removed'))
        elif tag == 'insert':
            for k in range(j1, j2):
                rows.append((None, k, 'added'))
    return rows


def count_diffs(rows):
    return sum(1 for r in rows if r[2] != 'same')


def next_diff(rows, current):
    """Index of next differing now after current (clamped)."""
    for i in range(current + 1, len(rows)):
        if rows[i][2] != 'same':
            return i
    return current


def prev_diff(rows, current):
    """Index of previous differing row before current (clamped)."""
    for i in range(current - 1, -1, -1):
        if rows[i][2] != 'same':
            return i
    return current

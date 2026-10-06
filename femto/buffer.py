"""
Text buffer management for Femto.

I/O Fidelity (v0.0.3a01):
  * Detects dominant line ending (CRLF/CR/LF) on load.
  * Normalizes to \n internally so cursor math and wrapping stay clean.
  * Re-applies the correct ending on save (.femtorc can override).
  * Ensures POSIX-compliant trailing newlines.
"""

import os

from femto.search import SearchOptions, find_next


# ── module-level I/O helpers (imported by the test-suite) ──────

def detect_newline(content):
    """Return the dominant line ending of raw file content.

    CRLF is counted before lone CR/LF so mixed files prefer CRLF.
    """
    crlf = content.count('\r\n')
    rest = content.replace('\r\n', '')
    cr = rest.count('\r')
    lf = rest.count('\n')
    if crlf and crlf >= lf and crlf >= cr:
        return '\r\n'
    if cr > lf:
        return '\r'
    return '\n'


def resolve_newline(config, detected):
    """Apply the .femtorc `line_ending` override to a detected ending."""
    override = getattr(config, 'line_ending', 'auto')
    if override == 'crlf':
        return '\r\n'
    if override == 'cr':
        return '\r'
    if override == 'lf':
        return '\n'
    return detected


class Buffer:
    """Handles the text content as a list of lines."""

    def __init__(self, config):
        self.lines = [""]
        self.filename = None
        self.modified = False
        self.revision = 0
        self.config = config

        # I/O state
        self.line_ending = '\n'
        self.had_final_newline = False

    # ── File I/O ──────────────────────────────────────────────

    def load_file(self, filepath):
        """Load a file, detecting line endings and normalizing internally."""
        self.filename = filepath
        self.line_ending = '\n'
        self.had_final_newline = False

        if filepath and os.path.exists(filepath):
            try:
                with open(filepath, 'r', encoding='utf-8', newline='') as f:
                    content = f.read()

                self.line_ending = detect_newline(content)
                self.had_final_newline = content.endswith(('\n', '\r'))

                # Normalize to \n internally (keeps cursor math clean)
                content = content.replace('\r\n', '\n').replace('\r', '\n')

                spaces = " " * self.config.tab_size
                self.lines = content.replace('\t', spaces).split('\n')

                # A trailing newline leaves an extra empty string; drop it
                if self.had_final_newline and self.lines and self.lines[-1] == '':
                    self.lines.pop()
                if not self.lines:
                    self.lines = [""]
            except Exception as e:
                self.lines = [f"Error reading file: {e}"]
        else:
            self.lines = [""]

        self.modified = False
        self.revision = 0

    def save(self):
        """Atomic save with correct line endings and trailing newline."""
        if not self.filename:
            return False

        ending = resolve_newline(self.config, self.line_ending)
        final_nl = getattr(self.config, 'final_newline', True)

        tmp = self.filename + ".femto-tmp"
        try:
            with open(tmp, 'w', encoding='utf-8', newline='') as f:
                text = ending.join(self.lines)
                if final_nl or self.had_final_newline:
                    text += ending
                f.write(text)
                f.flush()
                os.fsync(f.fileno())

            if getattr(self.config, 'make_backup', False) \
                    and os.path.exists(self.filename):
                os.replace(self.filename, self.filename + "~")
            os.replace(tmp, self.filename)
            self.modified = False
            return True
        except Exception:
            try:
                os.remove(tmp)
            except OSError:
                pass
            return False

    def touch(self):
        """Mark modified and bump the revision counter."""
        self.modified = True
        self.revision += 1

    # ── Editing ───────────────────────────────────────────────

    def insert_char(self, x, y, char):
        line = self.lines[y]
        self.lines[y] = line[:x] + char + line[x:]
        self.touch()

    def insert_newline(self, x, y):
        line = self.lines[y]
        self.lines[y] = line[:x]
        self.lines.insert(y + 1, line[x:])
        self.touch()

    def delete_char(self, x, y):
        if x < len(self.lines[y]):
            line = self.lines[y]
            self.lines[y] = line[:x] + line[x + 1:]
            self.touch()
        elif x == len(self.lines[y]) and y < len(self.lines) - 1:
            self.lines[y] += self.lines[y + 1]
            del self.lines[y + 1]
            self.touch()

    def backspace(self, x, y):
        if x > 0:
            self.delete_char(x - 1, y)
            return x - 1, y
        elif y > 0:
            prev_len = len(self.lines[y - 1])
            self.lines[y - 1] += self.lines[y]
            del self.lines[y]
            self.touch()
            return prev_len, y - 1
        return x, y

    # ── Tab / Indentation ─────────────────────────────────────

    def insert_tab(self, y, x):
        spaces = " " * self.config.tab_size
        line = self.lines[y]
        self.lines[y] = line[:x] + spaces + line[x:]
        self.touch()
        return x + len(spaces)

    def remove_tab(self, y, x):
        line = self.lines[y]
        spaces_to_remove = 0
        for i in range(min(self.config.tab_size, len(line))):
            if line[i] == ' ':
                spaces_to_remove += 1
            else:
                break
        if spaces_to_remove > 0:
            self.lines[y] = line[spaces_to_remove:]
            self.touch()
            return max(0, x - spaces_to_remove)
        return x

    # ── Auto-indent helper (v0.0.3a02) ────────────────────────

    def get_leading_whitespace(self, y):
        """Returns the leading whitespace string of line y."""
        if 0 <= y < len(self.lines):
            line = self.lines[y]
            return line[:len(line) - len(line.lstrip())]
        return ""

    # ── Word Navigation ───────────────────────────────────────

    def get_next_word_pos(self, y, x):
        line = self.lines[y]
        while x < len(line) and line[x].isalnum():
            x += 1
        while x < len(line) and not line[x].isalnum():
            x += 1
        return x

    def get_prev_word_pos(self, y, x):
        line = self.lines[y]
        if x == 0:
            return 0
        x -= 1
        while x >= 0 and not line[x].isalnum():
            x -= 1
        while x >= 0 and line[x].isalnum():
            x -= 1
        return x + 1

    # ── Search ───────────────────────────────────────────────

    def find_text(self, term, start_x, start_y):
        hit = find_next(self, term, SearchOptions(), start_x, start_y)
        return (hit[0], hit[1]) if hit else None

    # ── Line Operations (v0.0.4) ──────────────────────────────

    def insert_text(self, x, y, text):
        """Insert multi-line or single-line text at (x, y); returns new (x, y)."""
        if not text:
            return x, y
        chunks = text.split("\n")
        y = max(0, min(y, len(self.lines) - 1))
        line = self.lines[y]
        x = max(0, min(x, len(line)))
        head, tail = line[:x], line[x:]
        if len(chunks) == 1:
            self.lines[y] = head + chunks[0] + tail
            new_pos = (x + len(chunks[0]), y)
        else:
            first = head + chunks[0]
            last = chunks[-1] + tail
            self.lines[y:y + 1] = [first] + chunks[1:-1] + [last]
            new_pos = (len(chunks[-1]), y + len(chunks) - 1)
        self.touch()
        return new_pos

    def duplicate_line(self, y):
        """Duplicate line y below itself; returns new line index."""
        if not self.lines:
            self.lines = [""]
            self.touch()
            return 0
        y = max(0, min(y, len(self.lines) - 1))
        self.lines.insert(y + 1, self.lines[y])
        self.touch()
        return y + 1

    def transpose_line(self, y):
        """Transpose line y with line y - 1; returns new line index."""
        if len(self.lines) <= 1 or y <= 0 or y >= len(self.lines):
            return y
        self.lines[y - 1], self.lines[y] = self.lines[y], self.lines[y - 1]
        self.touch()
        return y - 1

    def sort_lines(self, start_y, end_y, case_sensitive=True):
        """Sort lines from start_y to end_y inclusive; returns count sorted."""
        if len(self.lines) <= 1:
            return 0
        start_y = max(0, min(start_y, len(self.lines) - 1))
        end_y = max(0, min(end_y, len(self.lines) - 1))
        if start_y > end_y:
            start_y, end_y = end_y, start_y
        if start_y == end_y:
            return 0
        target = self.lines[start_y:end_y + 1]
        if case_sensitive:
            sorted_lines = sorted(target)
        else:
            sorted_lines = sorted(target, key=lambda s: (s.casefold(), s))
        self.lines[start_y:end_y + 1] = sorted_lines
        self.touch()
        return end_y - start_y + 1

    def transform_case(self, bounds, upper=True):
        """Transform text in bounds [start, end) to upper or lower case."""
        (sx, sy), (ex, ey) = bounds
        if (sx, sy) == (ex, ey) or not self.lines:
            return
        if (sy, sx) > (ey, ex):
            (sx, sy), (ex, ey) = (ex, ey), (sx, sy)

        sy = max(0, min(sy, len(self.lines) - 1))
        ey = max(0, min(ey, len(self.lines) - 1))
        transform = str.upper if upper else str.lower

        if sy == ey:
            line = self.lines[sy]
            sx = max(0, min(sx, len(line)))
            ex = max(0, min(ex, len(line)))
            if sx >= ex:
                return
            self.lines[sy] = line[:sx] + transform(line[sx:ex]) + line[ex:]
        else:
            first_line = self.lines[sy]
            sx = max(0, min(sx, len(first_line)))
            self.lines[sy] = first_line[:sx] + transform(first_line[sx:])

            for y in range(sy + 1, ey):
                self.lines[y] = transform(self.lines[y])

            last_line = self.lines[ey]
            ex = max(0, min(ex, len(last_line)))
            self.lines[ey] = transform(last_line[:ex]) + last_line[ex:]

        self.touch()

    # ── Helpers ──────────────────────────────────────────────

    def get_line_length(self, y):
        if 0 <= y < len(self.lines):
            return len(self.lines[y])
        return 0

    @property
    def max_y(self):
        return max(0, len(self.lines) - 1)

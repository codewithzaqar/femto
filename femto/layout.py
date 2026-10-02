"""
Pure visual-layout mathematics for Femto.

Contains NO curses import so it can be unit-tested on any platform,
including CI runners without a terminal.
"""

import unicodedata


def char_width(char):
    """Return the terminal column width of a character."""
    if unicodedata.combining(char):
        return 0

    if unicodedata.category(char) == "Cf":
        return 0

    if unicodedata.east_asian_width(char) in ("W", "F"):
        return 2

    return 1


def visual_width(text):
    """Return the total terminal column width of a string."""
    return sum(char_width(char) for char in text)


def line_row_count(line_len, width):
    """Number of visual rows occupied by a line of `line_len` columns."""
    if width < 1:
        width = 1
    return max(1, (line_len + width - 1) // width)


def chunk_line(line, width):
    """Split a line into visual chunks of at most `width` columns."""
    if not line:
        return [""]
    if width < 1:
        width = 1

    chunks = []
    current = ""
    current_width = 0

    for char in line:
        char_w = char_width(char)

        if current and current_width + char_w > width:
            chunks.append(current)
            current = ""
            current_width = 0

        current += char
        current_width += char_w

    if current:
        chunks.append(current)

    return chunks


def get_visual_position(x, y, lines, width, soft_wrap=True):
    """
    Map logical (x, y) to visual (vx, vy).

    With soft_wrap on, vy counts wrapped rows and vx is the column
    inside the wrapped row. With soft_wrap off the mapping is the
    identity (horizontal scrolling handles overflow).
    """
    if not soft_wrap:
        return x, y

    if width < 1:
        width = 1

    vy = 0

    for i in range(y):
        vy += line_row_count(visual_width(lines[i]), width)

    if not (0 <= y < len(lines)):
        return 0, vy

    line = lines[y]
    length = len(line)

    if length == 0:
        return 0, vy

    # x is a logical character position.
    # Convert the characters before x into visual columns.
    visual_x = visual_width(line[:x])

    offset_rows = visual_x // width
    vx = visual_x % width

    # Cursor at the exact visual end of a full-width line
    # sits at column 0 of the next visual row.
    total_width = visual_width(line)

    if x == length and total_width % width == 0:
        offset_rows = total_width // width
        vx = 0

    return vx, vy + offset_rows


def get_logical_from_visual(target_vy, lines, width, soft_wrap=True):
    """Inverse of get_visual_position on the row axis."""
    if not soft_wrap:
        return target_vy

    if width < 1:
        width = 1

    vy = 0

    for y, line in enumerate(lines):
        rows = line_row_count(visual_width(line), width)

        if vy + rows > target_vy:
            return y

        vy += rows

    return max(0, len(lines) - 1)

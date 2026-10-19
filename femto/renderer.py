"""
Terminal rendering engine for Femto using curses.

Highlighting is stateful (PR #29): lexical state is carried across lines
via highlight_line(line, entering_state) and cached per buffer in
`_highlight_caches`, keyed by buffer identity + revision + filename.
Caches are released explicitly (release_buffer) AND automatically when
the Buffer object is garbage-collected (weakref.finalize).

Git gutter markers (v0.0.4a02): shows +/~/- symbols in the line-number
gutter for uncommitted changes vs. HEAD.
"""

import curses
import os
import weakref
from femto.theme import load_theme, nearest_xterm_256, xterm_256_rgb
from femto import __version__, __app_name__
from femto.layout import chunk_line, get_visual_position
from femto.diffview import count_diffs

try:
    from femto.highlight import highlight_line
except ImportError:  # fallback for stateless highlight modules
    def highlight_line(line, entering_state=None):
        from femto.highlight import get_spans
        return get_spans(line), None

BAR_STYLE = "color"


def _load_keybindings():
    for modname in ("femto.help", "femto.keys", "femto.app"):
        try:
            mod = __import__(modname, fromlist=["KEYBINDINGS"])
        except Exception:
            continue
        cat = getattr(mod, "KEYBINDINGS", None)
        if cat:
            return cat
    return {"General": [("^X", "Exit"), ("^S", "Save"), ("F1", "Help")]}


class Renderer:
    def __init__(self, stdscr, config):
        self.stdscr = stdscr
        self.config = config
        self.bar_attr = curses.A_REVERSE
        self.prompt_attr = curses.A_REVERSE | curses.A_BOLD
        self.sel_attr = curses.A_REVERSE
        self.match_attr = curses.A_REVERSE | curses.A_BOLD
        self.all_match_attr = curses.A_UNDERLINE
        self.gutter_attr = curses.A_BOLD
        self.git_marker_attr = curses.A_BOLD
        self._last_sig = None
        self._chunk_cache = {}
        self._hard_cache = {}
        self._highlight_caches = {}
        self.setup_colors()


    def setup_colors(self):
        if BAR_STYLE != "color":
            return

        try:
            curses.start_color()

            try:
                curses.use_default_colors()
                default_fg = -1
                default_bg = -1
            except curses.error:
                default_fg = curses.COLOR_WHITE
                default_bg = curses.COLOR_BLACK

            theme = load_theme(getattr(self.config, "theme", "default"))
            available_colors = min(curses.COLORS, 256)

            if available_colors < 1 or curses.COLOR_PAIRS <= 11:
                return

            truecolor = (
                os.environ.get("COLORTERM", "").lower()
                in ("truecolor", "24bit")
                and curses.can_change_color()
            )

            color_cache = {}
            next_color = 8

            def resolve_rgb(rgb):
                nonlocal next_color

                if rgb in color_cache:
                    return color_cache[rgb]

                if truecolor and next_color < available_colors:
                    color_id = next_color
                    next_color += 1
                    red, green, blue = rgb
                    curses.init_color(
                        color_id,
                        round(red * 1000 / 255),
                        round(green * 1000 / 255),
                        round(blue * 1000 / 255),
                    )
                elif available_colors >= 256:
                    color_id = nearest_xterm_256(rgb)
                else:
                    color_id = min(
                        range(available_colors),
                        key=lambda index: sum(
                            (component - palette_component) ** 2
                            for component, palette_component in zip(
                                rgb, xterm_256_rgb(index)
                            )
                        ),
                    )

                color_cache[rgb] = color_id
                return color_id

            def resolve_color(value, is_background=False):
                if value is None:
                    return default_bg if is_background else default_fg

                if isinstance(value, int):
                    if value < available_colors:
                        return value
                    value = xterm_256_rgb(value)

                return resolve_rgb(value)

            pair_sections = {
                1: "status_bar",
                2: "prompt",
                3: "comment",
                4: "string",
                5: "keyword",
                6: "number",
                7: "gutter",
                8: "git_marker",
                9: "selection",
                10: "match",
            }

            pair_attrs = {}

            for pair_id, section in pair_sections.items():
                colors = theme.get(section, {})
                foreground = resolve_color(colors.get("foreground"))
                background = resolve_color(
                    colors.get("background"), is_background=True
                )
                curses.init_pair(pair_id, foreground, background)
                pair_attrs[section] = curses.color_pair(pair_id)

            self.trailing_ws_attr = pair_attrs["match"]

            self.bar_attr = pair_attrs["status_bar"]
            self.prompt_attr = pair_attrs["prompt"] | curses.A_BOLD
            self.gutter_attr = pair_attrs["gutter"] | curses.A_BOLD
            self.git_marker_attr = pair_attrs["git_marker"] | curses.A_BOLD

            selection = theme.get("selection", {})
            if (
                selection.get("foreground") is None
                and selection.get("background") is None
            ):
                self.sel_attr = curses.A_REVERSE
            else:
                self.sel_attr = pair_attrs["selection"]

            self.match_attr = pair_attrs["match"]

        except (curses.error, ValueError, FileNotFoundError):
            pass

    def get_dimensions(self):
        height, width = self.stdscr.getmaxyx()
        return max(1, height - 2), max(1, width)

    def _safe_addstr(self, row, col, text, attr=0):
        try:
            if attr:
                self.stdscr.addstr(row, col, text, attr)
            else:
                self.stdscr.addstr(row, col, text)
        except curses.error:
            pass

    def _safe_move(self, row, col):
        try:
            self.stdscr.move(row, col)
        except curses.error:
            pass

    def _flash_screen(self):
        """Invert rendered attributes, preserving text, color pairs and cursor."""
        position = None
        try:
            position = self.stdscr.getyx()
            rows, cols = self.stdscr.getmaxyx()
            for row in range(rows):
                # Read a complete row before changing attributes. This also avoids
                # toggling the second cell of a wide glyph twice.
                attrs = [self.stdscr.inch(row, col) & curses.A_ATTRIBUTES
                         for col in range(cols)]
                start = 0
                while start < cols:
                    end = start + 1
                    while end < cols and attrs[end] == attrs[start]:
                        end += 1
                    self.stdscr.chgat(row, start, end - start,
                                      attrs[start] ^ curses.A_REVERSE)
                    start = end
        except curses.error:
            # A resize or an unsupported terminal must not interrupt editing.
            pass
        finally:
            if position is not None:
                self._safe_move(*position)

    def _refresh_screen(self, visual_bell=False):
        if visual_bell:
            self._flash_screen()
        try:
            self.stdscr.refresh()
        except curses.error:
            pass

    # ── chunk caches ──────────────────────────────────────────
    def _chunks_for(self, line, width):
        key = (line, width)
        chunks = self._chunk_cache.get(key)
        if chunks is None:
            chunks = chunk_line(line, width)
            if len(self._chunk_cache) > 2048:
                self._chunk_cache.clear()
            self._chunk_cache[key] = chunks
        return chunks

    def _hard_chunks_for(self, line, width):
        key = (line, width)
        chunks = self._hard_cache.get(key)
        if chunks is None:
            chunks = [line[i:i + width] for i in range(0, len(line), width)]
            if not chunks:
                chunks = [""]
            if len(self._hard_cache) > 2048:
                self._hard_cache.clear()
            self._hard_cache[key] = chunks
        return chunks

    def _chunks(self, line, width):
        if getattr(self.config, 'wrap_at_word', True):
            return self._chunks_for(line, width)
        return self._hard_chunks_for(line, width)

    # ── stateful highlighting (PR #29 contract) ───────────────
    def _highlights_for(self, buffer, y):
        """Spans for line y, carrying lexical state from line 0.

        Cached per buffer in `_highlight_caches`, invalidated by
        revision/filename change and by any line-text change above y.
        """
        if not (self.config.syntax_highlight and buffer.filename
                and buffer.filename.endswith('.py')):
            return []
        key = id(buffer)
        rev = getattr(buffer, 'revision', 0)
        ent = self._highlight_caches.get(key)
        if ent is None or ent['rev'] != rev or ent['fn'] != buffer.filename:
            ent = {'rev': rev, 'fn': buffer.filename, 'rows': []}
            self._highlight_caches[key] = ent
            # Auto-evict when the Buffer object is discarded
            try:
                weakref.finalize(buffer, self._highlight_caches.pop,
                                 key, None)
            except TypeError:
                pass
        rows = ent['rows']

        # validate cached prefix; truncate at first changed line
        for i in range(min(len(rows), y + 1)):
            ln = buffer.lines[i] if i < len(buffer.lines) else ''
            if rows[i][0] != ln:
                del rows[i:]
                break

        state = rows[-1][2] if rows else None
        i = len(rows)
        while i <= y:
            ln = buffer.lines[i] if i < len(buffer.lines) else ''
            spans, state = highlight_line(ln, state)
            rows.append((ln, spans, state))
            i += 1
        return rows[y][1]

    def release_buffer(self, buffer):
        """Drop the highlight cache for a discarded buffer."""
        self._highlight_caches.pop(id(buffer), None)

    forget_buffer = release_buffer
    drop_buffer = release_buffer
    discard_buffer = release_buffer

    # ── text area ─────────────────────────────────────────────
    def draw_text(self, buffer, cursor, screen_rows, screen_cols,
                  sel=None, match=None, all_matches=None, git_markers=None,
                  column_mode=False):
        gutter_width = (len(str(len(buffer.lines))) + 1
                        if self.config.show_line_numbers else 0)
        text_cols = max(1, screen_cols - gutter_width)

        if not self.config.soft_wrap:
            self._draw_text_hard(buffer, cursor, screen_rows, text_cols,
                                 sel, match, all_matches, gutter_width,
                                 git_markers)
            return

        visual_row = 0
        for y, line in enumerate(buffer.lines):
            chunks = self._chunks(line, text_cols)
            for i, chunk in enumerate(chunks):
                if visual_row < cursor.scroll_y:
                    visual_row += 1
                    continue
                if visual_row >= cursor.scroll_y + screen_rows:
                    return
                draw_y = visual_row - cursor.scroll_y
                if self.config.show_line_numbers:
                    # Git marker for soft-wrap (only on first chunk of line)
                    marker = ''
                    if git_markers and i == 0 and (y + 1) in git_markers:
                        marker = git_markers[y + 1]
                    
                    if i == 0:
                        if marker:
                            num = marker + str(y + 1).rjust(gutter_width - 2) + " "
                        else:
                            num = str(y + 1).rjust(gutter_width - 1) + " "
                        self._safe_addstr(draw_y, 0, num, self.gutter_attr)
                    else:
                        self._safe_addstr(draw_y, 0, " " * gutter_width)
                self._safe_move(draw_y, gutter_width)
                try:
                    self.stdscr.clrtoeol()
                except curses.error:
                    pass
                highlights = self._highlights_for(buffer, y)

                # Inject trailing whitespace highlight
                if self.config.show_trailing_ws and line != line.rstrip():
                    trail_start = len(line.rstrip())
                    highlights.append((trail_start, len(line), 10))

                logical_x0 = sum(len(c) for c in chunks[:i])
                self._draw_chunk(draw_y, chunk, logical_x0, y, sel, match,
                                 all_matches, highlights, gutter_width,
                                 column_mode)
                visual_row += 1

        while visual_row - cursor.scroll_y < screen_rows:
            draw_y = visual_row - cursor.scroll_y
            if draw_y >= 0:
                if self.config.show_line_numbers:
                    self._safe_addstr(draw_y, 0, " " * gutter_width)
                self._safe_addstr(draw_y, gutter_width, "~", curses.A_BOLD)
            visual_row += 1

    def _draw_text_hard(self, buffer, cursor, screen_rows, text_cols,
                        sel, match, all_matches, gutter_width, git_markers=None,
                        column_mode=False):
        for row in range(screen_rows):
            y = row + cursor.scroll_y
            if self.config.show_line_numbers:
                if y < len(buffer.lines):
                    # Check for git marker
                    marker = ''
                    if git_markers and (y + 1) in git_markers:
                        marker = git_markers[y + 1]
                    
                    if marker:
                        # Draw marker + line number (adjusted spacing)
                        num = marker + str(y + 1).rjust(gutter_width - 2) + " "
                        self._safe_addstr(row, 0, num, self.git_marker_attr)
                    else:
                        num = str(y + 1).rjust(gutter_width - 1) + " "
                        self._safe_addstr(row, 0, num, self.gutter_attr)
                else:
                    self._safe_addstr(row, 0, " " * gutter_width)
            if y < len(buffer.lines):
                x0 = cursor.scroll_x
                chunk = buffer.lines[y][x0:x0 + text_cols]
                highlights = self._highlights_for(buffer, y)
                
                # Inject trailing whitespace highlight
                line = buffer.lines[y]
                if self.config.show_trailing_ws and line != line.rstrip():
                    trail_start = len(line.rstrip())
                    highlights.append((trail_start, len(line), 10))

                self._draw_chunk(row, chunk, x0, y, sel, match, all_matches,
                                 highlights, gutter_width, column_mode)
            else:
                self._safe_addstr(row, gutter_width, "~", curses.A_BOLD)
                
    def draw_filetree(self, screen_rows, screen_cols, filetree):
        """Draw the file tree sidebar."""
        try:
            self.stdscr.erase()
        except curses.error:
            pass
        
        # Title bar
        self._draw_bar(0, " File Browser - F2/Esc to close ",
                       screen_cols, self.bar_attr)
        
        if not filetree or not filetree.entries:
            self._safe_addstr(2, 2, "No files found.")
        else:
            tree_width = min(30, screen_cols // 3)
            text_width = screen_cols - tree_width
            
            # Draw tree sidebar
            visible = filetree.get_visible_entries(screen_rows - 2)
            for i, (name, path, is_dir, depth) in enumerate(visible):  # Changed: removed _
                row = i + 1
                actual_idx = filetree.scroll_y + i
                
                # Highlight current selection
                attr = curses.A_REVERSE if actual_idx == filetree.current else 0
                
                # Indent based on depth
                indent = "  " * depth
                
                # Directory marker with expansion indicator
                if is_dir:
                    marker = "FOLD " if path in filetree.expanded else "FOLD "
                else:
                    marker = "FILE "
                
                display = f"{indent}{marker}{name}"
                self._safe_addstr(row, 0, display[:tree_width], attr)
            
            # Draw separator
            for row in range(1, screen_rows - 1):
                self._safe_addstr(row, tree_width, "│")
            
            # Draw file preview or current file info
            current_path = filetree.get_current_path()
            if current_path:
                preview_text = f"Selected: {current_path}"
                self._safe_addstr(1, tree_width + 2, preview_text[:text_width - 2])
        
        # Help bar
        self._draw_bar(screen_rows - 1,
                       " ↑↓ Navigate  Enter Open/Expand  F2/Esc Close",
                       screen_cols, self.bar_attr)
        
        try:
            self.stdscr.refresh()
        except curses.error:
            pass

    # ── overlays ─────────────────────────────────────────────
    def _overlap(self, bounds, x0, y, chunk_len, column_mode=False):
        """Compute the overlap interval between bounds and the chunk at (y, x0)."""
        (sx, sy), (ex, ey) = bounds
        
        if column_mode:
            # Column mode: bounds are (col_lo, row_lo), (col_hi, row_hi)
            if not (sy <= y <= ey):
                return None
            lo = max(0, sx - x0)
            hi = min(chunk_len, ex - x0)
            return (lo, hi) if lo < hi else None
        else:
            # Linear mode: existing logic
            if not (sy <= y <= ey):
                return None
            line_start = sx if y == sy else 0
            line_end = ex if y == ey else x0 + chunk_len
            lo = max(0, line_start - x0)
            hi = min(chunk_len, line_end - x0)
            return (lo, hi) if lo < hi else None

    def _draw_chunk(self, row, chunk, x0, y, sel, match, all_matches,
                    highlights, gutter_offset=0, column_mode=False):
        if not chunk:
            return
        intervals = []
        for hs, he, color_id in highlights:
            lo = max(0, hs - x0)
            hi = min(len(chunk), he - x0)
            if lo < hi:
                intervals.append((lo, hi, curses.color_pair(color_id)))
        if all_matches:
            for mx, my, ml in all_matches:
                if my == y:
                    lo = max(0, mx - x0)
                    hi = min(len(chunk), mx + ml - x0)
                    if lo < hi:
                        intervals.append((lo, hi, self.all_match_attr))
        if match is not None:
            mx, my, ml = match
            if my == y:
                lo = max(0, mx - x0)
                hi = min(len(chunk), mx + ml - x0)
                if lo < hi:
                    intervals.append((lo, hi, self.match_attr))
        if sel is not None:
            iv = self._overlap(sel, x0, y, len(chunk), column_mode)
            if iv:
                intervals.append((iv[0], iv[1], self.sel_attr))
        self._safe_addstr(row, gutter_offset, chunk)
        for lo, hi, attr in intervals:
            self._safe_addstr(row, gutter_offset + lo, chunk[lo:hi], attr)

    # ── bars / help / cursor ──────────────────────────────────
    def draw_status_bar(self, buffer, cursor, screen_rows, screen_cols,
                        message="", mark_set=False, doc_index=0, doc_count=1):
        status = f" {__app_name__} v{__version__}"
        status += f"  {buffer.filename or 'New Buffer'}"
        if doc_count > 1:
            status += f"  [{doc_index + 1}/{doc_count}]"
        if buffer.modified:
            status += "  [Modified]"
        if mark_set:
            status += "  [Mark]"
        if self.config.mouse:
            status += "  [Mouse]"
        status += f"  Ln {cursor.y + 1}, Col {cursor.x + 1}"
        if message:
            status += f"  | {message}"
        self._draw_bar(screen_rows, status, screen_cols, self.bar_attr)
        self._draw_bar(screen_rows + 1,
                       "^X Exit  ^S Save  ^W Find  ^K Cut  ^P/^U Copy/Paste  "
                       "^F/^L Buf  F1 Help", screen_cols, self.bar_attr)

    def draw_prompt(self, prompt, screen_rows, screen_cols, help_text=""):
        self._draw_bar(screen_rows, prompt.get_display(screen_cols),
                       screen_cols, self.prompt_attr)
        self._draw_bar(screen_rows + 1, help_text, screen_cols, self.bar_attr)
        cx = min(prompt.get_cursor_x(), screen_cols - 1)
        self._safe_move(screen_rows, cx)

    def _draw_confirm(self, display, help_text, screen_rows, screen_cols):
        self._draw_bar(screen_rows, display, screen_cols, self.prompt_attr)
        self._draw_bar(screen_rows + 1, help_text, screen_cols, self.bar_attr)

    def draw_exit_confirm(self, message, screen_rows, screen_cols):
        self._draw_confirm(f" {message}  (Y)es / (N)o / (C)ancel",
                           "Y Yes    N No    C Cancel",
                           screen_rows, screen_cols)

    def draw_replace_confirm(self, message, screen_rows, screen_cols):
        self._draw_confirm(f" {message}  (Y)es / (N)o / (A)ll / (C)ancel",
                           "Y Yes    N No    A All    C Cancel",
                           screen_rows, screen_cols)

    def draw_help_screen(self, screen_rows, screen_cols, help_scroll_y,
                         keybindings, visual_bell=False):
        try:
            self.stdscr.erase()
        except curses.error:
            pass
        self._draw_bar(0, f" {__app_name__} Help - Esc or q returns ",
                       screen_cols, self.bar_attr)
        if not keybindings:
            keybindings = _load_keybindings()
        content = []
        for category, bindings in keybindings.items():
            content.append((f"-- {category} --", curses.A_BOLD))
            for item in bindings:
                if isinstance(item, (tuple, list)) and len(item) == 2:
                    content.append((f"   {item[0]:<22} {item[1]}", 0))
                else:
                    content.append((f"   {item}", 0))
            content.append(("", 0))
        last = max(0, screen_rows - 2)
        for idx, (text, attr) in enumerate(content):
            vis = idx - help_scroll_y
            if vis < 0:
                continue
            if vis > last:
                break
            self._safe_addstr(1 + vis, 0, text[:screen_cols], attr)
        more = "  ..." if help_scroll_y + (last + 1) < len(content) else ""
        self._draw_bar(screen_rows - 1,
                       f" Up/Down scroll   PgUp/PgDn page   Esc/q exit{more}",
                       screen_cols, self.bar_attr)
        self._refresh_screen(visual_bell)

    def _draw_bar(self, row, text, width, attr):
        text = text.ljust(width)[:width]
        try:
            self.stdscr.addstr(row, 0, text, attr)
        except curses.error:
            pass

    def draw_cursor(self, cursor, buffer, screen_cols):
        gutter_width = (len(str(len(buffer.lines))) + 1
                        if self.config.show_line_numbers else 0)
        text_cols = max(1, screen_cols - gutter_width)
        vx, vy = get_visual_position(cursor.x, cursor.y, buffer.lines,
                                     text_cols, self.config.soft_wrap)
        try:
            self.stdscr.move(vy - cursor.scroll_y,
                             vx - cursor.scroll_x + gutter_width)
        except curses.error:
            pass

    def draw_grep_results(self, screen_rows, screen_cols,
                    grep_results, grep_current, visual_bell=False):
        """Draw grep results list."""
        try:
            self.stdscr.erase()
        except curses.error:
            pass

        self._draw_bar(0, " Grep Results - Enter to open, Esc/q to close ",
                screen_cols, self.bar_attr)

        if not grep_results:
            self._safe_addstr(2, 2, "No matches found.")
        else:
            # Calculate visible range
            visible_start = max(0, grep_current - screen_rows // 2)
            visible_end = min(len(grep_results), visible_start + screen_rows - 2)

            for i in range(visible_start, visible_end):
                row = i - visible_start + 1
                filepath, line_num, line_text = grep_results[i]

                # Highlight current selection
                attr = curses.A_REVERSE if i == grep_current else 0

                # Format: filepath:line_num: line_text
                display = f"{filepath}:{line_num}: {line_text[:screen_cols - 30]}"
                self._safe_addstr(row, 0, display[:screen_cols], attr)

        # Help bar
        self._draw_bar(screen_rows - 1,
                f" {grep_current + 1}/{len(grep_results)} "
                "Up/Down navigate Enter open Esc/q close",
                screen_cols, self.bar_attr)

        self._refresh_screen(visual_bell)

    _PROMPT_HELP = {
        "save_as": "Enter Save    Tab Complete    ^G Cancel",
        "search": "Enter Find Next    ^O Case    ^R Regex    ^G Cancel",
        "replace_search": "Enter Continue    ^O Case    ^R Regex    ^G Cancel",
        "replace_with": "Enter Confirm    ^G Cancel",
        "goto_line": "Enter Jump    ^G Cancel",
        "diff_pick": "Enter Compare    ^G Cancel",
    }

    # ── main entry ────────────────────────────────────────────
    def render(self, buffer, cursor, message="", prompt=None, mode="normal",
               selection=None, mark_set=False, column_mode=False, match=None,
               all_matches=None, keybindings=None,
               doc_index=0, doc_count=1, help_scroll_y=0,
               git_markers=None, grep_results=None, grep_current=None,
               visual_bell=False, filetree=None, diff_state=None):
        screen_rows, screen_cols = self.get_dimensions()

        if mode == "help":
            self._last_sig = None
            self.draw_help_screen(screen_rows, screen_cols,
                                  help_scroll_y, keybindings, visual_bell)
            return

        if mode == "grep":
            self._last_sig = None
            self.draw_grep_results(screen_rows, screen_cols,
                        grep_results, grep_current, visual_bell)
            return

        if mode == "diff":
            self.draw_diff(screen_rows, screen_cols, diff_state)
            return
            
        if mode == "filetree":
            self.draw_filetree(screen_rows, screen_cols, filetree)
            return

        sig = (
            id(buffer),
            getattr(buffer, "revision", 0),
            buffer.filename,
            cursor.x, cursor.y, cursor.scroll_x, cursor.scroll_y,
            selection, column_mode, match, message, mode, mark_set,
            screen_rows, screen_cols, doc_index, doc_count,
            self.config.show_line_numbers, self.config.mouse,
            self.config.syntax_highlight, self.config.soft_wrap,
            getattr(self.config, 'wrap_at_word', True),
            (len(all_matches), all_matches[0] if all_matches else None)
            if all_matches else None,
            (prompt.label, prompt.text, prompt.cursor_pos)
            if prompt and prompt.active else None,
            frozenset(git_markers.items()) if git_markers else None,
            visual_bell,
            (diff_state['current'], diff_state['scroll']) if diff_state else None,
        )
        if sig == self._last_sig:
            return
        self._last_sig = sig

        try:
            self.stdscr.erase()
        except curses.error:
            pass

        self.draw_text(buffer, cursor, screen_rows, screen_cols,
                       selection, match, all_matches, git_markers, column_mode)

        if prompt and prompt.active and mode in self._PROMPT_HELP:
            self.draw_prompt(prompt, screen_rows, screen_cols,
                             self._PROMPT_HELP[mode])
        elif mode == "exit_confirm":
            self.draw_exit_confirm(message, screen_rows, screen_cols)
            self.draw_cursor(cursor, buffer, screen_cols)
        elif mode == "replace_confirm":
            self.draw_replace_confirm(message, screen_rows, screen_cols)
            self.draw_cursor(cursor, buffer, screen_cols)
        else:
            self.draw_status_bar(buffer, cursor, screen_rows, screen_cols,
                                 message, mark_set, doc_index, doc_count)
            self.draw_cursor(cursor, buffer, screen_cols)

        self._refresh_screen(visual_bell)

    def draw_diff(self, screen_rows, screen_cols, st):
        """Draw the side-by-side diff view."""
        try:
            self.stdscr.erase()
        except curses.error:
            pass
        if not st:
            self._draw_bar(screen_rows - 1, " No diff loaded ", screen_cols,
                           self.bar_attr)
            return

        self._draw_bar(0, f" Diff: {st['left_name']}  <->  {st['right_name']} ",
                       screen_cols, self.bar_attr)

        half = max(10, (screen_cols - 1) // 2)

        # Pane headers
        self._safe_addstr(1, 0, st['left_name'][:half], curses.A_BOLD)
        self._safe_addstr(1, half + 1,
                          st['right_name'][:screen_cols - half - 1],
                          curses.A_BOLD)

        vis = max(1, screen_rows - 4)
        for i in range(vis):
            idx = st['scroll'] + i
            row = 2 + i
            if idx >= len(st['rows']):
                break
            li, ri, kind = st['rows'][idx]

            if kind == 'added':
                attr = curses.color_pair(3)     # green
            elif kind == 'removed':
                attr = curses.color_pair(8)     # red
            elif kind == 'changed':
                attr = curses.color_pair(6)     # yellow
            else:
                attr = 0
            cur = curses.A_REVERSE if idx == st['current'] else 0

            ltext = f"{li + 1:>4} {st['left'][li]}" if li is not None else "     --"
            rtext = f"{ri + 1:>4} {st['right'][ri]}" if ri is not None else "     --"

            self._safe_addstr(row, 0, ltext[:half], attr | cur)
            self._safe_addstr(row, half, "|", curses.A_BOLD)
            self._safe_addstr(row, half + 1,
                              rtext[:screen_cols - half - 1], attr | cur)

        self._draw_bar(screen_rows - 1,
                       f" row {st['current'] + 1}/{len(st['rows'])}"
                       f"  diffs: {count_diffs(st['rows'])}"
                       "   n/p next/prev   q/F3 close",
                       screen_cols, self.bar_attr)
        try:
            self.stdscr.refresh()
        except curses.error:
            pass

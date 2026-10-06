"""
Main Application Controller for Femto.
Multi-buffer: every per-file state lives in a Document; the Application
keeps a list plus the shared clipboard / search options / replace flow.
"""

import signal
import curses
import os

from femto.documents import Document
from femto.help import HelpView
from femto.renderer import Renderer
from femto.layout import (
    get_visual_position,
    get_logical_from_visual,
    get_logical_from_visual_point,
)
from femto.prompt import Prompt
from femto.clipboard import Clipboard
from femto.config import Config
from femto.search import SearchOptions, find_all, find_next, replace_in_line
from femto.keys import (
    Key, alt, is_backspace, is_enter, ALT_BASES, CONHOST_ALT_MAP,
)
from femto.help import KEYBINDINGS

HELP_ESCAPE_DELAY_MS = 100


def _ignore_suspend():
    sig = getattr(signal, "SIGTSTP", None)
    if sig is None:
        return
    try:
        signal.signal(sig, signal.SIG_IGN)
    except (OSError, ValueError):
        pass


class Mode:
    NORMAL = "normal"
    HELP = "help"
    SAVE_AS = "save_as"
    SEARCH = "search"
    REPLACE_SEARCH = "replace_search"
    REPLACE_WITH = "replace_with"
    REPLACE_CONFIRM = "replace_confirm"
    GOTO_LINE = "goto_line"
    EXIT_CONFIRM = "exit_confirm"


class Application:
    def __init__(self, filenames=None):
        self.config = Config()
        if isinstance(filenames, str):
            filenames = [filenames]
        if not filenames:
            filenames = [None]
        self.documents = [Document(self.config, fn) for fn in filenames]
        self.current = 0

        self.renderer = None
        self.message = ""
        self.running = True
        self.mode = Mode.NORMAL
        self.help_scroll_y = 0
        self.prompt = Prompt()
        self.clipboard = Clipboard()
        self.search_options = SearchOptions(self.config.ignore_case,
                                            self.config.regex_search)
        self.pending_exit = False
        self.last_search = ""
        self.replace_term = ""
        self.replace_with = ""
        self.replace_count = 0
        self._prompt_base = "Search"
        self._save_target = self.doc
        self._save_queue = []
        self._save_completion_prefix = ""
        self._save_completion_candidates = []
        self._save_completion_index = -1

    # ── per-document shortcuts ────────────────────────────────

    @property
    def doc(self):
        return self.documents[self.current]

    @property
    def buffer(self):
        return self.doc.buffer

    @property
    def cursor(self):
        return self.doc.cursor

    @property
    def history(self):
        return self.doc.history

    @property
    def selection(self):
        return self.doc.selection

    @property
    def last_match(self):
        return self.doc.last_match

    @last_match.setter
    def last_match(self, value):
        self.doc.last_match = value

    @property
    def last_found_pos(self):
        return self.doc.last_found_pos

    @last_found_pos.setter
    def last_found_pos(self, value):
        self.doc.last_found_pos = value

    # ── helpers ─────────────────────────────────────────────

    def _snapshot(self):
        self.history.push(self.buffer.lines, self.cursor.x, self.cursor.y)

    def _gutter_width(self):
        if not self.config.show_line_numbers:
            return 0
        return len(str(len(self.buffer.lines))) + 1

    def _set_mouse(self, on):
        try:
            if on:
                curses.mousemask(curses.ALL_MOUSE_EVENTS |
                                 curses.REPORT_MOUSE_POSITION)
                curses.mouseinterval(30)
            else:
                curses.mousemask(0)
        except curses.error:
            pass

    def _switch_buffer(self, step):
        if len(self.documents) < 2:
            self.message = "Only one buffer open."
            return
        if self.mode == Mode.REPLACE_CONFIRM:
            self._finish_replace(cancelled=True)
        self.current = (self.current + step) % len(self.documents)
        self.message = (f"Buffer {self.current + 1}/{len(self.documents)}: "
                        f"{self.doc.filename or 'New'}")

    def _pre_edit(self):
        self._snapshot()
        self.last_match = None
        if self.selection.active:
            bounds = self.selection.bounds(self.buffer,
                                           self.cursor.x, self.cursor.y)
            if not self.selection.is_empty(bounds):
                nx, ny = self.selection.delete_range(self.buffer, bounds)
                self.cursor.x, self.cursor.y = nx, ny
                self.selection.clear()

    def _current_bounds(self):
        return self.selection.bounds(self.buffer,
                                     self.cursor.x, self.cursor.y)

    def _search_label(self, base):
        return f"{base}{self.search_options.flag_label()}: "

    def _maybe_toggle(self, key):
        if key == Key.CTRL_O:
            self.search_options.ignore_case = not self.search_options.ignore_case
            self.prompt.label = self._search_label(self._prompt_base)
            return True
        if key == Key.CTRL_R:
            self.search_options.regex = not self.search_options.regex
            self.prompt.label = self._search_label(self._prompt_base)
            return True
        return False

    # ── clipboard ────────────────────────────────────────────

    def _cut(self):
        self._snapshot()
        self.last_match = None
        bounds = self._current_bounds()
        if self.selection.active and not self.selection.is_empty(bounds):
            text = self.selection.extract(self.buffer, bounds)
            nx, ny = self.selection.delete_range(self.buffer, bounds)
            self.cursor.x, self.cursor.y = nx, ny
            self.message = f"Cut {len(text)} chars."
        else:
            y = self.cursor.y
            text = self.buffer.lines[y] + "\n"
            if len(self.buffer.lines) > 1:
                del self.buffer.lines[y]
                self.cursor.x = 0
                self.cursor.y = min(y, self.buffer.max_y)
            else:
                self.buffer.lines[0] = ""
                self.cursor.x = 0
            self.buffer.touch()
            self.message = "Cut line."
        self.selection.clear()
        self.clipboard.store(text)

    def _copy(self):
        bounds = self._current_bounds()
        if self.selection.active and not self.selection.is_empty(bounds):
            text = self.selection.extract(self.buffer, bounds)
            self.message = f"Copied {len(text)} chars."
        else:
            text = self.buffer.lines[self.cursor.y] + "\n"
            self.message = "Copied line."
        self.clipboard.store(text)

    def _paste(self):
        if self.clipboard.empty:
            self.message = "Clipboard is empty."
            return
        self._pre_edit()
        nx, ny = self.clipboard.paste_into(self.buffer,
                                           self.cursor.x, self.cursor.y)
        self.cursor.x, self.cursor.y = nx, ny
        self.message = f"Pasted {len(self.clipboard.text)} chars."

    def _copy_to_clipboard(self, text):
        self.clipboard.store(text)
        if self.config.system_clipboard:
            from femto.sysclip import copy_to_system
            copy_to_system(text)

    def _paste_from_clipboard(self):
        text = self.clipboard.text
        if not text and self.config.system_clipboard:
            from femto.sysclip import paste_from_system
            text = paste_from_system()
            if text:
                self.clipboard.store(text)
        return text

    # ── line operations (v0.0.4) ─────────────────────────────

    def _duplicate(self):
        self._snapshot()
        self.last_match = None
        bounds = self._current_bounds()
        if self.selection.active and not self.selection.is_empty(bounds):
            text = self.selection.extract(self.buffer, bounds)
            (sx, sy), (ex, ey) = bounds
            if sy != ey and sx == 0 and (ex == 0 or ex == self.buffer.get_line_length(ey)):
                end_y = ey if ex > 0 or ey == sy else ey - 1
                lines_to_dup = self.buffer.lines[sy:end_y + 1]
                insert_at = end_y + 1
                self.buffer.lines[insert_at:insert_at] = list(lines_to_dup)
                self.buffer.touch()
                self.cursor.y = insert_at
                self.cursor.x = min(self.cursor.x, self.buffer.get_line_length(self.cursor.y))
            else:
                nx, ny = self.buffer.insert_text(ex, ey, text)
                self.cursor.x, self.cursor.y = nx, ny
            self.selection.clear()
            self.message = "Duplicated selection."
        else:
            y = self.cursor.y
            new_y = self.buffer.duplicate_line(y)
            self.cursor.y = new_y
            self.cursor.x = min(self.cursor.x, self.buffer.get_line_length(new_y))
            self.message = "Duplicated line."

    def _transpose(self):
        if len(self.buffer.lines) <= 1 or self.cursor.y <= 0:
            return
        self._snapshot()
        self.last_match = None
        new_y = self.buffer.transpose_line(self.cursor.y)
        self.cursor.y = new_y
        self.cursor.x = min(self.cursor.x, self.buffer.get_line_length(new_y))
        self.message = "Transposed line."

    def _sort_lines(self, case_sensitive=True):
        bounds = self._current_bounds()
        if not self.selection.active or self.selection.is_empty(bounds):
            self.message = "No selection to sort."
            return
        (sx, sy), (ex, ey) = bounds
        start_y = sy
        end_y = ey if ex > 0 or ey == sy else ey - 1
        if start_y >= end_y:
            self.message = "Need at least 2 lines selected to sort."
            return
        self._snapshot()
        self.last_match = None
        count = self.buffer.sort_lines(start_y, end_y, case_sensitive=case_sensitive)
        self.selection.clear()
        self.message = f"Sorted {count} lines."

    def _transform_case(self, upper=True):
        bounds = self._current_bounds()
        if not self.selection.active or self.selection.is_empty(bounds):
            self.message = "No selection."
            return
        self._snapshot()
        self.last_match = None
        self.buffer.transform_case(bounds, upper=upper)
        self.message = "Uppercase." if upper else "Lowercase."

    # ── mouse ────────────────────────────────────────────────

    def _handle_mouse(self, stdscr):
        if self.mode != Mode.NORMAL:
            return
        try:
            _, mx, my, _, bstate = curses.getmouse()
        except curses.error:
            return

        screen_rows, screen_cols = self.renderer.get_dimensions()
        gutter = self._gutter_width()
        text_cols = max(1, screen_cols - gutter)

        btn4 = getattr(curses, "BUTTON4_PRESSED", None)
        btn5 = getattr(curses, "BUTTON5_PRESSED", None)
        if btn4 and (bstate & btn4):
            self._wheel(-3)
            return
        if btn5 and (bstate & btn5):
            self._wheel(3)
            return

        if bstate & (curses.BUTTON1_PRESSED | curses.BUTTON1_CLICKED):
            if my >= screen_rows:
                return
            vy = my + self.cursor.scroll_y
            vx = max(0, mx - gutter) + self.cursor.scroll_x
            x, y = get_logical_from_visual_point(
                vy, vx, self.buffer.lines, text_cols, self.config.soft_wrap)
            self.cursor.set_pos(x, y,
                                self.buffer.get_line_length,
                                self.buffer.max_y)

    def _wheel(self, dy):
        self.cursor.move(0, dy,
                         self.buffer.get_line_length, self.buffer.max_y)

    # ── input routing ─────────────────────────────────────────

    def handle_input(self, key, screen_rows, screen_cols):
        if self.mode == Mode.HELP:
            self._handle_help(key, screen_rows, screen_cols)
            return
        if self.mode == Mode.NORMAL and key == Key.F1:
            self.help_scroll_y = 0
            self.mode = Mode.HELP
            return
        if self.mode == Mode.SAVE_AS:
            self._handle_save_as(key)
        elif self.mode == Mode.SEARCH:
            self._handle_search(key)
        elif self.mode == Mode.REPLACE_SEARCH:
            self._handle_replace_search(key)
        elif self.mode == Mode.REPLACE_WITH:
            self._handle_replace_with(key)
        elif self.mode == Mode.REPLACE_CONFIRM:
            self._handle_replace_confirm(key)
        elif self.mode == Mode.GOTO_LINE:
            self._handle_goto_line(key)
        elif self.mode == Mode.EXIT_CONFIRM:
            self._handle_exit_confirm(key)
        else:
            self._handle_normal(key, screen_rows, screen_cols)

    def _handle_help(self, key, screen_rows, screen_cols):
        if key in (Key.ESCAPE, ord('q')):
            self.mode = Mode.NORMAL
            return
        actions = {
            Key.ARROW_UP: "up", Key.ARROW_DOWN: "down",
            Key.PAGE_UP: "page_up", Key.PAGE_DOWN: "page_down",
            Key.HOME: "home", Key.END: "end",
        }
        if key in actions:
            view = HelpView(self.help_scroll_y)
            view.move(actions[key], screen_rows, screen_cols)
            self.help_scroll_y = view.offset

    # ── save / exit with multi-buffer queue ───────────────────

    def _reset_save_completion(self):
        self._save_completion_prefix = ""
        self._save_completion_candidates = []
        self._save_completion_index = -1

    def _handle_save_as(self, key):
        if key == Key.TAB:
            self._complete_save_as()
            return

        self._reset_save_completion()

        result = self.prompt.handle_key(key)
        if result == 'confirmed':
            filename = self.prompt.text.strip()
            if not filename:
                return
            target = self._save_target
            target.buffer.filename = filename
            ok = target.buffer.save()
            self.message = (f"Saved: {filename}" if ok
                            else "Error: could not save file.")
            if target in self._save_queue:
                self._save_queue.remove(target)
            self.prompt.deactivate()
            exit_after = self.pending_exit
            if ok and self._save_queue:
                self._save_next_in_queue(exit_after)
            elif ok and exit_after:
                self.running = False
            else:
                self.mode = Mode.NORMAL
                self.pending_exit = False
        elif result == 'cancelled':
            self._exit_prompt_mode()
            self._save_queue = []
            self.message = "Save cancelled."

    def _complete_save_as(self):
        text = self.prompt.text

        if not self._save_completion_candidates:
            directory = os.path.dirname(text) or "."
            prefix = os.path.basename(text)

            try:
                candidates = [
                    name for name in os.listdir(directory)
                    if name.startswith(prefix)
                ]
            except OSError:
                candidates = []

            if not candidates:
                self.message = "No matches."
                return

            self._save_completion_prefix = text
            self._save_completion_candidates = candidates
            self._save_completion_index = -1

            common = os.path.commonprefix(candidates)

            if common != prefix:
                path_prefix = (
                    text[:-len(prefix)] if prefix else text
                )
                completed = path_prefix + common
                self.prompt.text = completed
                self.prompt.cursor_pos = len(completed)
                self.message = "  ".join(candidates)
                return

        candidates = self._save_completion_candidates
        self._save_completion_index = (
            self._save_completion_index + 1
        ) % len(candidates)

        original = self._save_completion_prefix
        directory = os.path.dirname(original)
        path_prefix = (
            original[:-len(os.path.basename(original))]
            if os.path.basename(original)
            else original
        )

        candidate = candidates[self._save_completion_index]
        completed = path_prefix + candidate

        self.prompt.text = completed
        self.prompt.cursor_pos = len(completed)
        self.message = "  ".join(candidates)

    def _save_next_in_queue(self, exit_after):
        """Save queued modified docs; prompt for unnamed ones in turn."""
        self.pending_exit = exit_after
        while self._save_queue:
            d = self._save_queue[0]
            if d.buffer.filename:
                if d.buffer.save():
                    self._save_queue.pop(0)
                    continue
                self.message = "Error: could not save file."
                self._save_queue = []
                self.mode = Mode.NORMAL
                self.pending_exit = False
                return
            self._save_target = d
            self.mode = Mode.SAVE_AS
            self._reset_save_completion()
            self.prompt.start("Save As: ")
            return
        if exit_after:
            self.running = False
        else:
            self.mode = Mode.NORMAL
            self.pending_exit = False

    def _handle_exit_confirm(self, key):
        if key in (ord('y'), ord('Y')):
            self._save_queue = [d for d in self.documents
                                if d.buffer.modified]
            if not self._save_queue:
                self.running = False
                return
            self._save_next_in_queue(exit_after=True)
        elif key in (ord('n'), ord('N')):
            self.running = False
        elif key in (ord('c'), ord('C'), Key.CTRL_G, Key.ESCAPE):
            self.mode = Mode.NORMAL
            self.message = "Exit cancelled."

    # ── search / replace / goto ───────────────────────────────

    def _handle_search(self, key):
        if self._maybe_toggle(key):
            return
        result = self.prompt.handle_key(key)
        if result == 'confirmed':
            term = self.prompt.text
            if term:
                self.last_search = term
                self._find_text(term)
            self._exit_prompt_mode()
        elif result == 'cancelled':
            self._exit_prompt_mode()

    def _get_search_matches(self, term):
        cache_key = (
            self.buffer.revision,
            term,
            self.search_options.ignore_case,
            self.search_options.regex,
        )

        if self.doc.search_cache is not None:
            key, matches = self.doc.search_cache
            if key == cache_key:
                return matches

        matches = find_all(self.buffer, term, self.search_options)
        self.doc.search_cache = (cache_key, matches)
        return matches

    def _find_text(self, term):
        if (self.last_match and
                self.last_match[:2] == (self.cursor.x, self.cursor.y)):
            sx = self.cursor.x + max(1, self.last_match[2])
            sy = self.cursor.y
        else:
            sx, sy = self.cursor.x, self.cursor.y
        matches = self._get_search_matches(term)
        hit = find_next(self.buffer, term, self.search_options, sx, sy)
        if hit:
            x, y, length = hit
            self.cursor.set_pos(x, y, self.buffer.get_line_length,
                                self.buffer.max_y)
            self.last_match = hit
            self.message = f"Found: {term}{self.search_options.flag_label()}"
        else:
            self.message = f"Not found: {term}"
            self.last_match = None

    def _start_replace(self):
        self._prompt_base = "Replace"
        self.mode = Mode.REPLACE_SEARCH
        self.prompt.start(self._search_label("Replace"), self.last_search)

    def _handle_replace_search(self, key):
        if self._maybe_toggle(key):
            return
        result = self.prompt.handle_key(key)
        if result == 'confirmed':
            term = self.prompt.text
            if not term:
                self._exit_prompt_mode()
                return
            self.last_search = term
            self.replace_term = term
            self._prompt_base = "With"
            self.mode = Mode.REPLACE_WITH
            self.prompt.start("With: ")
        elif result == 'cancelled':
            self._exit_prompt_mode()

    def _handle_replace_with(self, key):
        result = self.prompt.handle_key(key)
        if result == 'confirmed':
            self.replace_with = self.prompt.text
            self.prompt.deactivate()
            self.replace_count = 0
            hit = find_next(self.buffer, self.replace_term,
                            self.search_options, self.cursor.x, self.cursor.y)
            if hit is None:
                self.message = f"Not found: {self.replace_term}"
                self.last_match = None
                self.mode = Mode.NORMAL
            else:
                self.last_match = hit
                self.cursor.set_pos(hit[0], hit[1],
                                    self.buffer.get_line_length,
                                    self.buffer.max_y)
                self.mode = Mode.REPLACE_CONFIRM
        elif result == 'cancelled':
            self._exit_prompt_mode()

    def _handle_replace_confirm(self, key):
        if key in (ord('y'), ord('Y')):
            self._replace_current()
            self._advance_replace(replaced=True)
        elif key in (ord('n'), ord('N')):
            self._advance_replace(replaced=False)
        elif key in (ord('a'), ord('A')):
            while self.last_match is not None:
                self._replace_current()
                self._advance_replace(replaced=True)
        elif key in (ord('c'), ord('C'), Key.CTRL_G, Key.ESCAPE):
            self._finish_replace(cancelled=True)

    def _replace_current(self):
        mx, my, ml = self.last_match
        self._snapshot()
        self.buffer.lines[my] = replace_in_line(
            self.buffer.lines[my], mx, mx + ml, self.replace_with)
        self.buffer.touch()
        self.replace_count += 1
        self.cursor.set_pos(mx + len(self.replace_with), my,
                            self.buffer.get_line_length, self.buffer.max_y)

    def _advance_replace(self, replaced):
        mx, my, ml = self.last_match
        if replaced:
            nx = mx + len(self.replace_with)
            if ml == 0 and not self.replace_with:
                nx = mx + 1
        else:
            nx = mx + ml if ml else mx + 1
        hit = find_next(self.buffer, self.replace_term, self.search_options,
                        nx, my, wrap=False)
        if hit is None:
            self._finish_replace()
        else:
            self.last_match = hit
            self.cursor.set_pos(hit[0], hit[1],
                                self.buffer.get_line_length,
                                self.buffer.max_y)

    def _finish_replace(self, cancelled=False):
        self.last_match = None
        self.mode = Mode.NORMAL
        if cancelled:
            self.message = (f"Replace cancelled "
                            f"({self.replace_count} replaced).")
        else:
            self.message = f"Replaced {self.replace_count} occurrence(s)."

    def _handle_goto_line(self, key):
        result = self.prompt.handle_key(key)
        if result == 'confirmed':
            raw = self.prompt.text.strip()
            try:
                target = int(raw)
                target_y = max(0, min(target - 1, self.buffer.max_y))
                self.cursor.set_pos(0, target_y,
                                    self.buffer.get_line_length,
                                    self.buffer.max_y)
                self.message = f"Line {target_y + 1}/{self.buffer.max_y + 1}"
            except ValueError:
                self.message = "Invalid line number."
            self._exit_prompt_mode()
        elif result == 'cancelled':
            self._exit_prompt_mode()

    # ── NORMAL mode ───────────────────────────────────────────

    def _handle_normal(self, key, screen_rows, screen_cols):
        self.message = ""
        buf = self.buffer
        cur = self.cursor
        max_x = buf.get_line_length
        max_y = buf.max_y

        if key == Key.CTRL_X:
            if any(d.buffer.modified for d in self.documents):
                self.mode = Mode.EXIT_CONFIRM
                self.message = "Save modified buffers?"
            else:
                self.running = False
            return
        if key == Key.CTRL_S:
            self._save_target = self.doc
            if buf.filename:
                if buf.save():
                    self.message = "File saved."
                else:
                    self.message = "Error: could not save file."
            else:
                self.mode = Mode.SAVE_AS
                self._reset_save_completion()
                self.prompt.start("Save As: ")
            return
        if key == Key.CTRL_F:
            self._switch_buffer(1); return
        if key == Key.CTRL_L:
            self._switch_buffer(-1); return
        if key == Key.CTRL_W:
            self._prompt_base = "Search"
            self.mode = Mode.SEARCH
            self.prompt.start(self._search_label("Search"), self.last_search)
            return
        if key == Key.CTRL_BACKSLASH:
            self._start_replace()
            return
        if key == Key.CTRL_T:
            self.mode = Mode.GOTO_LINE
            self.prompt.start("Go To Line: ")
            return

        # Clipboard
        if key == Key.CTRL_B:
            if self.selection.toggle(cur.x, cur.y):
                self.message = "Mark set."
            else:
                self.message = "Mark off."
            return
        if key == Key.CTRL_K:
            self._cut(); return
        if key == Key.CTRL_P:
            self._copy(); return
        if key == Key.CTRL_U:
            self._paste(); return

        # Toggles
        if key == Key.CTRL_N:
            self.config.show_line_numbers = not self.config.show_line_numbers
            self.message = ("Line numbers " +
                            ("on" if self.config.show_line_numbers else "off"))
            return
        if key == Key.CTRL_D:
            self.config.mouse = not self.config.mouse
            self._set_mouse(self.config.mouse)
            self.message = ("Mouse " +
                            ("on" if self.config.mouse else "off"))
            return

        # Undo / Redo
        if key == Key.CTRL_Z:
            self._do_undo(); return
        if key == Key.CTRL_Y:
            self._do_redo(); return

        # Line operations (v0.0.4)
        if key in (Key.ALT_D, alt(ord('D'))):
            self._duplicate(); return
        if key in (Key.ALT_T, alt(ord('T'))):
            self._transpose(); return
        if key == Key.ALT_S:
            self._sort_lines(case_sensitive=True); return
        if key == Key.ALT_SHIFT_S:
            self._sort_lines(case_sensitive=False); return
        if key in (Key.ALT_U, alt(ord('U'))):
            self._transform_case(upper=True); return
        if key in (Key.ALT_L, alt(ord('L'))):
            self._transform_case(upper=False); return

        # Navigation
        if key == Key.CTRL_LEFT:
            cur.x = buf.get_prev_word_pos(cur.y, cur.x)
        elif key == Key.CTRL_RIGHT:
            cur.x = buf.get_next_word_pos(cur.y, cur.x)
        elif key == Key.PAGE_UP:
            self._page(-1, screen_rows, screen_cols)
        elif key == Key.PAGE_DOWN:
            self._page(1, screen_rows, screen_cols)
        elif key == Key.HOME or key == Key.CTRL_A:
            cur.home()
        elif key == Key.END or key == Key.CTRL_E:
            cur.end(max_x(cur.y))
        elif key == Key.ARROW_UP:
            cur.move(0, -1, max_x, max_y)
        elif key == Key.ARROW_DOWN:
            cur.move(0, 1, max_x, max_y)
        elif key == Key.ARROW_LEFT:
            if cur.x > 0:
                cur.x -= 1
            elif cur.y > 0:
                cur.y -= 1
                cur.x = max_x(cur.y)
        elif key == Key.ARROW_RIGHT:
            if cur.x < max_x(cur.y):
                cur.x += 1
            elif cur.y < max_y:
                cur.y += 1
                cur.x = 0

        # Editing
        elif key == Key.TAB:
            self._pre_edit()
            cur.x = buf.insert_tab(cur.y, cur.x)
        elif key == Key.SHIFT_TAB:
            self._pre_edit()
            cur.x = buf.remove_tab(cur.y, cur.x)
        elif is_backspace(key):
            self._pre_edit()
            cur.x, cur.y = buf.backspace(cur.x, cur.y)
        elif key == Key.DELETE:
            self._pre_edit()
            buf.delete_char(cur.x, cur.y)
        elif is_enter(key):
            self._pre_edit()
            buf.insert_newline(cur.x, cur.y)
            cur.y += 1

            # Auto-indent logic
            if self.config.auto_indent:
                indent = buf.get_leading_whitespace(cur.y - 1)

                # Python-specific: add extra indent if previous line ends with ':'
                # We split on '#' to ignore inline comments (e.g., `def foo(): #hi`)
                if buf.filename and buf.filename.endswith(".py"):
                    prev_line_code = buf.lines[cur.y - 1].split('#')[0].rstrip()
                    if prev_line_code.endswith(':'):
                        indent += " " * self.config.tab_size

                buf.lines[cur.y] = indent + buf.lines[cur.y]
                buf.touch()
                cur.x = len(indent)
            else:
                cur.x = 0
        elif 32 <= key <= 126:
            self._pre_edit()
            buf.insert_char(cur.x, cur.y, chr(key))
            cur.x += 1

    def _page(self, direction, screen_rows, screen_cols):
        text_cols = max(1, screen_cols - self._gutter_width())
        if self.config.soft_wrap:
            _, vy = get_visual_position(
                self.cursor.x, self.cursor.y, self.buffer.lines,
                text_cols, True)
            target = max(0, vy + direction * screen_rows)
            y = get_logical_from_visual(target, self.buffer.lines,
                                        text_cols, True)
        else:
            y = self.cursor.y + direction * screen_rows
        self.cursor.set_pos(self.cursor.x, y,
                            self.buffer.get_line_length, self.buffer.max_y)

    # ── Undo / Redo ───────────────────────────────────────────

    def _do_undo(self):
        result = self.history.undo(self.buffer.lines,
                                   self.cursor.x, self.cursor.y)
        if result:
            lines, x, y = result
            self.buffer.lines = lines
            self.buffer.touch()
            self.last_match = None
            self.cursor.set_pos(x, y, self.buffer.get_line_length,
                                self.buffer.max_y)
            self.message = "Undo."
        else:
            self.message = "Nothing to undo."

    def _do_redo(self):
        result = self.history.redo(self.buffer.lines,
                                   self.cursor.x, self.cursor.y)
        if result:
            lines, x, y = result
            self.buffer.lines = lines
            self.buffer.touch()
            self.last_match = None
            self.cursor.set_pos(x, y, self.buffer.get_line_length,
                                self.buffer.max_y)
            self.message = "Redo."
        else:
            self.message = "Nothing to redo."

    def _exit_prompt_mode(self):
        self.prompt.deactivate()
        self.mode = Mode.NORMAL
        self.pending_exit = False

    # ── input reading ─────────────────────────────────────────

    def _read_key(self, stdscr):
        # curses can otherwise wait a full second before returning bare Esc.
        # Keep the shorter sequence timeout local to HELP and preserve the
        # terminal's configured delay for editing and prompts (Python 3.9+).
        get_delay = getattr(curses, "get_escdelay", None)
        set_delay = getattr(curses, "set_escdelay", None)
        previous_delay = None
        if self.mode == Mode.HELP and get_delay and set_delay:
            previous_delay = get_delay()
            set_delay(min(previous_delay, HELP_ESCAPE_DELAY_MS))
        try:
            key = stdscr.getch()
        finally:
            if previous_delay is not None:
                set_delay(previous_delay)

        if key in CONHOST_ALT_MAP:
            return alt(CONHOST_ALT_MAP[key])

        if key > 255:
            mapped = self._keyname_alt(key)
            if mapped is not None:
                return mapped

        if key == 27:
            if self.mode == Mode.HELP:
                stdscr.timeout(HELP_ESCAPE_DELAY_MS)
            else:
                curses.halfdelay(2)
            try:
                nxt = stdscr.getch()
            finally:
                if self.mode == Mode.HELP:
                    stdscr.timeout(-1)
                else:
                    curses.cbreak()
            if nxt == -1:
                return 27
            if nxt == ord('['):
                return self._read_csi(stdscr)
            return alt(nxt) if 0 <= nxt <= 255 else 27

        if 128 <= key <= 255:
            base = key - 128
            if chr(base) in ALT_BASES:
                return alt(base)
            return key

        return key

    def _keyname_alt(self, key):
        try:
            name = curses.keyname(key)
        except Exception:
            return None
        if name and name.startswith(b"ALT_") and len(name) == 5:
            return alt(name[4])
        return None

    def _read_csi(self, stdscr):
        seq = []
        stdscr.nodelay(True)
        try:
            while True:
                ch = stdscr.getch()
                if ch == -1:
                    break
                seq.append(ch)
                if 0x40 <= ch <= 0x7E:
                    break
        finally:
            stdscr.nodelay(False)
        code = "".join(chr(c) for c in seq)

        if code == "Z":
            return Key.SHIFT_TAB
        if code.endswith("D") and (";5" in code or code == "5D"):
            return Key.CTRL_LEFT
        if code.endswith("C") and (";5" in code or code == "5C"):
            return Key.CTRL_RIGHT
        return -1

    # ── Main loop ─────────────────────────────────────────────

    def main_loop(self, stdscr):
        _ignore_suspend()
        self.renderer = Renderer(stdscr, self.config)
        self._set_mouse(self.config.mouse)

        while self.running:
            screen_rows, screen_cols = self.renderer.get_dimensions()
            sel = None
            if self.mode == Mode.HELP:
                view = HelpView(self.help_scroll_y)
                view.move(None, screen_rows, screen_cols)
                self.help_scroll_y = view.offset
            else:
                text_cols = max(1, screen_cols - self._gutter_width())

                vx, vy = get_visual_position(
                    self.cursor.x, self.cursor.y, self.buffer.lines,
                    text_cols, self.config.soft_wrap)
                self.cursor.update_scroll(
                    vy, vx, screen_rows, text_cols,
                    self.config.smooth_scroll_margin, self.config.soft_wrap)

                if self.selection.active:
                    bounds = self._current_bounds()
                    if not self.selection.is_empty(bounds):
                        sel = bounds

            self.renderer.render(
                self.buffer, self.cursor, message=self.message,
                prompt=self.prompt, mode=self.mode,
                selection=sel, mark_set=self.selection.active,
                match=self.last_match,
                all_matches=getattr(self, "all_matches", None),
                keybindings=KEYBINDINGS if self.mode == Mode.HELP else None,
                doc_index=self.current, 
                doc_count=len(self.documents),
                help_scroll_y=getattr(self, "help_scroll_y", 0),
            )

            try:
                key = self._read_key(stdscr)
            except KeyboardInterrupt:
                if self.mode == Mode.HELP:
                    continue
                self.running = False
                break

            if key == Key.RESIZE:
                if self.config.mouse:
                    self._set_mouse(True)
                continue
            if key == curses.KEY_MOUSE:
                self._handle_mouse(stdscr)
                continue
            if key < 0:
                continue

            self.handle_input(key, screen_rows, screen_cols)

    def run(self):
        try:
            curses.wrapper(self.main_loop)
        except Exception as e:
            print(f"Femto crashed: {e}")

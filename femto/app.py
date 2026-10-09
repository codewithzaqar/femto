"""
Main application loop and input routing for Femto.
"""

import curses
import os
import sys
import time
from enum import Enum, auto

from femto.clipboard import Clipboard, Selection
from femto.config import Config
from femto.documents import Document
from femto.keys import Key, is_backspace, is_enter
from femto.help import KEYBINDINGS, HelpView
from femto.prompt import Prompt
from femto.renderer import Renderer
from femto.search import SearchOptions, find_next, find_all
from femto.swap import write_swap, read_swap, delete_swap
from femto.session import save_session, load_session
from femto.sysclip import copy_to_system, paste_from_system
from femto.layout import get_logical_from_visual_point
from femto.gitgutter import get_git_diff_markers


class Mode(Enum):
    NORMAL = auto()
    SEARCH = auto()
    REPLACE_SEARCH = auto()
    REPLACE_WITH = auto()
    SAVE_AS = auto()
    GOTO_LINE = auto()
    EXIT_CONFIRM = auto()
    REPLACE_CONFIRM = auto()
    HELP = auto()


class Application:
    def __init__(self, stdscr=None, initial_files=None):
        self.stdscr = stdscr
        self.config = Config()
        self.documents = []
        self.current = 0
        self.clipboard = Clipboard()
        self.selection = Selection()
        self.prompt = Prompt()
        self.message = ""
        self.mode = Mode.NORMAL
        self.running = True
        self.last_match = None
        self.all_matches = []
        self.search_options = SearchOptions()
        self.pre_search_cursor = (0, 0)
        self.help_view = HelpView()
        self._help_scroll_y = 0
        self.last_swap_time = time.time()
        self._replace_term = ""
        self.renderer = Renderer(stdscr, self.config) if stdscr else None
        self.git_markers = {}
        self.last_git_check = 0

        if initial_files:
            for f in initial_files:
                self.open_file(f)
        if not self.documents:
            self.new_buffer()

    # ── properties ───────────────────────────────────────────
    @property
    def document(self): return self.documents[self.current]
    @property
    def buffer(self): return self.document.buffer
    @property
    def cursor(self): return self.document.cursor
    @property
    def history(self): return self.document.history
    @property
    def help_scroll_y(self): return self._help_scroll_y
    @help_scroll_y.setter
    def help_scroll_y(self, v): self._help_scroll_y = v

    def _do_undo(self): return self._undo()
    def _do_redo(self): return self._redo()
    def _snapshot(self):
        self.history.push(self.buffer.lines[:], self.cursor.x, self.cursor.y)
        self.buffer.touch()

    def new_buffer(self):
        self.documents.append(Document(self.config))
        self.current = len(self.documents) - 1

    def open_file(self, filepath):
        self.documents.append(Document(self.config, filepath))
        self.current = len(self.documents) - 1

    def _get_text_cols(self):
        if self.renderer is None:
            return 80
        _, width = self.renderer.get_dimensions()
        gutter = (len(str(len(self.buffer.lines))) + 1
                  if self.config.show_line_numbers else 0)
        return max(1, width - gutter)

    # ── bulletproof key reading ───────────────────────────────
    def _read_key(self):
        """Handles get_wch/getch differences, Alt escapes, backspace variants."""
        try:
            key = self.stdscr.get_wch()
        except curses.error:
            return -1
        except AttributeError:
            key = self.stdscr.getch()

        # Mouse events pass through untouched, immediately
        if isinstance(key, int) and key == curses.KEY_MOUSE:
            return key

        # Backspace: normalize all variants
        if key in (8, 127, '\x7f', '\x08'):
            return curses.KEY_BACKSPACE

        if key == '\t' or key == 9:
            return getattr(Key, 'TAB', 9)

        # Alt keys via escape strings (get_wch): legacy aliases
        if isinstance(key, str) and len(key) >= 2 and key[0] == '\x1b':
            char = key[1]
            mapping = {
                'd': getattr(Key, 'ALT_D', None), 'D': getattr(Key, 'ALT_D', None),
                't': getattr(Key, 'ALT_T', None), 'T': getattr(Key, 'ALT_T', None),
                's': getattr(Key, 'ALT_S', None), 'S': getattr(Key, 'ALT_SHIFT_S', None),
                'u': getattr(Key, 'ALT_U', None), 'U': getattr(Key, 'ALT_U', None),
                'l': getattr(Key, 'ALT_L', None), 'L': getattr(Key, 'ALT_L', None),
            }
            mapped = mapping.get(char)
            if mapped is not None:
                return mapped
            return key

        # Alt keys via raw ESC (27) + char (getch style): legacy aliases
        if isinstance(key, int) and key == 27:
            self.stdscr.nodelay(True)
            try:
                k2 = self.stdscr.getch()
                if k2 != -1:
                    mapping = {
                        ord('d'): getattr(Key, 'ALT_D', None), ord('D'): getattr(Key, 'ALT_D', None),
                        ord('t'): getattr(Key, 'ALT_T', None), ord('T'): getattr(Key, 'ALT_T', None),
                        ord('s'): getattr(Key, 'ALT_S', None), ord('S'): getattr(Key, 'ALT_SHIFT_S', None),
                        ord('u'): getattr(Key, 'ALT_U', None), ord('U'): getattr(Key, 'ALT_U', None),
                        ord('l'): getattr(Key, 'ALT_L', None), ord('L'): getattr(Key, 'ALT_L', None),
                    }
                    mapped = mapping.get(k2)
                    if mapped is not None:
                        return mapped
                    return f'\x1b{chr(k2)}' if 0 <= k2 < 256 else 27
            finally:
                self.stdscr.nodelay(False)
                self.stdscr.timeout(1000)
            return 27

        return key

    # ── main loop / render ────────────────────────────────────
    def main_loop(self):
        if self.config.mouse and self.stdscr:
            try:
                curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
            except curses.error:
                pass
        self.stdscr.timeout(1000)
        while self.running:
            self.render()
            key = self._read_key()
            if key == -1:
                self._tick_autosave()
                continue
            rows, cols = self.renderer.get_dimensions()
            self.handle_input(key, rows, cols)

            gutter = (len(str(len(self.buffer.lines))) + 1
                      if self.config.show_line_numbers else 0)
            self.cursor.update_scroll(self.cursor.y, self.cursor.x,
                                      rows, max(1, cols - gutter), 3,
                                      self.config.soft_wrap)

    def render(self):
        self._refresh_git_markers()  # <-- ADD THIS LINE
        
        sel = (self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y)
               if self.selection.active else None)
        self.renderer.render(
            self.buffer, self.cursor, message=self.message,
            prompt=self.prompt, mode=self.mode.name.lower(),
            selection=sel, mark_set=self.selection.active,
            match=self.last_match, all_matches=self.all_matches,
            keybindings=KEYBINDINGS if self.mode == Mode.HELP else None,
            doc_index=self.current, doc_count=len(self.documents),
            help_scroll_y=self.help_scroll_y,
            git_markers=self.git_markers  # <-- ADD THIS PARAMETER
        )

    def _tick_autosave(self):
        if self.config.autosave_seconds > 0 and \
                time.time() - self.last_swap_time >= self.config.autosave_seconds:
            for doc in self.documents:
                if doc.buffer.modified and doc.buffer.filename:
                    write_swap(doc.buffer.filename, doc.buffer.lines,
                               doc.cursor.x, doc.cursor.y)
            self.last_swap_time = time.time()

    # ── routing ───────────────────────────────────────────────
    def handle_input(self, key, screen_rows=24, screen_cols=80):
        if self.mode == Mode.NORMAL:
            self._handle_normal(key, screen_rows, screen_cols)
        elif self.mode == Mode.HELP:
            self._handle_help(key, screen_rows, screen_cols)
        elif self.mode in (Mode.SEARCH, Mode.REPLACE_SEARCH,
                           Mode.REPLACE_WITH, Mode.SAVE_AS, Mode.GOTO_LINE):
            self._handle_prompt(key, screen_rows, screen_cols)
        elif self.mode == Mode.EXIT_CONFIRM:
            self._handle_exit_confirm(key)
        else:
            self.mode = Mode.NORMAL

    # ── normal mode ───────────────────────────────────────────
    def _handle_normal(self, key, screen_rows=24, screen_cols=80):
        self.message = ""

        if isinstance(key, int) and key == curses.KEY_MOUSE:
            self._handle_mouse()
            return

        # Alt line-ops (legacy aliases; tests use these)
        if key in (getattr(Key, 'ALT_D', None), getattr(Key, 'ALT_T', None),
                   getattr(Key, 'ALT_S', None), getattr(Key, 'ALT_SHIFT_S', None),
                   getattr(Key, 'ALT_U', None), getattr(Key, 'ALT_L', None)):
            self._line_operation(key)
            return

        k = key
        if isinstance(key, str) and len(key) == 1:
            k = ord(key)

        # Enter (must precede Ctrl block)
        if is_enter(key) or k in (10, 13, 343, 344):
            self._pre_edit()
            self.buffer.insert_newline(self.cursor.x, self.cursor.y)
            self.cursor.y += 1
            if self.config.auto_indent:
                indent = self.buffer.get_leading_whitespace(self.cursor.y - 1)
                if self.buffer.filename and self.buffer.filename.endswith('.py'):
                    code = self.buffer.lines[self.cursor.y - 1].split('#')[0].rstrip()
                    if code.endswith(':'):
                        indent += " " * self.buffer.config.tab_size
                self.buffer.lines[self.cursor.y] = indent + self.buffer.lines[self.cursor.y]
                self.buffer.touch()
                self.cursor.x = len(indent)
            else:
                self.cursor.x = 0
            return

        # Ctrl keys (8=Backspace, 9=Tab, 10/13=Enter excluded)
        if isinstance(k, int) and 1 <= k <= 28 and k not in (8, 9, 10, 13):
            if k == 24: self._quit()                      # ^X exit
            elif k == 19: self._save()                    # ^S save
            elif k == 23: self._search()                  # ^W find
            elif k == 11: self._cut()                     # ^K cut
            elif k == 16: self._copy()                    # ^P copy (nano alias)
            elif k == 3: self._copy()                     # ^C copy (universal)
            elif k == 21: self._paste()                   # ^U paste (nano alias)
            elif k == 22: self._paste()                   # ^V paste (universal)
            elif k == 26: self._undo()                    # ^Z undo
            elif k == 25: self._redo()                    # ^Y redo
            elif k == 6: self._switch_buffer(True)        # ^F next buffer
            elif k == 12: self._switch_buffer(False)      # ^L prev buffer
            elif k == 14: self.config.show_line_numbers = not self.config.show_line_numbers  # ^N
            elif k == 17:                                 # ^Q mouse toggle
                self.config.mouse = not self.config.mouse
                if self.stdscr:
                    try:
                        if self.config.mouse:
                            curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
                        else:
                            curses.mousemask(0)
                    except curses.error:
                        pass
            elif k == 20: self._goto_line()               # ^T goto line
            elif k == 28: self._replace()                 # ^\ replace
            elif k == 2: self.selection.toggle(self.cursor.x, self.cursor.y)  # ^B mark
            # ── Ctrl line-operations ──
            elif k == 4: self._line_operation(getattr(Key, 'ALT_D', None))          # ^D duplicate
            elif k == 5: self._line_operation(getattr(Key, 'ALT_T', None))          # ^E transpose
            elif k == 15: self._line_operation(getattr(Key, 'ALT_S', None))         # ^O sort
            elif k == 18: self._line_operation(getattr(Key, 'ALT_SHIFT_S', None))   # ^R sort ignore-case
            elif k == 1: self._line_operation(getattr(Key, 'ALT_U', None))          # ^A uppercase
            elif k == 7: self._line_operation(getattr(Key, 'ALT_L', None))          # ^G lowercase
            return

        # Printable characters
        ch = None
        if isinstance(key, str) and len(key) == 1 and ord(key) > 31:
            ch = key
        elif isinstance(key, int) and 32 <= key <= 126:
            ch = chr(key)
        if ch is not None:
            self._pre_edit()
            self.buffer.insert_char(self.cursor.x, self.cursor.y, ch)
            self.cursor.x += 1
            return

        # Special keys
        if isinstance(key, int):
            sw, tc = self.config.soft_wrap, self._get_text_cols()
            if key == curses.KEY_UP: self.cursor.move_up(self.buffer, sw, tc)
            elif key == curses.KEY_DOWN: self.cursor.move_down(self.buffer, sw, tc)
            elif key == curses.KEY_LEFT: self.cursor.move_left(self.buffer)
            elif key == curses.KEY_RIGHT: self.cursor.move_right(self.buffer)
            elif key == curses.KEY_HOME: self.cursor.x = 0
            elif key == curses.KEY_END: self.cursor.x = self.buffer.get_line_length(self.cursor.y)
            elif key == curses.KEY_PPAGE: self.cursor.page_up(self.buffer, screen_rows)
            elif key == curses.KEY_NPAGE: self.cursor.page_down(self.buffer, screen_rows)
            elif key == curses.KEY_F1: self._enter_help()
            elif is_backspace(key) or key == curses.KEY_BACKSPACE:
                self._pre_edit()
                self.cursor.x, self.cursor.y = self.buffer.backspace(self.cursor.x, self.cursor.y)
            elif key == curses.KEY_DC:
                self._pre_edit()
                self.buffer.delete_char(self.cursor.x, self.cursor.y)
            elif key == Key.TAB:
                self._pre_edit()
                self.cursor.x = self.buffer.insert_tab(self.cursor.y, self.cursor.x)
            elif key == curses.KEY_BTAB:
                self._pre_edit()
                self.cursor.x = self.buffer.remove_tab(self.cursor.y, self.cursor.x)

    def _pre_edit(self):
        if self.selection.active:
            bounds = self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y)
            self.cursor.x, self.cursor.y = self.selection.delete_range(self.buffer, bounds)
            self.selection.clear()
        self.history.push(self.buffer.lines[:], self.cursor.x, self.cursor.y)

    def _line_operation(self, key):
        if key == getattr(Key, 'ALT_D', None):
            self._snapshot()
            if self.selection.active:
                bounds = self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y)
                (sx, sy), (ex, ey) = bounds
                if (sx, sy) != (ex, ey) and sy == ey:
                    text = self.selection.extract(self.buffer, bounds)
                    line = self.buffer.lines[sy]
                    self.buffer.lines[sy] = line[:ex] + text + line[ex:]
                    self.cursor.x = ex + len(text)
                    self.message = "Duplicated selection."
                else:
                    self.buffer.duplicate_line(self.cursor.y)
                    self.cursor.y += 1
                    self.message = "Duplicated line."
            else:
                self.buffer.duplicate_line(self.cursor.y)
                self.cursor.y += 1
                self.message = "Duplicated line."
            self.buffer.touch()
            return
        if key == getattr(Key, 'ALT_T', None):
            if self.cursor.y > 0:
                self._snapshot()
                self.buffer.transpose_line(self.cursor.y)
                self.cursor.y -= 1
                self.message = "Transposed line."
                self.buffer.touch()
            return
        if key in (getattr(Key, 'ALT_S', None), getattr(Key, 'ALT_SHIFT_S', None)):
            if not self.selection.active:
                self.message = "No selection to sort."
                return
            self._snapshot()
            (sx, sy), (ex, ey) = self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y)
            if (sx, sy) == (ex, ey):
                lo, hi = 0, len(self.buffer.lines) - 1
            else:
                lo, hi = min(sy, ey), max(sy, ey)
            case_sens = (key == getattr(Key, 'ALT_S', None))
            seg = self.buffer.lines[lo:hi + 1]
            keyf = (lambda s: s) if case_sens else (lambda s: s.lower())
            self.buffer.lines[lo:hi + 1] = sorted(seg, key=keyf)
            self.buffer.touch()
            self.selection.clear()
            self.message = f"Sorted {hi - lo + 1} lines."
            return
        if key in (getattr(Key, 'ALT_U', None), getattr(Key, 'ALT_L', None)):
            if not self.selection.active:
                self.message = "No selection."
                return
            self._snapshot()
            bounds = self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y)
            is_upper = (key == getattr(Key, 'ALT_U', None))
            self.buffer.transform_case(bounds, upper=is_upper)
            self.buffer.touch()
            self.message = "Uppercase." if is_upper else "Lowercase."
            return

    # ── prompts ─────────────────────────────────────────────
    def _handle_prompt(self, key, screen_rows=24, screen_cols=80):
        if self.mode == Mode.SAVE_AS and key == Key.TAB:
            self._complete_path()
            return

        k = key
        if isinstance(key, str) and len(key) == 1:
            k = ord(key)

        if is_enter(key) or k in (10, 13, 343, 344):
            self._commit_prompt()
            return
        if k in (7, 27):  # ^G or Esc = cancel (prompt context only)
            self._cancel_prompt()
            return
        if k == 15:  # ^O case toggle (prompt context only)
            self.search_options.ignore_case = not self.search_options.ignore_case
            self._refresh_prompt_flags()
            return
        if k == 18:  # ^R regex toggle (prompt context only)
            self.search_options.regex = not self.search_options.regex
            self._refresh_prompt_flags()
            return
        if is_backspace(key) or k in (8, 127) or key == curses.KEY_BACKSPACE:
            self.prompt.backspace()
            self._prompt_changed()
            return
        if isinstance(key, int) and key == curses.KEY_DC:
            self.prompt.delete()
            self._prompt_changed()
            return
        if isinstance(key, int):
            if key == curses.KEY_LEFT: self.prompt.move(-1); return
            if key == curses.KEY_RIGHT: self.prompt.move(1); return
            if key == curses.KEY_HOME: self.prompt.home(); return
            if key == curses.KEY_END: self.prompt.end(); return

        ch = None
        if isinstance(key, str) and len(key) == 1 and ord(key) > 31:
            ch = key
        elif isinstance(key, int) and 32 <= key <= 126:
            ch = chr(key)
        if ch is not None:
            self.prompt.insert(ch)
            self._prompt_changed()
            return

    def _refresh_git_markers(self):
        """Refresh git diff markers if enough time has passed (1s debounce)."""
        if not self.config.git_gutter:
            return
        
        now = time.time()
        if now - self.last_git_check < 1.0:
            return
        
        if self.buffer.filename and os.path.exists(self.buffer.filename):
            self.git_markers = get_git_diff_markers(self.buffer.filename)
            self.last_git_check = now
        else:
            self.git_markers = {}

    def _refresh_prompt_flags(self):
        base = self.prompt.label.split(" [")[0]
        self.prompt.label = base + self.search_options.flag_label()
        self.message = ("case=" +
                        ("insensitive" if self.search_options.ignore_case else "sensitive") +
                        ", regex=" + ("on" if self.search_options.regex else "off"))

    def _prompt_changed(self):
        if self.mode == Mode.SEARCH:
            self._live_search_update()

    def _search(self):
        self.mode = Mode.SEARCH
        self.pre_search_cursor = (self.cursor.x, self.cursor.y)
        self._last_search = getattr(self, "_last_search", "")
        self.prompt.start("Search" + self.search_options.flag_label(), "")
        self.prompt.text = self._last_search
        self.prompt.cursor_pos = len(self.prompt.text)
        if self.prompt.text:
            self._live_search_update()

    def _live_search_update(self):
        """Re-highlight matches live while typing in the Search prompt."""
        term = self.prompt.text
        if not term:
            self.all_matches, self.last_match = [], None
            return
        try:
            self.all_matches = find_all(self.buffer, term, self.search_options)
        except Exception:
            self.message = "[bad regex]"
            self.all_matches = []
            return
        self.last_match = None
        for mx, my, ml in self.all_matches:
            if (my, mx) >= (self.pre_search_cursor[1], self.pre_search_cursor[0]):
                self.last_match = (mx, my, ml)
                self.cursor.set_pos(mx, my, self.buffer.get_line_length,
                                    self.buffer.max_y)
                break

    def _replace(self):
        self.mode = Mode.REPLACE_SEARCH
        self.prompt.start("Replace" + self.search_options.flag_label(), "")

    def _goto_line(self):
        self.mode = Mode.GOTO_LINE
        self.prompt.start("Go To Line", "")

    def _complete_path(self):
        text = self.prompt.text
        dirname = os.path.dirname(text)
        basename = os.path.basename(text)
        search_dir = dirname if dirname else '.'
        try:
            candidates = [f for f in os.listdir(search_dir)
                          if f.startswith(basename)
                          and (not f.startswith('.') or basename.startswith('.'))]
        except OSError:
            return
        if not candidates:
            return
        if len(candidates) == 1:
            match = candidates[0]
            new_text = os.path.join(dirname, match) if dirname else match
            if os.path.isdir(os.path.join(search_dir, match)):
                new_text += os.sep
            self.prompt.text = new_text
            self.prompt.cursor_pos = len(self.prompt.text)
            self.message = ""
        else:
            prefix = os.path.commonprefix(candidates)
            if len(prefix) > len(basename):
                self.prompt.text = os.path.join(dirname, prefix) if dirname else prefix
                self.prompt.cursor_pos = len(self.prompt.text)
            self.message = "  ".join(candidates[:5])

    def _commit_prompt(self):
        text = self.prompt.text
        if self.mode == Mode.SEARCH:
            if text:
                self._last_search = text
            hit = find_next(self.buffer, text, self.search_options,
                            self.cursor.x, self.cursor.y)
            if hit:
                self.last_match = hit
                self.cursor.set_pos(hit[0], hit[1], self.buffer.get_line_length, self.buffer.max_y)
                try:
                    self.all_matches = find_all(self.buffer, text, self.search_options)
                except Exception:
                    self.all_matches = []
            else:
                self.message = f"Not found: {text}"
        elif self.mode == Mode.REPLACE_SEARCH:
            self._replace_term = text
            self.mode = Mode.REPLACE_WITH
            self.prompt.start("With", "")
            return
        elif self.mode == Mode.REPLACE_WITH:
            self._snapshot()
            count = 0
            term = self._replace_term
            for i, line in enumerate(self.buffer.lines):
                if term and term in line:
                    count += line.count(term)
                    self.buffer.lines[i] = line.replace(term, text)
            self.buffer.touch()
            self.message = f"Replaced {count} occurrence(s)"
        elif self.mode == Mode.SAVE_AS:
            self.buffer.filename = text
            self._save()
        elif self.mode == Mode.GOTO_LINE:
            try:
                line = int(text) - 1
                self.cursor.set_pos(0, max(0, min(line, self.buffer.max_y)),
                                    self.buffer.get_line_length, self.buffer.max_y)
            except ValueError:
                self.message = "Invalid line number"
        self.mode = Mode.NORMAL
        self.prompt.clear()

    def _cancel_prompt(self):
        if self.mode == Mode.SEARCH:
            self.cursor.set_pos(self.pre_search_cursor[0], self.pre_search_cursor[1],
                                self.buffer.get_line_length, self.buffer.max_y)
            self.all_matches, self.last_match = [], None
        self.mode = Mode.NORMAL
        self.prompt.clear()

    # ── help ──────────────────────────────────────────────────
    def _enter_help(self):
        self.mode = Mode.HELP
        self.help_view.reset()
        self.help_scroll_y = 0

    def _handle_help(self, key, screen_rows=24, screen_cols=80):
        kk = ord(key) if (isinstance(key, str) and len(key) == 1) else key
        if kk == 27 or kk == ord('q') or kk == ord('Q'):
            self.mode = Mode.NORMAL
        elif key == curses.KEY_UP:
            self.help_scroll_y = self.help_view.move("up", screen_rows, screen_cols)
        elif key == curses.KEY_DOWN:
            self.help_scroll_y = self.help_view.move("down", screen_rows, screen_cols)
        elif key == curses.KEY_PPAGE:
            self.help_scroll_y = self.help_view.move("page_up", screen_rows, screen_cols)
        elif key == curses.KEY_NPAGE:
            self.help_scroll_y = self.help_view.move("page_down", screen_rows, screen_cols)

    # ── file & exit ───────────────────────────────────────────
    def _save(self):
        if not self.buffer.filename:
            self.mode = Mode.SAVE_AS
            self.prompt.start("Save As", "")
            return
        if self.buffer.save():
            delete_swap(self.buffer.filename)
            self.message = f"Saved {self.buffer.filename}"
        else:
            self.message = f"Error saving {self.buffer.filename}"

    def _quit(self):
        if any(d.buffer.modified for d in self.documents):
            self.mode = Mode.EXIT_CONFIRM
            self.message = "Unsaved changes! Quit anyway?"
        else:
            self._do_exit()

    def _handle_exit_confirm(self, key):
        kk = ord(key) if (isinstance(key, str) and len(key) == 1) else key
        if kk in (ord('y'), ord('Y')):
            self._do_exit()
        else:
            self.mode = Mode.NORMAL
            self.message = ""

    def _do_exit(self):
        if self.config.restore_session:
            save_session(self.documents, self.current)
        self.running = False

    # ── clipboard & history ───────────────────────────────────
    def _cut(self):
        text = None
        if self.selection.active:
            bounds = self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y)
            (sx, sy), (ex, ey) = bounds
            if (sx, sy) != (ex, ey):
                text = self.selection.extract(self.buffer, bounds)
                self.history.push(self.buffer.lines[:], self.cursor.x, self.cursor.y)
                self.cursor.x, self.cursor.y = self.selection.delete_range(self.buffer, bounds)
                self.selection.clear()
        if text is None:
            self.selection.clear()
            self.history.push(self.buffer.lines[:], self.cursor.x, self.cursor.y)
            text = self.buffer.lines[self.cursor.y] + "\n"
            del self.buffer.lines[self.cursor.y]
            if not self.buffer.lines:
                self.buffer.lines = [""]
            if self.cursor.y >= len(self.buffer.lines):
                self.cursor.y -= 1
            self.cursor.x = 0
        self.buffer.touch()
        self.clipboard.store(text)
        if self.config.system_clipboard:
            copy_to_system(text)
        self.message = "Cut"

    def _copy(self):
        if self.selection.active:
            bounds = self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y)
            text = self.selection.extract(self.buffer, bounds)
        else:
            text = self.buffer.lines[self.cursor.y]
        self.clipboard.store(text)
        if self.config.system_clipboard:
            copy_to_system(text)
        self.message = "Copied"

    def _paste(self):
        text = self.clipboard.text
        if not text and self.config.system_clipboard:
            text = paste_from_system()
            if text:
                self.clipboard.store(text)
        if not text:
            return
        self._pre_edit()
        self.cursor.x, self.cursor.y = self.clipboard.paste_into(
            self.buffer, self.cursor.x, self.cursor.y)

    def _undo(self):
        if self.history.can_undo:
            lines, x, y = self.history.undo(self.buffer.lines, self.cursor.x, self.cursor.y)
            self.buffer.lines = lines
            self.cursor.set_pos(x, y, self.buffer.get_line_length, self.buffer.max_y)
            self.buffer.touch()

    def _redo(self):
        if self.history.can_redo:
            lines, x, y = self.history.redo(self.buffer.lines, self.cursor.x, self.cursor.y)
            self.buffer.lines = lines
            self.cursor.set_pos(x, y, self.buffer.get_line_length, self.buffer.max_y)
            self.buffer.touch()

    def _switch_buffer(self, nxt=True):
        if len(self.documents) <= 1:
            return
        self.current = ((self.current + 1) if nxt else (self.current - 1)) % len(self.documents)

    def _handle_mouse(self):
        try:
            _, mx, my, _, bstate = curses.getmouse()
        except curses.error:
            return

        # ── Mouse wheel: scroll 3 lines per notch ──
        if bstate & getattr(curses, 'BUTTON4_PRESSED', 0):
            self._wheel(-3)   # wheel up
            return
        if bstate & getattr(curses, 'BUTTON5_PRESSED', 0):
            self._wheel(3)    # wheel down
            return

        if bstate & (curses.BUTTON1_CLICKED | curses.BUTTON1_PRESSED |
                     getattr(curses, 'BUTTON1_DOUBLE_CLICKED', 0)):
            gutter = (len(str(len(self.buffer.lines))) + 1
                      if self.config.show_line_numbers else 0)
            text_cols = self._get_text_cols()
            vis_y = my + self.cursor.scroll_y
            vis_x = max(0, mx - gutter)
            if self.config.soft_wrap:
                x, y = get_logical_from_visual_point(
                    vis_y, vis_x, self.buffer.lines, text_cols)
                self.cursor.set_pos(x, y, self.buffer.get_line_length, self.buffer.max_y)
            else:
                x = vis_x + self.cursor.scroll_x
                self.cursor.set_pos(x, vis_y, self.buffer.get_line_length, self.buffer.max_y)

    def _wheel(self, dy):
        """Scroll by moving the cursor |dy| lines; update_scroll follows."""
        steps = abs(dy)
        for _ in range(steps):
            if dy < 0:
                self.cursor.move_up(self.buffer, self.config.soft_wrap,
                                    self._get_text_cols())
            else:
                self.cursor.move_down(self.buffer, self.config.soft_wrap,
                                      self._get_text_cols())

# ── entry point ───────────────────────────────────────────────
def main():
    cfg = Config()
    cli_files = [a for a in sys.argv[1:] if not a.startswith('-')]

    recovered = {}
    for fp in cli_files:
        data = read_swap(fp)
        if data:
            print(f"\n[Femto] Swap file found for {fp}.")
            choice = input("Recover unsaved changes? (y/n): ").strip().lower()
            if choice == 'y':
                recovered[fp] = data
            else:
                delete_swap(fp)

    if not cli_files and cfg.restore_session:
        sess = load_session()
        if sess and sess.get('buffers'):
            cli_files = [b['filename'] for b in sess['buffers']
                         if b.get('filename') and os.path.exists(b['filename'])]

    def run(stdscr):
        try:
            stdscr.keypad(True)          # required for KEY_MOUSE delivery
        except curses.error:
            pass
        try:
            stdscr.raw()
        except curses.error:
            pass
        if cfg.mouse:
            try:
                curses.mousemask(curses.ALL_MOUSE_EVENTS | curses.REPORT_MOUSE_POSITION)
            except curses.error:
                pass
        app = Application(stdscr, initial_files=cli_files)
        for doc in app.documents:
            fp = doc.buffer.filename
            if fp and fp in recovered:
                d = recovered[fp]
                doc.buffer.lines = list(d.get('lines', ['']))
                doc.cursor.set_pos(d.get('x', 0), d.get('y', 0),
                                   doc.buffer.get_line_length, doc.buffer.max_y)
                doc.buffer.touch()
                delete_swap(fp)
        app.main_loop()

    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

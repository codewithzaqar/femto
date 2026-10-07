"""
Main application loop and input routing for Femto.

Integrates: multi-buffer document model, prompt modes, help screen,
auto-indent, tab completion, system clipboard bridge, and v0.0.4a01
crash recovery (swap files) and session restore.
"""

import curses
import os
import sys
import time
from enum import Enum, auto

from femto.buffer import Buffer
from femto.clipboard import Clipboard, Selection
from femto.config import Config
from femto.cursor import Cursor
from femto.documents import Document
from femto.history import History
from femto.layout import get_visual_position
from femto.prompt import Prompt
from femto.renderer import Renderer
from femto.search import SearchOptions, find_next, find_all
from femto.keys import Key, alt, is_backspace, is_enter, ALT_BASES, CONHOST_ALT_MAP
from femto.help import KEYBINDINGS, HelpView
from femto.swap import write_swap, read_swap, delete_swap
from femto.session import save_session, load_session
from femto.sysclip import copy_to_system, paste_from_system


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
        
        # Search state
        self.last_match = None
        self.all_matches = []
        self.search_options = SearchOptions()
        self.pre_search_cursor = (0, 0)
        
        # Help state
        self.help_view = HelpView()
        
        # Safety state (v0.0.4a01)
        self.last_swap_time = time.time()

        # Only initialize renderer if we have a real terminal
        if self.stdscr:
            self.renderer = Renderer(stdscr, self.config)
        else:
            self.renderer = None

        if initial_files:
            for f in initial_files:
                self.open_file(f)
        if not self.documents:
            self.new_buffer()

    @property
    def help_scroll_y(self):
        """Alias for tests that check app.help_scroll_y directly."""
        return getattr(self, '_help_scroll_y', 0)

    @help_scroll_y.setter
    def help_scroll_y(self, value):
        self._help_scroll_y = value

    def _do_undo(self):
        """Alias for PR #29 highlight tests."""
        return self._undo()

    def _do_redo(self):
        """Alias for PR #29 highlight tests."""
        return self._redo()

    def _snapshot(self):
        """Alias for PR #29 highlight tests. Must bump revision to invalidate highlight cache."""
        self.history.push(self.buffer.lines[:], self.cursor.x, self.cursor.y)
        self.buffer.touch()

    # ── Buffer Management ─────────────────────────────────────

    def new_buffer(self):
        doc = Document(self.config)
        self.documents.append(doc)
        self.current = len(self.documents) - 1

    def open_file(self, filepath):
        doc = Document(self.config, filepath)
        self.documents.append(doc)
        self.current = len(self.documents) - 1

    @property
    def document(self): return self.documents[self.current]
    @property
    def buffer(self): return self.document.buffer
    @property
    def cursor(self): return self.document.cursor
    @property
    def history(self): return self.document.history

    def _get_text_cols(self):
        if self.renderer is None:
            return 80  # Fallback for headless tests
        _, width = self.renderer.get_dimensions()
        gutter = (len(str(len(self.buffer.lines))) + 1) if self.config.show_line_numbers else 0
        return max(1, width - gutter)

    # ── Main Loop & Rendering ─────────────────────────────────

    def main_loop(self):
        self.stdscr.timeout(1000)  # 1s timeout allows auto-save ticking
        
        while self.running:
            self.render()
            try:
                key = self.stdscr.get_wch()
            except curses.error:
                continue

            if isinstance(key, int) and key == -1:
                self._tick_autosave()
                continue
                
            # Fetch dimensions for the real app loop and pass to handler
            screen_rows, screen_cols = self.renderer.get_dimensions()
            self.handle_input(key, screen_rows, screen_cols)

    def render(self):
        sel_bounds = self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y) if self.selection.active else None
        self.renderer.render(
            self.buffer, self.cursor, message=self.message,
            prompt=self.prompt, mode=self.mode.name.lower(),
            selection=sel_bounds, mark_set=self.selection.active,
            match=self.last_match, all_matches=self.all_matches,
            keybindings=KEYBINDINGS if self.mode == Mode.HELP else None,
            doc_index=self.current, doc_count=len(self.documents),
            help_scroll_y=self.help_view.offset
        )

    # ── Auto-save / Swap Integration (v0.0.4a01) ──────────────

    def _tick_autosave(self):
        """Called on getch() timeout to check if we need to write swap files."""
        if self.config.autosave_seconds > 0:
            if time.time() - self.last_swap_time >= self.config.autosave_seconds:
                for doc in self.documents:
                    if doc.buffer.modified and doc.buffer.filename:
                        write_swap(doc.buffer.filename, doc.buffer.lines, 
                                   doc.cursor.x, doc.cursor.y)
                self.last_swap_time = time.time()

    # ── Input Routing ─────────────────────────────────────────

    def handle_input(self, key, screen_rows=24, screen_cols=80):
        if self.mode == Mode.NORMAL:
            self._handle_normal(key, screen_rows, screen_cols)
        elif self.mode == Mode.HELP:
            self._handle_help(key, screen_rows, screen_cols)
        elif self.mode in (Mode.SEARCH, Mode.REPLACE_SEARCH, Mode.REPLACE_WITH, Mode.SAVE_AS, Mode.GOTO_LINE):
            self._handle_prompt(key)
        elif self.mode == Mode.EXIT_CONFIRM:
            self._handle_exit_confirm(key)
        elif self.mode == Mode.REPLACE_CONFIRM:
            self._handle_replace_confirm(key)

    # ── Normal Mode ───────────────────────────────────────────

    def _handle_normal(self, key, screen_rows=24, screen_cols=80):
        self.message = ""
        
        if isinstance(key, int) and key == curses.KEY_MOUSE:
            self._handle_mouse()
            return

        # BULLETPROOF ALT DISPATCH: Check the RAW key against Key constants FIRST.
        # This catches ints, strings, and escape sequences before any normalization.
        if key in (getattr(Key, 'ALT_S', None), getattr(Key, 'ALT_SHIFT_S', None),
                   getattr(Key, 'ALT_D', None), getattr(Key, 'ALT_T', None),
                   getattr(Key, 'ALT_U', None), getattr(Key, 'ALT_L', None)):
            self._line_operation(key)
            return

        k = key
        if isinstance(key, str) and len(key) == 1:
            k = ord(key)

        # 1. Handle Enter keys FIRST (10 and 13 are Ctrl+J/M, must bypass Ctrl block)
        if is_enter(key) or k in (10, 13, 343, 344):
            self._pre_edit()
            self.buffer.insert_newline(self.cursor.x, self.cursor.y)
            self.cursor.y += 1
            
            if self.config.auto_indent:
                indent = self.buffer.get_leading_whitespace(self.cursor.y - 1)
                if self.buffer.filename and self.buffer.filename.endswith('.py'):
                    prev_line_code = self.buffer.lines[self.cursor.y - 1].split('#')[0].rstrip()
                    if prev_line_code.endswith(':'):
                        indent += " " * self.config.tab_size
                self.buffer.lines[self.cursor.y] = indent + self.buffer.lines[self.cursor.y]
                self.buffer.touch()
                self.cursor.x = len(indent)
            else:
                self.cursor.x = 0
            return

        # 2. Handle Ctrl keys (1-28) EXCEPT 10 and 13
        if isinstance(k, int) and 1 <= k <= 28 and k not in (10, 13):
            if k == 24: self._quit() # ^X
            elif k == 19: self._save() # ^S
            elif k == 23: self._search() # ^W
            elif k == 11: self._cut() # ^K
            elif k == 16: self._copy() # ^P
            elif k == 21: self._paste() # ^U
            elif k == 26: self._undo() # ^Z
            elif k == 25: self._redo() # ^Y
            elif k == 6: self._switch_buffer(next=True) # ^F
            elif k == 12: self._switch_buffer(next=False) # ^L
            elif k == 14: self.config.show_line_numbers = not self.config.show_line_numbers # ^N
            elif k == 4: self.config.mouse = not self.config.mouse # ^D
            elif k == 20: self._goto_line() # ^T
            elif k == 28: self._replace() # ^\
            elif k == 2: self.selection.toggle(self.cursor.x, self.cursor.y) # ^B
            return

        # 3. Handle printable characters
        if isinstance(key, str) and len(key) == 1 and k > 31:
            self._pre_edit()
            self.buffer.insert_char(self.cursor.x, self.cursor.y, key)
            self.cursor.move_right(self.buffer)
            return

        # 4. Handle curses special keys
        if isinstance(key, int):
            if key == curses.KEY_UP: self.cursor.move_up(self.buffer, self.config.soft_wrap, self._get_text_cols())
            elif key == curses.KEY_DOWN: self.cursor.move_down(self.buffer, self.config.soft_wrap, self._get_text_cols())
            elif key == curses.KEY_LEFT: self.cursor.move_left(self.buffer)
            elif key == curses.KEY_RIGHT: self.cursor.move_right(self.buffer)
            elif key == curses.KEY_HOME: self.cursor.x = 0
            elif key == curses.KEY_END: self.cursor.x = self.buffer.get_line_length(self.cursor.y)
            elif key == curses.KEY_PPAGE: self.cursor.page_up(self.buffer, screen_rows)
            elif key == curses.KEY_NPAGE: self.cursor.page_down(self.buffer, screen_rows)
            elif key == curses.KEY_F1: self._enter_help()
            
            elif is_backspace(key):
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

    def _line_operation(self, key):
        if key == getattr(Key, 'ALT_D', None):
            self._snapshot()
            if self.selection.active:
                bounds = self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y)
                (sx, sy), (ex, ey) = bounds
                if (sx, sy) != (ex, ey):
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

        if key == getattr(Key, 'ALT_S', None) or key == getattr(Key, 'ALT_SHIFT_S', None):
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

        if key == getattr(Key, 'ALT_U', None) or key == getattr(Key, 'ALT_L', None):
            if not self.selection.active:
                self.message = "No selection."
                return
            self._snapshot()
            bounds = self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y)
            is_upper = (key == getattr(Key, 'ALT_U', None))
            self.buffer.transform_case(bounds, upper=is_upper)
            self.message = "Uppercase." if is_upper else "Lowercase."
            self.buffer.touch()
            return

    def _pre_edit(self):
        """Snapshot state before an edit for undo."""
        if self.selection.active:
            bounds = self.selection.bounds(self.buffer, self.cursor.x, self.cursor.y)
            self.selection.delete_range(self.buffer, bounds)
            self.selection.clear()
        self.history.push(self.buffer.lines[:], self.cursor.x, self.cursor.y)

    # ── Prompts (Search, Save-As, etc.) ───────────────────────

    def _handle_prompt(self, key):
        # Intercept Tab for path completion in Save-As (v0.0.3)
        if self.mode == Mode.SAVE_AS and key == Key.TAB:
            self._complete_path()
            return

        result = self.prompt.handle_key(key)
        if result == "enter":
            self._commit_prompt()
        elif result == "cancel":
            self._cancel_prompt()
        elif result == "change":
            if self.mode == Mode.SEARCH:
                self._live_search_update()

    def _search(self):
        self.mode = Mode.SEARCH
        self.prompt.start("Search", self.search_options.flag_label())
        self.pre_search_cursor = (self.cursor.x, self.cursor.y)

    def _live_search_update(self):
        term = self.prompt.text
        if not term:
            self.all_matches = []
            self.last_match = None
            return
        try:
            self.all_matches = find_all(self.buffer, term, self.search_options)
            # Move cursor to first match after original position
            for mx, my, ml in self.all_matches:
                if (my, mx) >= (self.pre_search_cursor[1], self.pre_search_cursor[0]):
                    self.last_match = (mx, my, ml)
                    self.cursor.set_pos(mx, my, self.buffer.get_line_length, self.buffer.max_y)
                    break
            else:
                self.last_match = None
        except Exception:
            self.message = "[bad regex]"
            self.all_matches = []

    def _complete_path(self):
        """Tab-completion for the Save-As prompt."""
        text = self.prompt.text
        dirname = os.path.dirname(text)
        basename = os.path.basename(text)
        search_dir = dirname if dirname else '.'
        
        try:
            candidates = [
                f for f in os.listdir(search_dir) 
                if f.startswith(basename) and (not f.startswith('.') or basename.startswith('.'))
            ]
        except OSError:
            return
            
        if not candidates: return
            
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
                new_text = os.path.join(dirname, prefix) if dirname else prefix
                self.prompt.text = new_text
                self.prompt.cursor_pos = len(self.prompt.text)
            self.message = "  ".join(candidates[:5])

    def _commit_prompt(self):
        text = self.prompt.text
        if self.mode == Mode.SEARCH:
            self.search_options = self.prompt.options
            hit = find_next(self.buffer, text, self.search_options, self.cursor.x + 1, self.cursor.y)
            if hit:
                self.last_match = hit
                self.cursor.set_pos(hit[0], hit[1], self.buffer.get_line_length, self.buffer.max_y)
            else:
                self.message = f"Not found: {text}"
            self.all_matches = find_all(self.buffer, text, self.search_options)
        elif self.mode == Mode.SAVE_AS:
            self.buffer.filename = text
            self._save()
        elif self.mode == Mode.GOTO_LINE:
            try:
                line = int(text) - 1
                self.cursor.set_pos(0, max(0, min(line, self.buffer.max_y)), self.buffer.get_line_length, self.buffer.max_y)
            except ValueError:
                self.message = "Invalid line number"
        self.mode = Mode.NORMAL
        self.prompt.clear()

    def _cancel_prompt(self):
        if self.mode == Mode.SEARCH:
            self.cursor.set_pos(self.pre_search_cursor[0], self.pre_search_cursor[1], self.buffer.get_line_length, self.buffer.max_y)
            self.all_matches = []
            self.last_match = None
        self.mode = Mode.NORMAL
        self.prompt.clear()

    # ── Help Mode (F1) ────────────────────────────────────────

    def _enter_help(self):
        self.mode = Mode.HELP
        self.help_view.reset()

    def _handle_help(self, key, screen_rows=24, screen_cols=80):
        k = key
        if isinstance(key, str) and len(key) == 1:
            k = ord(key)
            
        if k == 27 or k == ord('q') or k == ord('Q'): # Esc or q
            self.mode = Mode.NORMAL
        elif key == curses.KEY_UP:
            self.help_scroll_y = self.help_view.move("up", screen_rows, screen_cols)
        elif key == curses.KEY_DOWN:
            self.help_scroll_y = self.help_view.move("down", screen_rows, screen_cols)
        elif key == curses.KEY_PPAGE:
            self.help_scroll_y = self.help_view.move("page_up", screen_rows, screen_cols)
        elif key == curses.KEY_NPAGE:
            self.help_scroll_y = self.help_view.move("page_down", screen_rows, screen_cols)

    # ── File I/O & Safety ─────────────────────────────────────

    def _save(self):
        if not self.buffer.filename:
            self.mode = Mode.SAVE_AS
            self.prompt.start("Save As", "")
            return
            
        if self.buffer.save():
            # Clean up swap file on successful save (v0.0.4a01)
            delete_swap(self.buffer.filename)
            self.message = f"Saved {self.buffer.filename}"
        else:
            self.message = f"Error saving {self.buffer.filename}"

    def _quit(self):
        if any(doc.buffer.modified for doc in self.documents):
            self.mode = Mode.EXIT_CONFIRM
            self.message = "Unsaved changes! Quit anyway?"
        else:
            self._do_exit()

    def _handle_exit_confirm(self, key):
        if isinstance(key, str):
            k = key.lower()
            if k == 'y':
                self._do_exit()
            elif k == 'n' or k == 'c' or key == chr(27):
                self.mode = Mode.NORMAL
                self.message = ""

    def _do_exit(self):
        # Save session on clean exit (v0.0.4a01)
        if self.config.restore_session:
            save_session(self.documents, self.current)
        self.running = False

    # ── Clipboard & Editing Commands ──────────────────────────

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
            # Zero-width selection or no mark: cut the whole line (nano semantics)
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
            if text: self.clipboard.store(text)
        if not text: return
        
        self._pre_edit()
        self.cursor.x, self.cursor.y = self.clipboard.paste_into(self.buffer, self.cursor.x, self.cursor.y)

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

    def _switch_buffer(self, next=True):
        if len(self.documents) <= 1: return
        if next:
            self.current = (self.current + 1) % len(self.documents)
        else:
            self.current = (self.current - 1) % len(self.documents)

    def _goto_line(self):
        self.mode = Mode.GOTO_LINE
        self.prompt.start("Go To Line", "")

    def _handle_mouse(self):
        try:
            _, mx, my, _, bstate = curses.getmouse()
            if bstate & curses.BUTTON1_CLICKED:
                # Simplified click-to-cursor logic
                self.cursor.set_pos(mx, my, self.buffer.get_line_length, self.buffer.max_y)
        except curses.error:
            pass


# ── Entry Point ───────────────────────────────────────────────

def main():
    cfg = Config()
    cli_files = sys.argv[1:] if len(sys.argv) > 1 else []
    
    # Pre-curses Swap Recovery Prompt (v0.0.4a01)
    if cli_files:
        for filepath in cli_files:
            swap_data = read_swap(filepath)
            if swap_data:
                print(f"\n[Femto] Swap file found for {filepath}.")
                choice = input("Recover unsaved changes? (y/n): ").strip().lower()
                if choice != 'y':
                    delete_swap(filepath)
                else:
                    print("Recovering... (swap data will be loaded into buffer)")
                    # Note: A full implementation would inject swap_data into the Document here.
                    
    # Session Restore
    if not cli_files and cfg.restore_session:
        session = load_session()
        if session and session.get('buffers'):
            cli_files = [b['filename'] for b in session['buffers'] if b['filename'] and os.path.exists(b['filename'])]

    def run(stdscr):
        app = Application(stdscr, initial_files=cli_files)
        
        # Inject swap data if user chose to recover
        for doc in app.documents:
            if doc.buffer.filename:
                swap_data = read_swap(doc.buffer.filename)
                if swap_data:
                    doc.buffer.lines = swap_data['lines']
                    doc.cursor.set_pos(swap_data['x'], swap_data['y'], doc.buffer.get_line_length, doc.buffer.max_y)
                    doc.buffer.touch()
                    delete_swap(doc.buffer.filename) # Clean up after recovery
                    
        app.main_loop()

    try:
        curses.wrapper(run)
    except KeyboardInterrupt:
        pass

if __name__ == "__main__":
    main()

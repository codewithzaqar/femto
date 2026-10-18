# Changelog

All notable changes to Femto are documented in this file.

## [0.0.5a03]

### Added
- **Snippet Expansion:** Type a trigger and press Tab to expand templates.
    - Snippets defined in `~/config/femto/snippets.ini` (INI format, per filetype + global)
    - Tab stops `${1:placeholder}` selected in order; typing replaces placeholder
    - Tab / Shift+Tab navigate stops, Esc exits snippet mode, F4 lists snippets
    - Ships with default Python/JavaScript/global snippets

- **Column Selection:** Rectangular selection with `Alt+B`.
    - Set column mark with Alt+B, move cursor to define rectangle
    - Cut/copy operations respect column mode (extract rectangle as block)
    - Renderer highlights rectangular region across all affected lines
    - Esc cancels back to no selection

- **File Tree Browser:** Visual project navigation with F2.
    - Browse directory structure with arrow keys
    - Expand/collapse directories with +/- keys
    - Enter opens selected file
    - Respects .gitignore patterns and common ignore directories
    - Shows file/directory for visual clarity

- **Error Notifications:** Visual bell (100ms screen inversion) and audible bell for errors:
  - Search not found, invalid regex, file >50MB, missing save filename, unchanged buffer, failed saves
  - Non-blocking: uses timed input wait without sleeping or consuming user input
  - Config: `bell` (default: false) and `visual_bell` (default: true)
  - Preserves cursor position, text, and color pairs during flash

### Documentation
- **Configuration Reference:** Complete guide to all 22 config options with defaults, behabiors, and examples
- **Keybinding Guide:** Shortcuts organized by editor mode (normal, search, prompts, file tree, help)
- **README Updates:** Corrected config paths, exit behavior, and removed unsupported CLI examples

## [0.0.4] - 2026-10-15

### Features
- **Crash Recovery:** Swap files written to temp directory every 30s; recovery prompt on startup (v0.0.4a01)
- **Session Restore:** Open buffers and cursor positions persist across restarts (v0.0.4a01)
- **Git Gutter Markers:** Shows `+`/`~` symbols for uncommitted changes in the line-number gutter (v0.0.4a02)
- **Project-Wide Grep:** Search across all files with `^W` then `^E` (v0.0.4a03)
- **Whitespace Hygiene:** Visual trailing whitespace highlighting + auto-trim on save (v0.0.4a04)
- **Truecolor Themes:** Configurable color themes with RGB -> 256-color fallback for modern terminals
- **Large File Protection:** Files > 50MB refused with clear error message to prevent UI freeze

### Quality of Life
- **Universal Ctrl Keys:** `^C`/`^V` for copy/paste, `^D` for duplicate, `^Q` for mouse toggle
- **Live Search:** Matches highlight as you type, cursor jumps automatically
- **Mouse Wheel:** Scroll viewport with wheel (3 lines per notch)
- **Bulletproof Input:** Handles all terminals quirks (getch/get_wch, Alt escape sequences, backspace variants)
- **`.editorconfig` Support:** Honors `indent_size`, `tab_width`, `end_of_line`, `insert_final_newline`

### Bug Fixes
- Sort selection now consumes the mark (fixes consecutive sort bug)
- Cut/copy operations read selection before mutation (fixes highlight cache invalidation)
- Stateful highlighting correctly tracks lexical state across wrapped and off-screen lines
- Cursor properly clamps after trailing whitespace trim

### Stats
- **183 tests** (up from 154 at v0.0.3)
- **5 external contributors** mentored through complex PRs
- **Zero external dependencies** (pure stdlib)

### Community
Massive thanks to our contributors who made this release cycle possible:
- `@drathava847-beep` (Truecolor Themes, 50MB Fast-Fail, Search Highlighting, Unicode/Tab Completion)
- `@tushar-hub` (Line Operations Bundle)
- `@legendteddy` (Sort Selection Mark Consumption)
- `@S2zxx0zxx` (.editorconfig Support)
- `@feliperm17` & `@HarshRajSinghania` (Various v0.0.3 carry-overs)

## [0.0.3] - 2026-10-06

### 🚀 Features
- **Full-Screen Help (F1):** Categorized, scrollable help screen detailing every keybinding (fixes #20).
- **System Clipboard Bridge:** `Ctrl+P` / `Ctrl+U` now sync with `pbcopy`, `xclip`, `wl-copy`, and `clip.exe` via a new `system_clipboard` config flag (fixes #18).
- **Save-As Tab Completion:** Pressing `Tab` in the Save-As prompt auto-completes filenames and directories (fixes #21).
- **Highlight All Matches:** Search now highlights every occurrence on screen with a low-priority overlay, keeping the active match distinct (fixes #22).
- **Smart Auto-Indent:** `Enter` copies leading whitespace and automatically indents one extra level in Python files when the previous line ends with `:` (fixes #17).
- **Word-Boundary Wrapping:** Soft wrap now breaks at spaces instead of mid-word, with a hard-cut fallback for long words (fixes #19).

### 🐛 Bug Fixes & I/O Fidelity
- **Multi-line Python Highlighting:** Syntax highlighter now carries lexical state across lines, fixing broken coloring for `"""` docstrings (fixes #14).
- **Line Ending Preservation:** Detects and preserves CRLF/CR/LF line endings on save, with a `line_ending` config override (fixes #11).
- **POSIX Trailing Newlines:** Ensures files always end with a newline, configurable via `final_newline` (fixes #2).
- **Unicode Fidelity:** Fixed layout math for ZWJ emoji clusters (e.g., 👨‍👩‍👧‍👦) and combining characters/accents (e.g., `é`, `ñ`) so they correctly occupy 0 or 2 terminal columns (fixes #16, #25).

### ⚡ Architecture & Performance
- **Memory-Efficient Undo:** Replaced deep-copy snapshots with content-addressed line interning, reducing undo memory usage by ~99% on large files (fixes #15).
- **Lazy Highlighting Invalidation:** Highlighting state is now cached by `(line, entering_state)` and invalidated via `buffer.revision`, eliminating `O(N)` penalties on unchanged frames.

### 🙏 Community
Massive thanks to our contributors who made this release possible:
- `@feliperm17` (F1 Help Screen, Multi-line Highlighting State Machine)
- `@drathava847-beep` (Highlight All Matches, Unicode/Combining Fixes, Tab Completion)
- `@HarshRajSinghania` (CRLF Line Ending Preservation)

## [0.0.2] - Stable

- **Multi-buffer editing:** Open multiple files (`femto a b c`), switch with `Ctrl+F` / `Ctrl+L`.
- **Selection & Clipboard:** `Ctrl+B` (mark), `Ctrl+K` (cut), `Ctrl+P` (copy), `Ctrl+U` (paste).
- **Search & Replace:** `Ctrl+\` flow with per-match `Y/N/A/C` confirm. Regex and case-insensitive toggles (`Ctrl+R`, `Ctrl+O`).
- **Readability:** Dynamic line-number gutter (`Ctrl+N`), pure-Python syntax highlighting for `.py` files.
- **Mouse Support:** Wheel scrolling and click-to-cursor (`Ctrl+D` toggle).
- **Unicode Fidelity:** Width-aware layout math for CJK and Emoji characters (no more broken soft-wrap).
- **Platform Hardening:** Windows `Shift+Tab` / `Ctrl+Arrow` fallbacks, robust Alt/Ctrl key decoding.
- **Performance & Safety:** Atomic saves (`fsync` + `os.replace`), optional `name~` backups, frame-signature redraw skip, memoised syntax highlighting.

## [0.0.1] - Stable
- Packaging: `pyproject.toml`, console script `femto`, `python -m femto`
- CLI flags: `--version`, `--tab-size`, `--scroll-margin`, `--no-wrap`
- New `layout.py` (curses-free visual mapping) + unittest regression suite
- `soft_wrap = false` now works (horizontal-scroll fallback)
- Page Up/Down respect soft-wrapped visual rows
- Scroll clamping for very small terminals; ASCII-safe status messages
- MIT license, finalized README
- Visual soft line wrapping, smooth scrolling, `.femtorc` config parsing
- Search (Ctrl+W), Go-To-Line (Ctrl+T), snapshot Undo/Redo (Ctrl+Z / Ctrl+Y)
- Mode state machine, Save-As prompt, exit confirmation (Y/N/C)
- Word jump, Page Up/Down, Home/End, Tab / Shift-Tab indentation
- Initial alpha: load/save, arrows, insert/delete, nano-style status bar

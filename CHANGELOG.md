# Changelog

All notable changes to Femto are documented in this file.

## [0.0.4a02]

### Added
- **Git Gutter Markers:** Shows `+` (added), `~` (modified) symbols in the line-number gutter for uncommitted changes vs. HEAD.
- Enabled via `git_gutter = true` in config (default: disabled).
- Recomputes every 1 second while idle; fails silently outside git repos.
- Pure stdlib implementation using `subprocess` + `git diff -U0`.
- `.editorconfig` support: Honors `indent_size`, `tab_width`, `end_of_line`, and `insert_final_newline` by walking up the directory tree (fixes #[insert_correct_issue_number]) — thanks @S2zxx0zxx!
- Line operations bundle: Duplicate (`Alt+D`), Transpose (`Alt+T`), Sort (`Alt+S`/`Alt+Shift+S`), and Case Transform (`Alt+U`/`Alt+L`) for lines and selections (fixes #36) - thanks @tushar-hub!

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
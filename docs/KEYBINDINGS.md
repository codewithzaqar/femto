# Keybinding reference

`Ctrl+X` (also written `^X` in the help screen) means hold Ctrl and press X.
`Alt+D` means hold Alt and press D. Shortcuts depend on the current mode.
These tables follow [`Application`'s input handlers](../femto/app.py) and the
[help catalog](../femto/help.py); where older README instructions differ, the
handlers determine the behavior described here.

## General and buffers (normal editing mode)

| Key | Action |
| --- | --- |
| Ctrl+S | Save; open Save As if the buffer has no filename. |
| Ctrl+X | Exit if all buffers are unmodified; otherwise ask whether to quit anyway. **This confirmation does not save your changes.** |
| Ctrl+F / Ctrl+L | Next / previous buffer. |
| F1 | Open read-only help. |
| F2 | Open the file-tree browser. |
| Ctrl+N | Toggle line numbers for this session. |
| Ctrl+Q | Toggle mouse reporting for this session. |

Save modified buffers with Ctrl+S before exiting if you want to keep them.

### Exit confirmation

| Key | Action |
| --- | --- |
| Y / y | Quit without saving modified documents. |
| Any other key | Cancel exit and return to editing. |

## Navigation and editing

| Key | Action |
| --- | --- |
| Arrow keys | Move the cursor; Up/Down account for soft wrapping. |
| Home / End | Beginning / end of the logical line. |
| PgUp / PgDn | Move one page up / down. |
| Ctrl+T | Open the Go To Line prompt (1-based line numbers). |
| Enter | Insert a newline; apply auto-indent if enabled. |
| Tab | Insert `tab_size` spaces at the cursor. |
| Shift+Tab | Remove up to `tab_size` leading spaces from the current line. |
| Backspace / Ctrl+H | Delete before the cursor; join lines at the beginning of a line. |
| Delete | Delete at the cursor; join lines at the end of a line. |
| Ctrl+Z / Ctrl+Y | Undo / redo. |
| Ctrl+D | Duplicate the current line, or a non-empty single-line selection. |
| Ctrl+E | Swap the current line with the line above. |
| Ctrl+O / Ctrl+R | Sort selected lines case-sensitively / case-insensitively. Requires a mark; a mark at the current cursor with no range sorts the whole buffer. Sorting clears the mark. |
| Ctrl+A / Ctrl+G | Convert the selected range to uppercase / lowercase. Requires a mark. |

Ctrl+A and Ctrl+E are **case conversion and transpose**, not Home/End.
Word-movement constants exist in `keys.py`, but the normal input handler does
not currently dispatch Ctrl+Left/Right or Shift+Left/Right as word movement.
Use Home/End and the unmodified arrows.

### Optional Alt aliases (normal editing only)

| Key | Same operation as |
| --- | --- |
| Alt+D | Ctrl+D (duplicate). |
| Alt+T | Ctrl+E (transpose). |
| Alt+S | Ctrl+O (case-sensitive sort). |
| Alt+Shift+S | Ctrl+R (case-insensitive sort). |
| Alt+U / Alt+L | Ctrl+A / Ctrl+G (uppercase / lowercase). |

Alt aliases depend on the escape sequences delivered by your terminal. Prefer
the Ctrl variants if an alias is intercepted or not recognized.

## Clipboard and selection

| Key | Action |
| --- | --- |
| Ctrl+B | Set / clear the selection mark; move the cursor to extend the selection. |
| Ctrl+K | Cut the selected range, or the whole current line when no non-empty selection exists. |
| Ctrl+P / Ctrl+C | Copy the selected range, or the current line when no mark is active. Prefer Ctrl+P if the terminal intercepts Ctrl+C. |
| Ctrl+U / Ctrl+V | Paste the internal clipboard; try the OS clipboard only if it is empty and `system_clipboard` is enabled. |

These are Femto commands. The terminal's own copy/paste shortcuts may be
different and are configured outside Femto. See
[`system_clipboard`](CONFIGURATION.md#search-and-input) for configuration.

## Search and replace

| Key or sequence | Action |
| --- | --- |
| Ctrl+W | Open Search. Matches are highlighted as you type. |
| Enter in Search | Find the next match, wrapping around the buffer; return to editing. Reopen Ctrl+W to use the remembered term. |
| Ctrl+W, type a pattern, Ctrl+E | Search files under the current working directory and show grep results. |
| Ctrl+Backslash | Open Replace: enter the search text, press Enter, enter replacement text, and press Enter again. |
| Ctrl+O in a prompt | Toggle case-insensitive search. |
| Ctrl+R in a prompt | Toggle regex matching for search. |
| Ctrl+G / Esc in a prompt | Cancel; cancelling Search also restores the pre-search cursor. |

The current replacement handler performs a **literal, case-sensitive replacement
throughout the buffer**. It does not offer a per-match Y/N/A confirmation, and
does not apply the regex/case toggles to replacement. Review the result and use
Ctrl+Z to undo it if needed. Those toggles control searching even though the
prompt handler accepts them in other prompts too.

### Common prompt editing

Applies to Save As, Search, Replace, and Go To Line:

| Key | Action |
| --- | --- |
| Left / Right | Move the prompt cursor. |
| Home / End | Beginning / end of the prompt text. |
| Backspace / Ctrl+H | Delete before the prompt cursor. |
| Delete | Delete at the prompt cursor. |
| Enter | Submit the current prompt. |
| Ctrl+G / Esc | Cancel the prompt. |
| Tab in Save As | Complete a path; ambiguous matches may extend the shared prefix and display candidates. |

F1 does not open help from these prompts.

## Grep results

| Key | Action |
| --- | --- |
| Up / Down | Select the previous / next result. |
| PgUp / PgDn | Move by a page of results. |
| Enter | Open the selected result's file and jump to its line. |
| Esc / q | Return to editing. |

## File-tree browser

| Key | Action |
| --- | --- |
| Up / Down | Select the previous / next entry. |
| PgUp / PgDn | Move by a page of entries. |
| + / = / - | Toggle the selected directory's expanded state. Both + and - toggle; they are not separate expand/collapse commands. |
| Enter | Open a selected file, or toggle a selected directory. |
| Esc / F2 | Close the browser and return to editing. |

## Help screen

| Key | Action |
| --- | --- |
| Up / Down | Scroll one row. |
| PgUp / PgDn | Scroll one page. |
| Esc / q / Q | Return to editing without modifying the document. |

Home/End are not handled in the current help view. Normal editing commands
are ignored while help is open.

## Mouse and terminal compatibility

With `mouse = true` or after Ctrl+Q:

- Click to position the cursor.
- Use the wheel to move three lines up/down per event.

The bindings are intended for POSIX terminals and Windows with
`windows-curses`, but only keys the terminal delivers can reach the editor:

- F1/F2, Shift+Tab, Delete, navigation keys, Alt sequences, and mouse events
  depend on terminal/curses mappings and may be intercepted by the terminal.
- Ctrl+S/Ctrl+Q can be consumed by terminal flow control. Ctrl+Z may suspend
  the process, and Ctrl+C may raise `KeyboardInterrupt` instead of copying.
  The launcher catches that interrupt and exits without a save confirmation.
- Prefer Ctrl+P for copy and Ctrl+U for paste when universal clipboard
  combinations are intercepted. Use Home/End for line navigation.
- A working shortcut in one mode can mean something different in another:
  Ctrl+G lowercases a selection in editing but cancels a prompt; Ctrl+O sorts
  in editing but changes search case handling in prompts.

The keybinding tables describe the current handlers, not a guarantee that every
terminal sends every combination. No user-defined key remapping is currently
parsed from `.femtorc`.

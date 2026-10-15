# Configuration reference

This reference describes the settings currently implemented in
[`femto/config.py`](../femto/config.py). For shortcuts, see the
[keybinding reference](KEYBINDINGS.md).

## Config file location and precedence

Femto reads the **first existing** file in this order:

1. `~/.femtorc` in your home directory.
2. `.femtorc` in the directory from which you start Femto.

The files are not merged: if the home file exists, the local file is not read.
On Windows, `~` is expanded by Python to your user home directory, normally
`%USERPROFILE%`. The current loader does **not** read
`~/.config/femto/config` or `%APPDATA%\femto\config`. Create `.femtorc` yourself
and restart Femto after editing it; there is no live config reload.

## File syntax

Use one `key = value` assignment per line, without section headers or quotes.
Blank lines and lines beginning with `#` are ignored. Keys are case-sensitive.
For booleans, `true`, `1`, and `yes` mean true (case-insensitive); every other
value means false. Use `true` and `false` for clarity.

Put comments on their own lines. Inline comments are **not** stripped:
`final_newline = true # comment` sets the option to false, and
`theme = "default"` includes the quotes in the theme name. Unknown keys and
lines without `=` are ignored. A read or conversion error is silently caught
and stops processing the rest of that file; earlier assignments remain.

## Options and defaults

All 22 keys accepted by `_parse()` are listed below. Options marked as not
connected are accepted by the parser but do not currently have the advertised
effect in the running editor.

### Indentation and display

| Option | Default | Meaning |
| --- | --- | --- |
| `tab_size` | `4` | Spaces inserted by Tab and used when expanding tabs on file load; integer, clamped to at least 1. Femto edits with spaces, not literal tabs. |
| `auto_indent` | `true` | Copy leading whitespace when inserting a newline; Python files also gain one indentation level after a line ending in `:`. |
| `smooth_scroll_margin` | `3` | Integer clamped to at least 0. Currently stored only: the main loop passes a fixed margin of 3, so changing this setting does not change scrolling. |
| `soft_wrap` | `true` | Wrap long lines visually without inserting newlines; false uses horizontal scrolling. |
| `wrap_at_word` | `true` | Prefer word boundaries for soft wrapping; false uses fixed-width chunks. |
| `show_line_numbers` | `false` | Display the line-number gutter; Ctrl+N toggles it for the current session. |
| `syntax_highlight` | `true` | Highlight named files ending in `.py`; not a language selector. |
| `show_trailing_ws` | `true` | Highlight trailing spaces and tabs. |
| `theme` | `default` | Load a theme by name from `femto/themes/`; see [Themes](#themes). |

### Search and input

| Option | Default | Meaning |
| --- | --- | --- |
| `ignore_case` | `false` | Parsed but not copied into the application's `SearchOptions`. Use Ctrl+O in a search prompt to change the active search option. |
| `regex_search` | `false` | Parsed but not copied into `SearchOptions`. Use Ctrl+R in a search prompt to enable regex matching. |
| `mouse` | `false` | Enable terminal mouse reporting; Ctrl+Q toggles it during editing. Support depends on the terminal. |
| `bell` | `false` | Write the terminal BEL character on supported error notifications; sound depends on terminal settings. |
| `visual_bell` | `true` | Briefly invert the screen for error notifications, without blocking input. |
| `system_clipboard` | `false` | Also send copied/cut text to an OS clipboard helper. Paste uses Femto's internal clipboard first, and reads the system clipboard only when the internal clipboard is empty. External helper availability depends on the OS/session. |

### Saving and session state

| Option | Default | Meaning |
| --- | --- | --- |
| `make_backup` | `false` | Before replacing an existing file, save its previous contents as `filename~`. Later saves replace that backup. |
| `line_ending` | `auto` | `auto` preserves the detected line ending (LF for a new file); `lf`, `crlf`, and `cr` force that ending. Values must be lowercase; other values are ignored. |
| `final_newline` | `true` | Ensure a final newline when saving. False does not remove an existing final newline: the buffer also preserves one detected on load. |
| `trim_on_save` | `false` | Strip trailing whitespace from every line when saving through the application. |
| `autosave_seconds` | `30` | Interval for writing recovery swap data for modified, named buffers during idle input checks; 0 or a negative integer disables it. This does **not** save the original document. |
| `restore_session` | `true` | Save session metadata on normal exit. Loading saved filenames is implemented by `femto.app.main()` (`python -m femto.app`), but the packaged `femto` / `python -m femto` launcher does not currently call that startup path. |
| `git_gutter` | `false` | Request Git diff markers for the current named file; enable `show_line_numbers` to see the markers in the gutter. Requires Git and a file in a repository. |

Session metadata uses `$XDG_CONFIG_HOME/femto/session.json`, falling back to
`~/.config/femto/session.json`. This is a separate file from `.femtorc` and is
not an alternative location for editor settings.

## Example customization

Save this as `~/.femtorc` (or a local `.femtorc` if no home file exists):

```ini
# Indentation and appearance
tab_size = 2
auto_indent = true
soft_wrap = true
wrap_at_word = true
show_line_numbers = true
theme = solarized-dark

# Saving
make_backup = true
line_ending = lf
final_newline = true
trim_on_save = true

# Input and notifications
mouse = false
system_clipboard = false
bell = false
visual_bell = true

# Background recovery and Git markers
autosave_seconds = 60
restore_session = true
git_gutter = true
```

## Per-file EditorConfig settings

For named documents, `Config.for_file()` copies the base settings and applies
matching `.editorconfig` files from ancestor directories. A preamble
`root = true` stops the upward search; nearer files and later matching sections
override earlier settings. `unset` removes an inherited EditorConfig property,
leaving the base Femto setting if no value remains.

The supported properties are:

| Property | Effect |
| --- | --- |
| `indent_size` | Positive integer overrides `tab_size`. `indent_size = tab` uses `tab_width` if supplied. |
| `tab_width` | Used for `indent_size = tab`; it does not independently change indentation. |
| `end_of_line` | `lf`, `crlf`, or `cr` overrides `line_ending`. |
| `insert_final_newline` | `true` or `false` overrides `final_newline`, subject to the existing-newline preservation described above. |

```ini
root = true

[*.py]
indent_size = 4
end_of_line = lf
insert_final_newline = true

[*.js]
indent_size = 2
```

This is a limited implementation, not the whole EditorConfig specification.
For example, `indent_style`, `charset`, and `trim_trailing_whitespace` are not
applied. Use Femto's `trim_on_save` for the last behavior.

## Themes

Built-in names are `default`, `default-light`, `solarized-dark`,
`solarized-light`, and `high-contrast`. Give only the name, without `.ini` or
quotes. Theme colors are rendered according to terminal color capabilities;
RGB colors fall back to the available palette. The `theme` setting does not
accept an arbitrary file path.

## Sources

- [Config loading and parsing](../femto/config.py)
- [Per-file configuration](../femto/documents.py)
- [Saving and line endings](../femto/buffer.py)
- [Input, autosave, and startup behavior](../femto/app.py)
- [Packaged launcher](../femto/__main__.py)
- [Theme loading](../femto/theme.py)

# Femto

### A tiny, Nano-style terminal text editor written in Python.

<p align="center">
    <img src="assets/femto-demo.png" alt="Femto v0.0.3 Terminal Editor Demo" width="800">
    <br>
    <em>Femto v0.0.3: Featuring the F1 help screen, stateful Python docstring highlighting, word-boundary wrapping, and multi-match search overlays.</em>
</p>

[![PyPI version](https://img.shields.io/pypi/v/femto-editor)](https://pypi.org/project/femto-editor/)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-Standard%20Library-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![GitHub stars](https://img.shields.io/github/stars/codewithzaqar/femto?style=social)](https://github.com/codewithzaqar/femto/stargazers)

**Femto** is a lightweight, keyboard-driven terminal text editor inspired by GNU Nano. Built with Python and the standard-library `curses` module, it provides an efficient text-editing experience directly in your terminal.

Femto aims to keep things simple: open your files, edit your text, navigate between buffers, search for content, and save your changes without the overhead of a heavyweight editor.

- **Lightweight:** No third-party runtime dependencies on POSIX systems.
- **Terminal-native:** Edit files directly inside your terminal.
- **Keyboard-driven:** Navigate and edit using familiar shortcuts.
- **Unicode-aware:** Support for Unicode text, including CJK characters and emoji.
- **Configurable:** Customize the editor's behavior and appearance.

**Repository:** [codewithzaqar/femto](https://github.com/codewithzaqar/femto)

## Features

- **Multi-buffer editing** — Open multiple files and switch between buffers.
- **Soft line wrapping** — Read and edit long lines without inserting extra newline characters.
- **Python syntax highlighting** — Highlight Python source files, including stateful docstring highlighting.
- **Search and replace** — Search within documents, optionally use regular expressions, and replace matching text.
- **Unicode support** — Handle wide characters, CJK text, and emoji.
- **Mouse support** — Position the cursor with mouse clicks when supported by your terminal.
- **Line numbers** — Toggle line numbers while editing.
- **Undo and redo** — Reverse and restore editing operations.
- **Selection and clipboard** — Select, copy, cut, and paste text.
- **File-tree browser** — Browse directories and open files from the editor.
- **Built-in help** — Access the keyboard shortcut reference with F1.
- **Configurable themes** — Choose from built-in themes and customize editor settings.
- **Automatic indentation** — Preserve indentation when inserting new lines.
- **Backup and recovery options** — Configure file backups and recovery-related behavior.

> Note: Regular-expression matching applies to search. The current replace operation performs literal, case-sensitive replacement throughout the buffer.

## Installation

### Option 1: Install with pipx (recommended)

[pipx](https://pipx.pypa.io/) installs Python applications in isolated environments and makes their commands available from your terminal.

```bash
pipx install femto-editor
```

### Option 2: Install with pip

```bash
pip install femto-editor
```

### Option 3: Install from source

Clone the repository and install the local package:

```bash
git clone https://github.com/codewithzaqar/femto.git
cd femto
pip install .
```

After installation, the `femto` command should be available in your terminal.

### Platform support

- **Linux and other POSIX systems:** Uses the Python standard-library `curses` module without third-party runtime dependencies.
- **Windows:** The package automatically installs `windows-curses` when required.

Terminal behavior and shortcut availability can vary depending on your operating system and terminal emulator.

## Quick start

Open the editor without specifying a file:

```bash
femto
```

Open an existing file:

```bash
femto README.md
```

Create or edit a Python file:

```bash
femto hello.py
```

Open multiple files in separate buffers:

```bash
femto main.py utils.py README.md
```

You can switch between buffers without launching a separate editor for every file.

## Keyboard shortcuts

The following shortcuts apply to normal editing mode. Some combinations may be intercepted by your terminal.

| Shortcut | Action |
|---|---|
| `Ctrl + S` | Save the current file |
| `Ctrl + X` | Exit the editor |
| `Ctrl + F` | Switch to the next buffer |
| `Ctrl + L` | Switch to the previous buffer |
| `Ctrl + W` | Open search |
| `Ctrl + P` | Copy the selection or current line |
| `Ctrl + U` | Paste from the internal clipboard |
| `Ctrl + K` | Cut the selection or current line |
| `Ctrl + Z` | Undo |
| `Ctrl + Y` | Redo |
| `Ctrl + N` | Toggle line numbers |
| `Ctrl + T` | Go to a specific line |
| `F1` | Open the help screen |
| `F2` | Open the file-tree browser |
| Arrow keys | Move the cursor |

**Important:** When exiting with unsaved changes, Femto asks for confirmation. Confirming exit discards those changes. Save your files with `Ctrl + S` before leaving if you want to keep them.

For additional shortcuts, selection commands, search behavior, and terminal compatibility notes, see the [complete keybinding reference](docs/KEYBINDINGS.md).

## Configuration

Femto supports a `.femtorc` configuration file.

The editor checks these locations in order:

1. `~/.femtorc`
2. `.femtorc` in the current working directory, but only if the home configuration does not exist.

The files are not merged. Restart Femto after changing configuration settings.

### Example configuration

Create a file named `~/.femtorc` and add:

```ini
# Indentation
tab_size = 4
auto_indent = true

# Display
show_line_numbers = true
soft_wrap = true
wrap_at_word = true
syntax_highlight = true
theme = default

# File handling
make_backup = true
final_newline = true
trim_on_save = false

# Input
mouse = false
system_clipboard = false
```

Configuration values use `key = value` syntax. Do not wrap values in quotes.

Available themes include:

- `default`
- `default-light`
- `solarized-dark`
- `solarized-light`
- `high-contrast`

Some settings are accepted by the configuration parser but are not yet connected to the running editor. Check the [configuration reference](docs/CONFIGURATION.md) for the implemented behavior, defaults, and limitations.

Femto also supports a subset of [EditorConfig](https://editorconfig.org/) settings for named files.

## Running the tests

Femto includes a regression test suite based on Python's built-in `unittest` framework.

Clone the repository, enter its directory, and run:

```bash
python -m unittest discover -s tests -v
```

The test suite is designed to run without an interactive terminal.

## Project structure

The repository is organized around the application, its supporting modules, documentation, and tests.

```text
femto/
├── .github/
├── assets/
├── docs/
│   ├── KEYBINDINGS.md
│   └── CONFIGURATION.md
├── femto/
├── tests/
├── .femtorc
├── CHANGELOG.md
├── LICENSE
├── README.md
├── femto.py
└── pyproject.toml
```

- `femto/` — Core application and supporting modules.
- `tests/` — Automated regression tests.
- `docs/` — Keyboard shortcuts and configuration documentation.
- `assets/` — Project assets.
- `CHANGELOG.md` — Version history.
- `pyproject.toml` — Python packaging and project configuration.

## Design philosophy

Femto is built around a few simple principles:

1. **Keep it lightweight.** Avoid unnecessary dependencies and complexity.
2. **Stay in the terminal.** Make text editing available wherever a terminal is available.
3. **Prioritize usability.** Provide useful editing features through clear keyboard interactions.
4. **Keep configuration practical.** Allow users to customize the editor without a complicated setup.
5. **Improve incrementally.** Build, test, document, and refine the project over time.

Femto is an evolving open-source project. Features and behavior may change as development continues.

## Contributing

Contributions, bug reports, feature suggestions, and feedback are welcome.

To get started:

1. Explore the [repository](https://github.com/codewithzaqar/femto).
2. Check existing [issues](https://github.com/codewithzaqar/femto/issues).
3. Reproduce a bug or identify a specific improvement.
4. Create a focused change and add tests when appropriate.
5. Open a pull request describing what changed and why.

Please keep contributions focused, documented, and consistent with the project's lightweight design philosophy.

## Roadmap

Future improvements can be discussed through GitHub Issues. Potential areas to explore include:

- Improving terminal compatibility.
- Expanding editing and navigation capabilities.
- Refining syntax highlighting.
- Improving configuration and documentation.
- Strengthening automated test coverage.

These are potential development directions, not promises that every item is currently implemented or scheduled.

## License

Femto is released under the [MIT License](LICENSE).

You are welcome to use, modify, and distribute the project under the terms of that license.

## Author

**Zaqar Hakobyan** — creator and maintainer of Femto.

- GitHub: [@codewithzaqar](https://github.com/codewithzaqar)
- Project: [Femto](https://github.com/codewithzaqar/femto)

---

If you find Femto useful, consider giving the repository a ⭐ on GitHub. It helps other developers discover the project.

**Built with Python. Designed for the terminal.**

# Femto

### A tiny, fast, and lightweight terminal text editor written in Python.

[![PyPI version](https://img.shields.io/pypi/v/femto-editor?style=flat-square&color=blue)](https://pypi.org/project/femto-editor/)
[![Python](https://img.shields.io/badge/Python-3-blue?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![GitHub Stars](https://img.shields.io/github/stars/codewithzaqar/femto?style=flat-square)](https://github.com/codewithzaqar/femto/stargazers)
[![GitHub Forks](https://img.shields.io/github/forks/codewithzaqar/femto?style=flat-square)](https://github.com/codewithzaqar/femto/forks)

**Femto** is a lightweight, nano-style terminal text editor built with Python and the standard library. It brings practical editing features directly to your terminal without the overhead of a large editor.

Designed for developers who value simplicity, portability, and a focused terminal workflow.

[**Get started**](#-installation) · [**Features**](#-features) · [**Report a bug**](https://github.com/codewithzaqar/femto/issues) · [**Contribute**](CONTRIBUTING.md)

---

## ✨ Features

- **Lightweight by design** — uses Python's standard library on POSIX systems.
- **Multiple buffers** — open and switch between multiple files in one session.
- **Syntax highlighting** — make source code easier to read.
- **Search and replace** — find text using regular expressions.
- **Unicode support** — work with international text, CJK characters, and emoji.
- **Soft line wrapping** — read long lines without horizontal scrolling.
- **Mouse support** — interact with the editor using a supported terminal.
- **Built-in help** — access the editor's keybinding help screen.
- **File-tree browser** — browse files from inside the editor.
- **Configurable experience** — customize settings, themes, and editing behavior.

## 🚀 Installation

Femto is available on PyPI as `femto-editor`.

### Option 1: Install with pipx

Recommended for installing a command-line application in an isolated environment.

```bash
pipx install femto-editor
```

### Option 2: Install with pip

```bash
python -m pip install femto-editor
```

### Option 3: Install from source

```bash
git clone https://github.com/codewithzaqar/femto.git
cd femto
python -m pip install .
```

After installation, the `femto` command should be available in your terminal.

## 💻 Quick start

Open a file:

```bash
femto README.md
```

Open multiple files:

```bash
femto main.py utils.py
```

Start the editor without specifying a file:

```bash
femto
```

## ⌨️ Essential keyboard shortcuts

| Shortcut | Action |
| --- | --- |
| `Ctrl + S` | Save the current file |
| `Ctrl + X` | Exit the editor |
| `Ctrl + W` | Search |
| `Ctrl + P` | Copy |
| `Ctrl + U` | Paste |
| `Ctrl + F` | Switch to the next buffer |
| `Ctrl + L` | Switch to the previous buffer |
| `F1` | Open the help screen |
| `F2` | Open the file-tree browser |

**Tip:** Save your changes before exiting. If a buffer has unsaved changes, Femto asks for confirmation before quitting.

## ⚙️ Configuration

Femto supports a `.femtorc` configuration file.

It checks these locations in order:

1. `~/.femtorc`
2. `./.femtorc`

The first existing file is used; the files are not merged.

Example configuration:

```ini
tab_size = 4
show_line_numbers = true
theme = default
make_backup = true
final_newline = true
```

Restart Femto after changing configuration settings.

See the project's documentation for the full list of configuration options and supported themes.

## 🧪 Running tests

Femto includes a regression test suite using Python's built-in `unittest` framework.

Run the tests from the repository root:

```bash
python -m unittest discover -s tests -v
```

## 🛠️ Built with

- **Python** — the implementation language.
- **curses** — terminal user-interface support.
- **Python standard library** — minimal runtime dependencies on POSIX systems.

On Windows, the project uses `windows-curses` to provide terminal support.

## 🗺️ Roadmap

Femto is an evolving open-source project. Potential areas for future development include:

- Improving the editing experience and usability.
- Expanding documentation and usage examples.
- Refining terminal compatibility.
- Improving tests and reliability.
- Listening to community feedback and feature requests.

Have an idea? [Open a feature request](https://github.com/codewithzaqar/femto/issues).

## 🤝 Contributing

Contributions, bug reports, suggestions, and documentation improvements are welcome.

1. Explore the existing [issues](https://github.com/codewithzaqar/femto/issues).
2. Read the [contribution guidelines](CONTRIBUTING.md).
3. Fork the repository and create a branch for your changes.
4. Make your changes and run the test suite.
5. Submit a pull request describing your improvements.

Even a small contribution can make Femto better for everyone.

## 🐛 Found a bug?

If you encounter a bug or unexpected behavior, please [open an issue](https://github.com/codewithzaqar/femto/issues).

Include the steps to reproduce the problem, your operating system, your Python version, and any relevant error messages.

## 📦 Project links

- **Repository:** [github.com/codewithzaqar/femto](https://github.com/codewithzaqar/femto)
- **PyPI:** [pypi.org/project/femto-editor](https://pypi.org/project/femto-editor/)
- **Issues:** [Report a bug or request a feature](https://github.com/codewithzaqar/femto/issues)
- **Changelog:** [CHANGELOG.md](CHANGELOG.md)
- **License:** [MIT License](LICENSE)

## 📄 License

Femto is open-source software released under the [MIT License](LICENSE).

## ⭐ Support the project

If Femto is useful to you, consider giving it a **star on GitHub**.

Stars help other developers discover the project and encourage continued development.

**Built with Python. Made for the terminal.**

---

Created and maintained by [@codewithzaqar](https://github.com/codewithzaqar).

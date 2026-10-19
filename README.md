# Femto v0.0.5

Femto is a tiny, nano-style terminal text editor written in **pure Python**.
It ships with zero runtime dependencies on POSIX system (standard-library `curses` only) and automatically pulls `windows-curses` on Windows.

Femto supports multi-buffer editing, soft line wrapping, syntax highlighting, regex search & replace, mouse support, and is fully Unicode (CJK/Emoji) aware.

<p align="center">
    <img src="assets/femto-demo.png" alt="Femto v0.0.3 Terminal Editor Demo" width="800">
    <br>
    <em>Femto v0.0.3: Featuring the F1 help screen, stateful Python docstring highlighting, word-boundary wrapping, and multi-match search overlays.</em>
</p>

## Install

```bash
# From PyPI (Recommended)
pipx install femto-editor
# or
pip install femto-editor

# From source
git clone https://github.com/codewithzaqar/femto.git
cd femto
pip install .
```

After installation, the `femto` command is available globally.

## Usage
```bash
femto [file ...]        # open one or multiple files
femto a.py x.py         # open two buffers
```

## Keybindings

See the [complete keybinding reference](docs/KEYBINDINGS.md) for shortcuts by
mode, selection and search commands, and terminal compatibility notes.

| Key | Action in normal editing mode |
| --- | --- |
| Ctrl+S | Save; open Save As for an unnamed buffer. |
| Ctrl+X | Exit; modified buffers require confirmation. **Confirming quits without saving.** |
| Ctrl+P / Ctrl+U | Copy / paste. |
| Ctrl+W | Search. |
| Ctrl+F / Ctrl+L | Next / previous buffer. |
| F1 / F2 | Open help / the file-tree browser. |

Save changes with Ctrl+S before confirming exit. In help, use Up/Down or
PgUp/PgDn to scroll and Esc or q to return to editing.

## Configuration

Femto reads the first existing file: `~/.femtorc`, then `./.femtorc`.
The files are not merged. Restart the editor after changing settings.

```ini
# Put comments on their own lines, and do not quote values.
tab_size = 4
show_line_numbers = true
theme = default
make_backup = true
final_newline = true
```

See the [configuration reference](docs/CONFIGURATION.md) for all 22 options,
defaults, parsing rules, themes, EditorConfig support, and a customization
example. It also identifies settings that are parsed but not yet connected
to the running editor.

## Running the tests

Femto includes a comprehensive `unittest` regression suite that runs headlessely (no terminal required).

```bash
python -m unittest discover -s tests -v
```

## Building a release

```bash
pip install build twine
python -m build          # creates dist/femto_editor-0.0.1-*.whl
python -m twine upload dist/* # publish to PyPI
```

## Star History

<a href="https://www.star-history.com/?repos=codewithzaqar%2Ffemto&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=codewithzaqar/femto&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=codewithzaqar/femto&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=codewithzaqar/femto&type=date&legend=top-left" />
 </picture>
</a>

## License

MIT - see [LICENSE](LICENSE).

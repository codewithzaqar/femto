"""
Configuration file parser for Femto.
Looks for ~/.femtorc or ./.femtorc
"""

import configparser
import copy
import fnmatch
import os
from pathlib import PurePosixPath


_EDITORCONFIG_PREAMBLE = "__editorconfig_preamble__"


def _read_editorconfig(path):
    parser = configparser.ConfigParser(
        interpolation=None,
        strict=False,
        delimiters=("=",),
        default_section="__editorconfig_default__",
    )
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()
        parser.read_string(
            f"[{_EDITORCONFIG_PREAMBLE}]\n{content}",
            source=path,
        )
    except (OSError, UnicodeError, configparser.Error):
        return None
    return parser


def _matches_editorconfig_section(section, filepath, config_path):
    relative = os.path.relpath(
        filepath,
        os.path.dirname(config_path),
    ).replace(os.sep, "/")
    pattern = section.strip().lstrip("/")

    if "/" in pattern:
        return PurePosixPath(relative).match(pattern)
    return fnmatch.fnmatchcase(os.path.basename(relative), pattern)


def _editorconfig_settings(filepath):
    if not filepath:
        return {}

    filepath = os.path.abspath(filepath)
    directory = os.path.dirname(filepath) or os.curdir
    files = []

    while True:
        path = os.path.join(directory, ".editorconfig")
        if os.path.isfile(path):
            parser = _read_editorconfig(path)
            if parser is not None:
                files.append((path, parser))
                root = parser.get(
                    _EDITORCONFIG_PREAMBLE,
                    "root",
                    fallback="false",
                    raw=True,
                )
                if root.strip().lower() == "true":
                    break

        parent = os.path.dirname(directory)
        if parent == directory:
            break
        directory = parent

    settings = {}
    for path, parser in reversed(files):
        for section in parser.sections():
            if section == _EDITORCONFIG_PREAMBLE:
                continue
            if not _matches_editorconfig_section(section, filepath, path):
                continue

            for key, value in parser.items(section, raw=True):
                key = key.strip().lower()
                value = value.strip()
                if value.lower() == "unset":
                    settings.pop(key, None)
                else:
                    settings[key] = value

    return settings



class Config:
    def __init__(self):
        self.tab_size = 4
        self.smooth_scroll_margin = 3
        self.soft_wrap = True
        self.ignore_case = False      
        self.regex_search = False 
        self.show_line_numbers = False   
        self.syntax_highlight = True
        self.mouse = False    
        self.make_backup = False
        self.line_ending = 'auto'
        self.final_newline = True
        self.auto_indent = True
        self.wrap_at_word = True
        self.system_clipboard = False
        self.autosave_seconds = 30
        self.restore_session = True
        self.git_gutter = False  # NEW: disabled by default
        self.load()

    def load(self):
        paths = [
            os.path.expanduser("~/.femtorc"),
            ".femtorc",
        ]
        for path in paths:
            if os.path.exists(path):
                self._parse(path)
                break

    def for_file(self, filepath):
        scoped = copy.copy(self)
        settings = _editorconfig_settings(filepath)

        indent_size = settings.get("indent_size")
        if indent_size and indent_size.lower() == "tab":
            indent_size = settings.get("tab_width")
        if indent_size:
            try:
                size = int(indent_size)
            except ValueError:
                pass
            else:
                if size > 0:
                    scoped.tab_size = size

        line_ending = settings.get("end_of_line", "").lower()
        if line_ending in ("lf", "crlf", "cr"):
            scoped.line_ending = line_ending

        final_newline = settings.get("insert_final_newline", "").lower()
        if final_newline in ("true", "false"):
            scoped.final_newline = final_newline == "true"

        return scoped

    def _parse(self, path):
        try:
            with open(path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue
                    if "=" in line:
                        key, val = line.split("=", 1)
                        key = key.strip()
                        val = val.strip()
                        if key == "tab_size":
                            self.tab_size = max(1, int(val))
                        elif key == "smooth_scroll_margin":
                            self.smooth_scroll_margin = max(0, int(val))
                        elif key == "soft_wrap":
                            self.soft_wrap = val.lower() in ("true", "1", "yes")
                        elif key == "ignore_case":
                            self.ignore_case = val.lower() in ("true", "1", "yes")
                        elif key == "regex_search":
                            self.regex_search = val.lower() in ("true", "1", "yes")
                        elif key == "show_line_numbers":
                            self.show_line_numbers = val.lower() in ("true", "1", "yes")
                        elif key == "syntax_highlight":
                            self.syntax_highlight = val.lower() in ("true", "1", "yes")
                        elif key == "mouse":
                            self.mouse = val.lower() in ("true", "1", "yes")
                        elif key == "make_backup":
                            self.make_backup = val.lower() in ("true", "1", "yes")
                        elif key == "line_ending":
                            if val in ("auto", "lf", "crlf", "cr"):
                                self.line_ending = val
                        elif key == "final_newline":
                            self.final_newline = val.lower() in ("true", "1", "yes")
                        elif key == "auto_indent":
                            self.auto_indent = val.lower() in ("true", "1", "yes")
                        elif key == "wrap_at_word":
                            self.wrap_at_word = val.lower() in ("true", "1", "yes")
                        elif key == "system_clipboard":
                            self.system_clipboard = val.lower() in ("true", "1", "yes")
                        elif key == "autosave_seconds":
                            self.autosave_seconds = int(val)
                        elif key == "restore_session":
                            self.restore_session = val.lower() in ("true", "1", "yes")
                        elif key == "git_gutter":
                            self.git_gutter = val.lower() in ("true", "1", "yes")
        except Exception:
            pass

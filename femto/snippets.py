"""
Snippet expansion for Femto (stdlib only).

Snippets live in an INI file (default ~/.config/femto/snippets.ini):

    [python]
    if = if $(1:condition):\\n    ${2:pass}

    [global]
    todo = TODO: ${1:description}

Tab stops use ${n} or ${n:placeholder} syntax. On expansion the
placeholders are inserted and selected one by one with Tab/Shift+Tab;
typing replaces the selected placeholder.
"""

import configparser
import os
import re

TAB_STOP_RE = re.compile(r"\$\{(\d+)(?::([^}]*))?\}")


class Snippet:
    def __init__(self, name, body):
        self.name = name
        self.body = body.replace("\\n", "\n").replace("\\t", "\t")
        self.stops = []
        for m in TAB_STOP_RE.finditer(self.body):
            self.stops.append((int(m.group(1)), m.group(2) or ""))
        self.stops.sort(key=lambda s: s[0])

    def plain_text(self):
        """Body with tab stops replaced by their placeholder text."""
        return TAB_STOP_RE.sub(lambda m: m.group(2) or "", self.body)

    def stop_positions(self):
        """Return [(offset, length)] of each tab stop inside plain_text()."""
        position = []
        for m in TAB_STOP_RE.finditer(self.body):
            prefix = self.body[:m.start()]
            plain_prefix = TAB_STOP_RE.sub(lambda mm: mm.group(2) or "", prefix)
            position.append((int(m.group(1)), len(plain_prefix),
                        len(m.group(2) or "")))
        position.sort(key=lambda p: p[0])
        return [(off, ln) for _, off, ln in position]


def default_snippets_path():
    home = os.path.expanduser("~")
    if os.name == "nt":
        base = os.environ.get("APPDATA", home)
        return os.path.join(base, "femto", "snippets.ini")
    return os.path.join(home, ".config", "femto", "snippets.ini")


DEFAULT_SNIPPETS = """[python]
if = if ${1:condition}:\\n    ${2:pass}
def = def ${1:name}(${2:args}):\\n    ${3:pass}
for = for ${1:item} in ${2:iterable}:\\n    ${3:pass}
class = class ${1:Name}:\\n    def __init__(self${2:, args}):\\n    ${3:pass}

[javascript]
fn = function ${1:name}(${2:args}) {\\n    ${3:}\\n}

[global]
todo = TODO: ${1:description}
"""


def load_snippets(path=None):
    """Return {filetype: {trigger: Snippet}}."""
    if path is None:
        path = default_snippets_path()
    parser = configparser.ConfigParser()
    if path and os.path.exists(path):
        try:
            parser.read(path, encoding="utf-8")
        except configparser.Error:
            return {}
    else:
        try:
            parser.read_string(DEFAULT_SNIPPETS)
        except configparser.Error:
            return {}
    result = {}
    for section in parser.sections():
        ftype = section.lower()
        result.setdefault(ftype, {})
        for trigger, body in parser.items(section):
            result[ftype][trigger] = Snippet(trigger, body)
    return result


def snippets_for_file(snippets, filename):
    """Merge global + filetype snippets for a filename."""
    ext_map = {
        ".py": "python", ".js": "javascript", ".ts": "javascript",
        ".jsx": "javascript", ".tsx": "javascript",
        ".c": "c", ".h": "c", ".cpp": "cpp", ".hpp": "cpp",
        ".md": "markdown", ".sh": "shell",
    }
    ext = os.path.splitext(filename or "")[1].lower()
    ftype = ext_map.get(ext, "")
    merged = dict(snippets.get("global", {}))
    merged.update(snippets.get(ftype, {}))
    return merged

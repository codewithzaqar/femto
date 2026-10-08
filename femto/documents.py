"""
Per-file document state for Femto multi-buffer editing.

Everything that belongs to ONE file lives here: text, cursor, undo
history, selection and search-match highlight.  The clipboard and
search options stay global (shared), like nano's cutbuffer.
"""

from femto.buffer import Buffer
from femto.cursor import Cursor
from femto.history import History
from femto.clipboard import Selection


class Document:
    """Bundles all per-file editor state."""

    def __init__(self, config, filename=None):
        file_config = config.for_file(filename) if filename else config
        self.buffer = Buffer(file_config)
        self.buffer.load_file(filename)
        self.cursor = Cursor()
        self.history = History()
        self.selection = Selection()
        self.last_match = None
        self.last_found_pos = None
        self.search_cache = None

    @property
    def filename(self):
        return self.buffer.filename

    @property
    def modified(self):
        return self.buffer.modified

"""Headless contracts for configurable, non-blocking error notifications."""

import curses
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from femto.app import Application, Mode
from femto.config import Config
from femto.renderer import Renderer


class TestNotificationConfig(unittest.TestCase):
    def setUp(self):
        self.loader = patch.object(Config, "load")
        self.loader.start()
        self.addCleanup(self.loader.stop)

    def test_defaults_are_silent_with_visual_feedback(self):
        config = Config()
        self.assertFalse(config.bell)
        self.assertTrue(config.visual_bell)

    def test_options_parse_independently(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "femtorc"
            filename.write_text("bell = yes\nvisual_bell = false\n")
            config = Config()
            config._parse(str(filename))
            self.assertTrue(config.bell)
            self.assertFalse(config.visual_bell)
            filename.write_text("bell = false\nvisual_bell = 1\n")
            config._parse(str(filename))
            self.assertFalse(config.bell)
            self.assertTrue(config.visual_bell)


class TestErrorNotifications(unittest.TestCase):
    def setUp(self):
        self.loader = patch.object(Config, "load")
        self.loader.start()
        self.addCleanup(self.loader.stop)
        self.clock = patch("femto.app.time.monotonic", return_value=10.0)
        self.now = self.clock.start()
        self.addCleanup(self.clock.stop)
        self.app = Application(None)
        self.app.config.autosave_seconds = 0
        self.app.config.restore_session = False
        self.app.buffer.lines = ["example text"]

    def test_visual_feedback_expires_after_100ms(self):
        self.app._notify_error("problem")
        self.assertEqual(self.app.message, "problem")
        self.assertTrue(self.app.visual_bell_active)
        self.assertLessEqual(self.app._input_timeout(), 100)
        self.now.return_value = 10.099
        self.assertTrue(self.app.visual_bell_active)
        self.now.return_value = 10.101
        self.assertFalse(self.app.visual_bell_active)
        self.assertEqual(self.app._input_timeout(), 1000)

    def test_repeated_error_restarts_deadline(self):
        self.app._notify_error("first")
        self.now.return_value = 10.09
        self.app._notify_error("second")
        self.now.return_value = 10.15
        self.assertTrue(self.app.visual_bell_active)
        self.now.return_value = 10.20
        self.assertFalse(self.app.visual_bell_active)

    def test_options_disabled_preserve_message_without_effects(self):
        self.app.config.bell = False
        self.app.config.visual_bell = False
        self.app.stdscr = Mock()
        with patch("femto.app.sys.stdout", new_callable=io.StringIO) as output:
            self.app._notify_error("problem")
            self.assertEqual(output.getvalue(), "")
        self.assertFalse(self.app.visual_bell_active)
        self.assertEqual(self.app.message, "problem")

    def test_audible_option_emits_one_bel(self):
        self.app.config.bell = True
        self.app.config.visual_bell = False
        self.app.stdscr = Mock()
        with patch("femto.app.sys.stdout", new_callable=io.StringIO) as output:
            self.app._notify_error("problem")
            self.assertEqual(output.getvalue(), "\a")
        self.assertFalse(self.app.visual_bell_active)

    def test_headless_application_does_not_write_bel(self):
        self.app.config.bell = True
        with patch("femto.app.sys.stdout", new_callable=io.StringIO) as output:
            self.app._notify_error("problem")
            self.assertEqual(output.getvalue(), "")

    def test_broken_bell_output_does_not_interrupt_editing(self):
        self.app.config.bell = True
        self.app.stdscr = Mock()
        with patch("femto.app.sys.stdout") as output:
            output.write.side_effect = OSError("output unavailable")
            self.app._notify_error("problem")
        self.assertEqual(self.app.message, "problem")
        self.assertTrue(self.app.visual_bell_active)

    def test_search_not_found_notifies(self):
        self.app.mode = Mode.SEARCH
        self.app.prompt.start("Search")
        self.app.prompt.insert("missing")
        self.app._commit_prompt()
        self.assertIn("Not found", self.app.message)
        self.assertTrue(self.app.visual_bell_active)
        self.assertEqual(self.app.mode, Mode.NORMAL)

    def test_successful_search_does_not_notify(self):
        self.app.mode = Mode.SEARCH
        self.app.prompt.start("Search")
        self.app.prompt.insert("example")
        self.app._commit_prompt()
        self.assertFalse(self.app.visual_bell_active)
        self.assertIsNotNone(self.app.last_match)

    def test_invalid_regex_search_keeps_prompt_and_text(self):
        self.app.search_options.regex = True
        self.app.mode = Mode.SEARCH
        self.app.prompt.start("Search")
        self.app.prompt.insert("[")
        before = self.app.buffer.lines[:]
        self.app._commit_prompt()
        self.assertEqual(self.app.message, "[bad regex]")
        self.assertTrue(self.app.visual_bell_active)
        self.assertEqual(self.app.mode, Mode.SEARCH)
        self.assertTrue(self.app.prompt.active)
        self.assertEqual(self.app.buffer.lines, before)

    def test_invalid_regex_replace_does_not_advance(self):
        self.app.search_options.regex = True
        self.app.mode = Mode.REPLACE_SEARCH
        self.app.prompt.start("Replace")
        self.app.prompt.insert("[")
        self.app._commit_prompt()
        self.assertEqual(self.app.mode, Mode.REPLACE_SEARCH)
        self.assertEqual(self.app.prompt.text, "[")
        self.assertTrue(self.app.visual_bell_active)
        self.assertFalse(self.app.buffer.modified)

    def test_invalid_live_regex_clears_stale_matches(self):
        self.app.search_options.regex = True
        self.app.mode = Mode.SEARCH
        self.app.prompt.start("Search")
        self.app.prompt.insert("[")
        self.app.all_matches = [(0, 0, 1)]
        self.app.last_match = (0, 0, 1)
        self.app._live_search_update()
        self.assertEqual(self.app.all_matches, [])
        self.assertIsNone(self.app.last_match)
        self.assertTrue(self.app.visual_bell_active)

    def test_plain_search_accepts_regex_metacharacters(self):
        self.app.buffer.lines = ["["]
        self.app.mode = Mode.SEARCH
        self.app.prompt.start("Search")
        self.app.prompt.insert("[")
        self.app._commit_prompt()
        self.assertFalse(self.app.visual_bell_active)
        self.assertIsNotNone(self.app.last_match)

    def test_unnamed_save_notifies_without_losing_save_as(self):
        self.app._save()
        self.assertEqual(self.app.mode, Mode.SAVE_AS)
        self.assertTrue(self.app.prompt.active)
        self.assertTrue(self.app.visual_bell_active)

    def test_empty_save_as_stays_open(self):
        self.app.mode = Mode.SAVE_AS
        self.app.prompt.start("Save As", "")
        self.app._commit_prompt()
        self.assertEqual(self.app.mode, Mode.SAVE_AS)
        self.assertTrue(self.app.prompt.active)
        self.assertTrue(self.app.visual_bell_active)
        self.assertIsNone(self.app.buffer.filename)

    def test_unchanged_existing_buffer_notifies_without_write(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "example.txt"
            filename.write_text("example text\n")
            self.app.open_file(str(filename))
            with patch.object(self.app.buffer, "save") as save:
                self.app._save()
                save.assert_not_called()
            self.assertEqual(self.app.message, "No changes to save.")
            self.assertTrue(self.app.visual_bell_active)
            self.assertEqual(filename.read_text(), "example text\n")

    def test_new_named_empty_file_is_created(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "new.txt"
            self.app.open_file(str(filename))
            self.app._save()
            self.assertTrue(filename.is_file())
            self.assertFalse(self.app.visual_bell_active)

    def test_explicit_save_as_still_writes_an_unmodified_buffer(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "target.txt"
            filename.write_text("old\n")
            self.app.mode = Mode.SAVE_AS
            self.app.prompt.start("Save As")
            self.app.prompt.insert(str(filename))
            self.app._commit_prompt()
            self.assertEqual(filename.read_text(), "example text\n")
            self.assertFalse(self.app.visual_bell_active)

    def test_trim_on_save_still_applies(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "trim.txt"
            filename.write_text("example text  \n")
            self.app.open_file(str(filename))
            self.app.config.trim_on_save = True
            self.app._save()
            self.assertEqual(filename.read_text(), "example text\n")
            self.assertFalse(self.app.visual_bell_active)

    def test_failed_save_notifies(self):
        self.app.buffer.filename = "unused.txt"
        self.app.buffer.touch()
        with patch.object(self.app.buffer, "save", return_value=False):
            self.app._save()
        self.assertIn("Error saving", self.app.message)
        self.assertTrue(self.app.visual_bell_active)

    def test_large_file_notifies_without_reading_or_overwriting(self):
        with tempfile.TemporaryDirectory() as directory:
            filename = Path(directory) / "large.txt"
            filename.write_text("untouched\n")
            with patch(
                "femto.buffer.os.path.getsize", return_value=50 * 1024 * 1024 + 1
            ):
                self.app.open_file(str(filename))
            self.assertIn("File too large", self.app.message)
            self.assertIsNone(self.app.buffer.filename)
            self.assertTrue(self.app.visual_bell_active)
            self.assertEqual(filename.read_text(), "untouched\n")

    def test_typing_during_flash_remains_responsive(self):
        self.app._notify_error("problem")
        self.app._handle_normal("Z", 24, 80)
        self.assertEqual(self.app.buffer.lines, ["Zexample text"])
        self.assertTrue(self.app.visual_bell_active)

    def test_slow_flash_frame_does_not_wait_for_full_idle_timeout(self):
        self.app.renderer = Mock()
        self.app._notify_error("problem")
        self.app.render()
        self.now.return_value = 10.2
        self.assertEqual(self.app._input_timeout(), 1)
        self.app.render()
        self.assertEqual(self.app._input_timeout(), 1000)
        self.assertFalse(self.app.renderer.render.call_args.kwargs["visual_bell"])

    def test_main_loop_restores_without_waiting_for_a_key(self):
        self.app.stdscr = Mock()
        self.app.renderer = Mock()
        self.app._notify_error("problem")
        reads = []

        def read_key():
            reads.append(self.app.stdscr.timeout.call_args.args[0])
            if len(reads) == 1:
                self.now.return_value = 10.101
            else:
                self.app.running = False
            return -1

        with patch.object(self.app, "_read_key", side_effect=read_key):
            self.app.main_loop()
        self.assertLessEqual(reads[0], 100)
        self.assertEqual(reads[1], 1000)
        rendered = self.app.renderer.render.call_args_list
        self.assertTrue(rendered[0].kwargs["visual_bell"])
        self.assertFalse(rendered[1].kwargs["visual_bell"])


class FakeWindow:
    def __init__(self):
        self.cursor = (1, 2)
        self.attrs = [
            [
                0,
                curses.A_BOLD | (curses.A_COLOR & -curses.A_COLOR),
                curses.A_REVERSE,
                curses.A_BOLD | curses.A_REVERSE,
            ]
            for _ in range(4)
        ]
        self.refresh_count = 0

    def getmaxyx(self):
        return (4, 4)

    def getyx(self):
        return self.cursor

    def inch(self, row, col):
        return ord("x") | self.attrs[row][col]

    def chgat(self, row, start, length, attr):
        for col in range(start, start + length):
            self.attrs[row][col] = attr
        self.cursor = (row, start)

    def move(self, row, col):
        self.cursor = (row, col)

    def erase(self):
        self.attrs = [[0] * 4 for _ in range(4)]

    def refresh(self):
        self.refresh_count += 1


class TestVisualNotificationRenderer(unittest.TestCase):
    def setUp(self):
        with patch.object(Config, "load"), patch.object(Renderer, "setup_colors"):
            self.window = FakeWindow()
            self.config = Config()
            self.renderer = Renderer(self.window, self.config)
            self.app = Application(None)

    def test_inversion_preserves_other_attributes_and_cursor(self):
        before = [row[:] for row in self.window.attrs]
        self.renderer._flash_screen()
        self.assertEqual(self.window.cursor, (1, 2))
        self.assertEqual(
            self.window.attrs,
            [[attr ^ curses.A_REVERSE for attr in row] for row in before],
        )

    def test_terminal_resize_error_does_not_escape(self):
        with patch.object(self.window, "inch", side_effect=curses.error):
            self.renderer._flash_screen()
        self.assertEqual(self.window.cursor, (1, 2))

    def test_flash_expiry_invalidates_render_cache(self):
        with patch.object(self.renderer, "draw_text"), patch.object(
            self.renderer, "draw_status_bar"
        ), patch.object(self.renderer, "draw_cursor"):
            self.renderer.render(self.app.buffer, self.app.cursor, visual_bell=True)
            self.assertTrue(
                all(
                    attr & curses.A_REVERSE for row in self.window.attrs for attr in row
                )
            )
            self.renderer.render(self.app.buffer, self.app.cursor, visual_bell=False)
            self.assertEqual(self.window.attrs, [[0] * 4 for _ in range(4)])
            self.assertEqual(self.window.refresh_count, 2)
            self.renderer.render(self.app.buffer, self.app.cursor, visual_bell=False)
            self.assertEqual(self.window.refresh_count, 2)


if __name__ == "__main__":
    unittest.main()

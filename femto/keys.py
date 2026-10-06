"""
Keybindings and input mapping for Femto.
"""

import curses

ALT_MASK = 0x1000


def alt(code):
    return code | ALT_MASK


def is_alt(key):
    return (key & ALT_MASK) != 0


def alt_code(key):
    return key & ~ALT_MASK


# Alt base letters used for line operations and Alt key translation.
ALT_BASES = "dtTsSuUlL"
CONHOST_ALT_MAP = {}


class Key:
    # Line operations (v0.0.4)
    ALT_D = alt(ord('d'))
    ALT_T = alt(ord('t'))
    ALT_S = alt(ord('s'))
    ALT_SHIFT_S = alt(ord('S'))
    ALT_U = alt(ord('u'))
    ALT_L = alt(ord('l'))

    # File / mode commands
    CTRL_X = 24
    CTRL_S = 19
    CTRL_G = 7

    # Navigation helpers
    CTRL_A = 1
    CTRL_E = 5

    # Search / goto / undo
    CTRL_W = 23
    CTRL_T = 20
    CTRL_Z = 26
    CTRL_Y = 25

    # Replace
    CTRL_BACKSLASH = 28
    CTRL_O = 15
    CTRL_R = 18

    # View toggles
    CTRL_N = 14
    CTRL_D = 4

    # Buffer switching (new in 0.0.2rc1)
    CTRL_F = 6
    CTRL_L = 12

    # Clipboard
    CTRL_K = 11
    CTRL_U = 21
    CTRL_B = 2
    CTRL_P = 16

    # Arrows
    ARROW_UP = curses.KEY_UP
    ARROW_DOWN = curses.KEY_DOWN
    ARROW_LEFT = curses.KEY_LEFT
    ARROW_RIGHT = curses.KEY_RIGHT

    # Word navigation
    CTRL_LEFT = curses.KEY_SLEFT
    CTRL_RIGHT = curses.KEY_SRIGHT

    # Page navigation
    PAGE_UP = curses.KEY_PPAGE
    PAGE_DOWN = curses.KEY_NPAGE

    # Home / End
    HOME = curses.KEY_HOME
    END = curses.KEY_END

    # Editing keys
    BACKSPACE = (curses.KEY_BACKSPACE, 127, 8)
    DELETE = curses.KEY_DC
    ENTER = (curses.KEY_ENTER, 10, 13)
    TAB = 9
    SHIFT_TAB = curses.KEY_BTAB

    # Terminal
    F1 = curses.KEY_F1
    RESIZE = curses.KEY_RESIZE
    ESCAPE = 27


def is_backspace(key):
    return key in Key.BACKSPACE


def is_enter(key):
    return key in Key.ENTER

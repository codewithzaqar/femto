"""Theme loading and color conversion for Femto."""

import configparser
import os
import re


_RGB_PATTERN = re.compile(r"rgb\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)", re.IGNORECASE)
_INDEX_PATTERN = re.compile(r"index\(\s*(\d+)\s*\)", re.IGNORECASE)
_HEX_PATTERN = re.compile(r"#([0-9a-f]{6})", re.IGNORECASE)


def parse_color(value):
    """Parse a theme color as RGB, an xterm color index, or the default color."""
    value = value.strip().lower()

    if value == "default":
        return None

    match = _HEX_PATTERN.fullmatch(value)
    if match:
        color = match.group(1)
        return tuple(int(color[i:i + 2], 16) for i in (0, 2, 4))

    match = _RGB_PATTERN.fullmatch(value)
    if match:
        rgb = tuple(int(component) for component in match.groups())
        if any(component > 255 for component in rgb):
            raise ValueError(f"RGB components must be between 0 and 255: {value}")
        return rgb

    match = _INDEX_PATTERN.fullmatch(value)
    if match:
        index = int(match.group(1))
        if index > 255:
            raise ValueError(f"Color index must be between 0 and 255: {value}")
        return index

    if value.isdigit():
        index = int(value)
        if index > 255:
            raise ValueError(f"Color index must be between 0 and 255: {value}")
        return index

    raise ValueError(f"Unsupported theme color: {value}")


def xterm_256_rgb(index):
    """Return the RGB value of an xterm-256 palette entry."""
    if not 0 <= index <= 255:
        raise ValueError("Color index must be between 0 and 255")

    base_colors = (
        (0, 0, 0),
        (205, 0, 0),
        (0, 205, 0),
        (205, 205, 0),
        (0, 0, 238),
        (205, 0, 205),
        (0, 205, 205),
        (229, 229, 229),
        (127, 127, 127),
        (255, 0, 0),
        (0, 255, 0),
        (255, 255, 0),
        (92, 92, 255),
        (255, 0, 255),
        (0, 255, 255),
        (255, 255, 255),
    )

    if index < 16:
        return base_colors[index]

    if index < 232:
        levels = (0, 95, 135, 175, 215, 255)
        index -= 16
        return (
            levels[index // 36],
            levels[(index % 36) // 6],
            levels[index % 6],
        )

    gray = 8 + (index - 232) * 10
    return (gray, gray, gray)


def nearest_xterm_256(rgb):
    """Find the xterm-256 color with the smallest squared RGB distance."""
    return min(
        range(16, 232),
        key=lambda index: sum(
            (component - palette_component) ** 2
            for component, palette_component in zip(rgb, xterm_256_rgb(index))
        ),
    )


def load_theme(theme_name="default"):
    """Load a named theme from Femto's themes directory."""
    if not re.fullmatch(r"[A-Za-z0-9_-]+", theme_name):
        raise ValueError(f"Invalid theme name: {theme_name}")

    theme_path = os.path.join(
        os.path.dirname(__file__), "themes", f"{theme_name}.ini"
    )

    parser = configparser.ConfigParser()
    if not parser.read(theme_path):
        raise FileNotFoundError(f"Theme file not found: {theme_path}")

    theme = {}
    for section in parser.sections():
        theme[section] = {}
        for key, value in parser.items(section):
            if key not in ("foreground", "background"):
                continue
            theme[section][key] = parse_color(value)

    return theme

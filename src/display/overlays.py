"""
display/overlays.py
===================
Draws overlays (path, portals, '42' highlight, HUD) into raw RGBA
pixel buffers.

All functions write into a bytearray of shape W × H × 4 (RGBA).
No external dependencies — pure Python pixel operations.
"""

import math
from .tiles import TILE_SIZE


# -- Colours -------------------------------------------------------

PATH_COLOR:      tuple[int, int, int, int] = (80,  160, 255, 160)
PATTERN42_COLOR: tuple[int, int, int, int] = (255, 200, 0,   80)
HUD_BG:          tuple[int, int, int]       = (22,  22,  28)
HUD_LINE:        tuple[int, int, int]       = (55,  60,  78)

ENTRY_RINGS: list[tuple[int, int, int]] = [
    (0,   120, 55),
    (0,   160, 75),
    (20,  200, 95),
    (80,  235, 130),
    (150, 255, 175),
]
EXIT_RINGS: list[tuple[int, int, int]] = [
    (130, 30,  0),
    (170, 55,  10),
    (200, 80,  15),
    (230, 115, 35),
    (255, 170, 80),
]
PORTAL_RADII: list[int] = [14, 10, 7, 4, 2]

HUD_H: int = 46


# -- Pixel primitives -------------------------------------------------------

def _put(
    buf: bytearray,
    x: int,
    y: int,
    r: int,
    g: int,
    b: int,
    a: int,
    width: int,
    height: int,
) -> None:
    """Write one RGBA pixel, clipping to buffer bounds.

    Args:
        buf:    Target RGBA bytearray (row-major, 4 bytes/pixel).
        x:      Column.
        y:      Row.
        r:      Red (0–255).
        g:      Green (0–255).
        b:      Blue (0–255).
        a:      Alpha (0–255, 255 = opaque).
        width:  Buffer width in pixels.
        height: Buffer height in pixels.
    """
    if not (0 <= x < width and 0 <= y < height):
        return
    i = (y * width + x) * 4
    buf[i]     = r
    buf[i + 1] = g
    buf[i + 2] = b
    buf[i + 3] = a


def _blend(
    buf: bytearray,
    x: int,
    y: int,
    r: int,
    g: int,
    b: int,
    a: int,
    width: int,
    height: int,
) -> None:
    """Alpha-blend one pixel over the existing colour in the buffer.

    Uses standard over-compositing: out = src*alpha + dst*(1-alpha).

    Args:
        buf:    Target RGBA bytearray.
        x:      Column.
        y:      Row.
        r:      Source red.
        g:      Source green.
        b:      Source blue.
        a:      Source alpha (0–255).
        width:  Buffer width.
        height: Buffer height.
    """
    if not (0 <= x < width and 0 <= y < height):
        return
    if a == 0:
        return
    i  = (y * width + x) * 4
    t  = a / 255.0
    buf[i]     = int(r * t + buf[i]     * (1 - t))
    buf[i + 1] = int(g * t + buf[i + 1] * (1 - t))
    buf[i + 2] = int(b * t + buf[i + 2] * (1 - t))
    buf[i + 3] = 255


def _fill_rect_buf(
    buf: bytearray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    r: int,
    g: int,
    b: int,
    a: int,
    width: int,
    height: int,
) -> None:
    """Alpha-blend a filled rectangle into the buffer.

    Args:
        buf:    Target RGBA bytearray.
        x0:     Left column (inclusive).
        y0:     Top row (inclusive).
        x1:     Right column (exclusive).
        y1:     Bottom row (exclusive).
        r:      Red.
        g:      Green.
        b:      Blue.
        a:      Alpha.
        width:  Buffer width.
        height: Buffer height.
    """
    for y in range(max(0, y0), min(height, y1)):
        for x in range(max(0, x0), min(width, x1)):
            _blend(buf, x, y, r, g, b, a, width, height)


def _fill_circle(
    buf: bytearray,
    cx: int,
    cy: int,
    radius: int,
    r: int,
    g: int,
    b: int,
    a: int,
    width: int,
    height: int,
) -> None:
    """Alpha-blend a filled circle into the buffer.

    Args:
        buf:    Target RGBA bytearray.
        cx:     Centre column.
        cy:     Centre row.
        radius: Circle radius in pixels.
        r:      Red.
        g:      Green.
        b:      Blue.
        a:      Alpha.
        width:  Buffer width.
        height: Buffer height.
    """
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                _blend(buf, x, y, r, g, b, a, width, height)


def _draw_text(
    buf: bytearray,
    x: int,
    y: int,
    text: str,
    color: tuple[int, int, int],
    width: int,
    height: int,
) -> int:
    """Draw ASCII text using a minimal 5×7 bitmap font.

    Args:
        buf:    Target RGBA bytearray.
        x:      Left pixel of the first character.
        y:      Top pixel of the text.
        text:   String to draw.
        color:  RGB colour.
        width:  Buffer width.
        height: Buffer height.

    Returns:
        x position just past the last drawn character.
    """
    r, g, b = color
    cx = x
    for ch in text:
        bits = _FONT.get(ch, _FONT.get(" ", []))
        for row, byte in enumerate(bits):
            for col in range(5):
                if byte & (1 << (4 - col)):
                    _put(buf, cx + col, y + row, r, g, b, 255, width, height)
        cx += 6   # 5px char + 1px gap
    return cx


# -- Minimal 5×7 bitmap font (printable ASCII subset) ----------------------
# Each character is 7 bytes; each byte is a 5-bit row bitmask.
# Generated from a standard 5x7 pixel font — no copyright applies to
# simple bitmap glyph data of this kind.

_FONT: dict[str, list[int]] = {
    " ": [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00],
    "!": [0x04, 0x04, 0x04, 0x04, 0x00, 0x04, 0x00],
    "#": [0x0A, 0x1F, 0x0A, 0x0A, 0x1F, 0x0A, 0x00],
    "%": [0x18, 0x19, 0x02, 0x04, 0x09, 0x03, 0x00],
    "+": [0x00, 0x04, 0x04, 0x1F, 0x04, 0x04, 0x00],
    "-": [0x00, 0x00, 0x00, 0x1F, 0x00, 0x00, 0x00],
    ".": [0x00, 0x00, 0x00, 0x00, 0x00, 0x04, 0x00],
    "/": [0x01, 0x01, 0x02, 0x04, 0x08, 0x10, 0x00],
    ":": [0x00, 0x04, 0x00, 0x00, 0x04, 0x00, 0x00],
    "=": [0x00, 0x1F, 0x00, 0x1F, 0x00, 0x00, 0x00],
    "?": [0x0E, 0x11, 0x02, 0x04, 0x00, 0x04, 0x00],
    "0": [0x0E, 0x11, 0x13, 0x15, 0x19, 0x11, 0x0E],
    "1": [0x04, 0x0C, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "2": [0x0E, 0x11, 0x01, 0x06, 0x08, 0x10, 0x1F],
    "3": [0x1F, 0x02, 0x04, 0x02, 0x01, 0x11, 0x0E],
    "4": [0x02, 0x06, 0x0A, 0x12, 0x1F, 0x02, 0x02],
    "5": [0x1F, 0x10, 0x1E, 0x01, 0x01, 0x11, 0x0E],
    "6": [0x06, 0x08, 0x10, 0x1E, 0x11, 0x11, 0x0E],
    "7": [0x1F, 0x01, 0x02, 0x04, 0x08, 0x08, 0x08],
    "8": [0x0E, 0x11, 0x11, 0x0E, 0x11, 0x11, 0x0E],
    "9": [0x0E, 0x11, 0x11, 0x0F, 0x01, 0x02, 0x0C],
    "A": [0x0E, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "B": [0x1E, 0x11, 0x11, 0x1E, 0x11, 0x11, 0x1E],
    "C": [0x0E, 0x11, 0x10, 0x10, 0x10, 0x11, 0x0E],
    "D": [0x1C, 0x12, 0x11, 0x11, 0x11, 0x12, 0x1C],
    "E": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x1F],
    "F": [0x1F, 0x10, 0x10, 0x1E, 0x10, 0x10, 0x10],
    "G": [0x0E, 0x11, 0x10, 0x17, 0x11, 0x11, 0x0F],
    "H": [0x11, 0x11, 0x11, 0x1F, 0x11, 0x11, 0x11],
    "I": [0x0E, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "J": [0x07, 0x02, 0x02, 0x02, 0x12, 0x12, 0x0C],
    "K": [0x11, 0x12, 0x14, 0x18, 0x14, 0x12, 0x11],
    "L": [0x10, 0x10, 0x10, 0x10, 0x10, 0x10, 0x1F],
    "M": [0x11, 0x1B, 0x15, 0x15, 0x11, 0x11, 0x11],
    "N": [0x11, 0x19, 0x15, 0x13, 0x11, 0x11, 0x11],
    "O": [0x0E, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "P": [0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10, 0x10],
    "Q": [0x0E, 0x11, 0x11, 0x11, 0x15, 0x12, 0x0D],
    "R": [0x1E, 0x11, 0x11, 0x1E, 0x14, 0x12, 0x11],
    "S": [0x0E, 0x11, 0x10, 0x0E, 0x01, 0x11, 0x0E],
    "T": [0x1F, 0x04, 0x04, 0x04, 0x04, 0x04, 0x04],
    "U": [0x11, 0x11, 0x11, 0x11, 0x11, 0x11, 0x0E],
    "V": [0x11, 0x11, 0x11, 0x11, 0x11, 0x0A, 0x04],
    "W": [0x11, 0x11, 0x15, 0x15, 0x15, 0x0A, 0x0A],
    "X": [0x11, 0x11, 0x0A, 0x04, 0x0A, 0x11, 0x11],
    "Y": [0x11, 0x11, 0x0A, 0x04, 0x04, 0x04, 0x04],
    "Z": [0x1F, 0x01, 0x02, 0x04, 0x08, 0x10, 0x1F],
    "a": [0x00, 0x00, 0x0E, 0x01, 0x0F, 0x11, 0x0F],
    "b": [0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x1E],
    "c": [0x00, 0x00, 0x0E, 0x10, 0x10, 0x11, 0x0E],
    "d": [0x01, 0x01, 0x0F, 0x11, 0x11, 0x11, 0x0F],
    "e": [0x00, 0x00, 0x0E, 0x11, 0x1F, 0x10, 0x0E],
    "f": [0x06, 0x09, 0x08, 0x1C, 0x08, 0x08, 0x08],
    "g": [0x00, 0x0F, 0x11, 0x11, 0x0F, 0x01, 0x0E],
    "h": [0x10, 0x10, 0x1E, 0x11, 0x11, 0x11, 0x11],
    "i": [0x04, 0x00, 0x0C, 0x04, 0x04, 0x04, 0x0E],
    "j": [0x02, 0x00, 0x06, 0x02, 0x02, 0x12, 0x0C],
    "k": [0x10, 0x10, 0x12, 0x14, 0x18, 0x14, 0x12],
    "l": [0x0C, 0x04, 0x04, 0x04, 0x04, 0x04, 0x0E],
    "m": [0x00, 0x00, 0x1A, 0x15, 0x15, 0x11, 0x11],
    "n": [0x00, 0x00, 0x1E, 0x11, 0x11, 0x11, 0x11],
    "o": [0x00, 0x00, 0x0E, 0x11, 0x11, 0x11, 0x0E],
    "p": [0x00, 0x1E, 0x11, 0x11, 0x1E, 0x10, 0x10],
    "q": [0x00, 0x0F, 0x11, 0x11, 0x0F, 0x01, 0x01],
    "r": [0x00, 0x00, 0x16, 0x19, 0x10, 0x10, 0x10],
    "s": [0x00, 0x00, 0x0E, 0x10, 0x0E, 0x01, 0x1E],
    "t": [0x08, 0x08, 0x1C, 0x08, 0x08, 0x09, 0x06],
    "u": [0x00, 0x00, 0x11, 0x11, 0x11, 0x11, 0x0F],
    "v": [0x00, 0x00, 0x11, 0x11, 0x11, 0x0A, 0x04],
    "w": [0x00, 0x00, 0x11, 0x15, 0x15, 0x15, 0x0A],
    "x": [0x00, 0x00, 0x11, 0x0A, 0x04, 0x0A, 0x11],
    "y": [0x00, 0x11, 0x11, 0x0F, 0x01, 0x11, 0x0E],
    "z": [0x00, 0x00, 0x1F, 0x02, 0x04, 0x08, 0x1F],
    "[": [0x06, 0x04, 0x04, 0x04, 0x04, 0x04, 0x06],
    "]": [0x06, 0x02, 0x02, 0x02, 0x02, 0x02, 0x06],
    "x": [0x00, 0x00, 0x11, 0x0A, 0x04, 0x0A, 0x11],
}


# -- Path overlay -------------------------------------------------------

def draw_path(
    buf: bytearray,
    path: list[tuple[int, int]],
    offset_x: int,
    offset_y: int,
    tile_px: int,
    width: int,
    height: int,
) -> None:
    """Draw the solution path as half-cell strips into the buffer.

    Each cell draws coloured strips only toward its neighbours in the
    path. Adjacent half-strips join at passage openings to form a
    continuous corridor through the maze.

    Args:
        buf:      Target RGBA bytearray.
        path:     Ordered list of (row, col) solution cells.
        offset_x: Pixel x of the maze top-left corner.
        offset_y: Pixel y of the maze top-left corner.
        tile_px:  Current tile size in pixels.
        width:    Buffer width.
        height:   Buffer height.
    """
    if not path:
        return

    pr, pg, pb, pa = PATH_COLOR
    half  = tile_px // 2
    strip = max(4, tile_px // 6)
    h     = strip // 2

    for i, (r, c) in enumerate(path):
        px = c * tile_px + offset_x
        py = r * tile_px + offset_y
        cx = px + half
        cy = py + half

        dirs: list[str] = []
        if i > 0:
            pr2, pc2 = path[i - 1]
            dr, dc = r - pr2, c - pc2
            if dr == -1:   dirs.append("N")
            elif dr == 1:  dirs.append("S")
            elif dc == -1: dirs.append("W")
            elif dc == 1:  dirs.append("E")
        if i < len(path) - 1:
            nr, nc = path[i + 1]
            dr2, dc2 = nr - r, nc - c
            if dr2 == -1:   dirs.append("N")
            elif dr2 == 1:  dirs.append("S")
            elif dc2 == -1: dirs.append("W")
            elif dc2 == 1:  dirs.append("E")

        for d in dirs:
            if d == "N":
                _fill_rect_buf(buf, cx-h, py,    cx+h, cy,    pr, pg, pb, pa, width, height)
            elif d == "S":
                _fill_rect_buf(buf, cx-h, cy,    cx+h, py+tile_px, pr, pg, pb, pa, width, height)
            elif d == "W":
                _fill_rect_buf(buf, px,   cy-h,  cx,   cy+h, pr, pg, pb, pa, width, height)
            elif d == "E":
                _fill_rect_buf(buf, cx,   cy-h,  px+tile_px, cy+h, pr, pg, pb, pa, width, height)

        _fill_circle(buf, cx, cy, h + 1, pr, pg, pb, pa, width, height)


# -- Portal drawing -------------------------------------------------------

def draw_portal(
    buf: bytearray,
    cx: int,
    cy: int,
    rings: list[tuple[int, int, int]],
    arrow_up: bool,
    width: int,
    height: int,
) -> None:
    """Draw a glowing portal with concentric rings and a directional arrow.

    Args:
        buf:      Target RGBA bytearray.
        cx:       Centre column pixel.
        cy:       Centre row pixel.
        rings:    RGB colours for rings, outer to inner.
        arrow_up: True = exit (arrow points up), False = entry (down).
        width:    Buffer width.
        height:   Buffer height.
    """
    for radius, col in zip(PORTAL_RADII, rings):
        _fill_circle(buf, cx, cy, radius, *col, 220, width, height)

    ar, ag, ab = (220, 255, 225) if not arrow_up else (255, 235, 190)
    if arrow_up:
        for dy in range(-3, 7):
            _put(buf, cx - 1, cy + dy, ar, ag, ab, 255, width, height)
            _put(buf, cx,     cy + dy, ar, ag, ab, 255, width, height)
        for i in range(6):
            for dx in range(-5 + i, 6 - i):
                _put(buf, cx + dx, cy - 3 - i, ar, ag, ab, 255, width, height)
    else:
        for dy in range(-6, 4):
            _put(buf, cx - 1, cy + dy, ar, ag, ab, 255, width, height)
            _put(buf, cx,     cy + dy, ar, ag, ab, 255, width, height)
        for i in range(6):
            for dx in range(-5 + i, 6 - i):
                _put(buf, cx + dx, cy + 3 + i, ar, ag, ab, 255, width, height)


# -- '42' highlight -------------------------------------------------------

def draw_42_highlight(
    buf: bytearray,
    cells: set[tuple[int, int]],
    offset_x: int,
    offset_y: int,
    tile_px: int,
    width: int,
    height: int,
) -> None:
    """Draw a golden highlight over the '42' pattern cells.

    Args:
        buf:      Target RGBA bytearray.
        cells:    Set of (row, col) cells to highlight.
        offset_x: Pixel x of the maze top-left corner.
        offset_y: Pixel y of the maze top-left corner.
        tile_px:  Current tile size in pixels.
        width:    Buffer width.
        height:   Buffer height.
    """
    pr, pg, pb, pa = PATTERN42_COLOR
    for r, c in cells:
        x0 = c * tile_px + offset_x
        y0 = r * tile_px + offset_y
        _fill_rect_buf(
            buf, x0, y0, x0 + tile_px, y0 + tile_px,
            pr, pg, pb, pa, width, height,
        )


# -- HUD -------------------------------------------------------

def draw_hud(
    buf: bytearray,
    width: int,
    height: int,
    theme_name: str,
    show_path: bool,
    show_42: bool,
    cols: int,
    rows: int,
    zoom: float,
    filename: str,
) -> None:
    """Draw the top HUD bar with status indicators and control hints.

    Args:
        buf:        Target RGBA bytearray.
        width:      Buffer width.
        height:     Buffer height.
        theme_name: Name of the active colour theme.
        show_path:  Whether the path overlay is active.
        show_42:    Whether the '42' highlight is active.
        cols:       Maze column count.
        rows:       Maze row count.
        zoom:       Current zoom level.
        filename:   Base filename of the loaded maze (shown in HUD).
    """
    # Background
    _fill_rect_buf(buf, 0, 0, width, HUD_H,
                   *HUD_BG, 255, width, height)
    # Bottom divider line
    for x in range(width):
        _put(buf, x, HUD_H - 1, *HUD_LINE, 255, width, height)

    txt  = (195, 200, 215)
    acc  = (100, 180, 255)
    on_c = (75,  215, 80)
    gold = (255, 200, 55)
    warn = (200,  90, 90)

    zoom_str   = f"{zoom:.1f}"
    path_state = "ON" if show_path else "OFF"
    p42_state  = "ON" if show_42 else "OFF"

    items: list[tuple[str, tuple[int, int, int]]] = [
        (filename,                                         txt),
        (f"{cols}x{rows}",                                 txt),
        (f"[SPC] Path:{path_state} ", on_c if show_path else txt),
        (f" [C] {theme_name} ",                              acc),
        (f" [4] 42:{p42_state} ",       gold if show_42 else txt),
        (" [+/-] Zoom ",                                     txt),
        (f"{zoom_str}x",                                 txt),
        ("[ESC] Quit",                                    warn),
    ]

    cx = 10
    cy = (HUD_H - 7) // 2   # vertically centre 7px tall text
    for text, color in items:
        cx = _draw_text(buf, cx, cy, text, color, width, height)
        cx += 8
        if cx > width - 80:
            break

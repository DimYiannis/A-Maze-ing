"""
    display/tiles.py

    renders all 16 hex maze tiles as RGBA bytearrays — no external libs.
    Each tile is TILE_SIZE × TILE_SIZE pixels, stored as a flat bytearray
    of R, G, B, A bytes in row-major order.

    tile wall encoding (same as the maze file):
        Bit 0 (LSB) = North wall
        Bit 1       = East  wall
        Bit 2       = South wall
        Bit 3       = West  wall
"""

from typing import NamedTuple

# sizes

TILE_SIZE: int = 64  # tile width and height in pixels
WALL: int = 15  # wall strip thickness in pixels

# colour themes


class Theme(NamedTuple):
    """
        A wall colour theme.

        attributes:
            name:     display name for the HUD.
            floor:    RGB of the passage floor.
            wall:     RGB of the wall face.
            wall_hi:  RGB of the inner edge highlight line.
    """

    name: str
    floor: tuple[int, int, int]
    wall: tuple[int, int, int]
    wall_hi: tuple[int, int, int]


THEMES: list[Theme] = [
    Theme("Grey", (50, 50, 53), (150, 157, 167), (190, 198, 210)),
    Theme("Brown", (50, 50, 53), (100, 80, 60), (140, 115, 88)),
    Theme("Blue", (50, 50, 53), (140, 175, 210), (200, 225, 245)),
    Theme("Orange", (50, 50, 53), (160, 70, 20), (220, 120, 40)),
    Theme("Green", (50, 50, 53), (70, 105, 55), (105, 145, 80)),
]

#  Drawing primitives


def _fill(
    buf: bytearray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
) -> None:
    """
        fill a rectangle with a solid opaque colour.

        args:
            buf:   Target bytearray (RGBA, TILE_SIZE stride).
            x0:    Left column (inclusive).
            y0:    Top row (inclusive).
            x1:    Right column (exclusive).
            y1:    Bottom row (exclusive).
            color: RGB tuple.
    """
    r, g, b = color  # tuple unpacking
    row = bytes([r, g, b, 255] * (x1 - x0))  # build one row of pixels at once
    for y in range(y0, y1):
        i = (y * TILE_SIZE + x0) * 4  # calc start index
        buf[i: i + len(row)] = row  # copy whole row


# tile rendering


def render_tile(hv: int, theme: Theme) -> bytearray:
    """
        render a single maze tile as a flat RGBA bytearray.

        each wall is drawn as a solid strip with a small bright line

        args:
            hv:    hex value (0–15) showing which walls are closed.
            theme: color theme.

        returns:
            bytearray of length TILE_SIZE × TILE_SIZE × 4.
    """
    T = TILE_SIZE
    wt = WALL
    n = (hv >> 0) & 1
    e = (hv >> 1) & 1
    s = (hv >> 2) & 1
    w = (hv >> 3) & 1

    buf = bytearray(T * T * 4)

    # floor
    _fill(buf, 0, 0, T, T, theme.floor)

    # walls
    if n:
        _fill(buf, 0, 0, T, wt, theme.wall)
        _fill(buf, 0, wt, T, wt + 2, theme.wall_hi)  # inner edge
    if s:
        _fill(buf, 0, T - wt, T, T, theme.wall)
        #              x0    y0      x1   y1    color
        _fill(buf, 0, T - wt - 2, T, T - wt, theme.wall_hi)
    if e:
        _fill(buf, T - wt, 0, T, T, theme.wall)
        _fill(buf, T - wt - 2, 0, T - wt, T, theme.wall_hi)
    if w:
        _fill(buf, 0, 0, wt, T, theme.wall)
        _fill(buf, wt, 0, wt + 2, T, theme.wall_hi)
    return buf


def build_tile_cache(theme: Theme) -> dict[int, bytearray]:
    """
        build all 16 tiles for the given theme.
        save time to make them once and save them
        than building them over and over again

        args:
            class of the theme color for maze

        returns:
            dict with all the tile.
    """
    return {hv: render_tile(hv, theme) for hv in range(16)}

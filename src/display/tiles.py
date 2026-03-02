"""
    display/tiles.py

    renders all 16 hex maze tiles as RGBA bytearrays — no external libs.

    each tile is TILE_SIZE × TILE_SIZE pixels, stored as a flat bytearray
    of R, G, B, A bytes in row-major order.

    this format is compatible with mlx_image_t.pixels (MLX42).
    call build_tile_cache() to get all 16 pre-rendered tiles at once.

    tile wall encoding (same as the maze file):
        bit 0 (LSB) = North wall
        bit 1       = East  wall
        bit 2       = South wall
        bit 3       = West  wall

    Visual style:
        - Floor: flat dark colour, no texture
        - Walls: smooth light colour with a soft brightness bevel on edges
        - No brick lines, no grout
"""

import random
from typing import NamedTuple


# -- Sizes -------------------------------------------------------

TILE_SIZE: int = 64   # tile width and height in pixels
WALL_T:    int = 22   # wall strip thickness in pixels

# -- Bit masks -------------------------------------------------------

N_BIT: int = 0b0001
E_BIT: int = 0b0010
S_BIT: int = 0b0100
W_BIT: int = 0b1000


# -- Colour themes -------------------------------------------------------

class Theme(NamedTuple):
    """
    wall colour theme using pseudo-3D shading

    attributes:
        name:        Display name for the HUD.
        floor:       RGB of the passage floor.
        wall:        RGB of the wall face.
        wall_hi:     RGB of the bright bevel edge.
        wall_shadow: RGB of the dark bevel edge.
    """
    name:        str
    floor:       tuple[int, int, int]
    wall:        tuple[int, int, int]
    wall_hi:     tuple[int, int, int]
    wall_shadow: tuple[int, int, int]


THEMES: list[Theme] = [
    Theme("Grey",   (50,  50,  53),  (150, 157, 167), (190, 198, 210), (100, 106, 116)),
    Theme("Brown", (30,  28,  35),  (100,  80,  60), (140, 115,  88), ( 60,  48,  36)),
    Theme("Blue",     (20,  30,  45),  (140, 175, 210), (200, 225, 245), ( 80, 115, 155)),
    Theme("Orange",    (25,  15,  10),  (160,  70,  20), (220, 120,  40), ( 90,  35,  10)),
    Theme("Green",  (20,  28,  18),  ( 70, 105,  55), (105, 145,  80), ( 38,  58,  28)),
]


# -- Drawing primitives -------------------------------------------------------

def _put(
    buf: bytearray,
    x: int,
    y: int,
    r: int,
    g: int,
    b: int,
    stride: int = TILE_SIZE,
) -> None:
    """
        write one opaque RGBA pixel into a bytearray buffer.

        args:
            buf:    Target bytearray (RGBA, row-major).
            x:      Pixel column.
            y:      Pixel row.
            r:      Red channel (0–255).
            g:      Green channel (0–255).
            b:      Blue channel (0–255).
            stride: Row width in pixels (default TILE_SIZE).
    """
    i = (y * stride + x) * 4
    buf[i]     = r
    buf[i + 1] = g
    buf[i + 2] = b
    buf[i + 3] = 255


def _fill_rect(
    buf: bytearray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    color: tuple[int, int, int],
) -> None:
    """
        fill a rectangle with a solid colour.

        args:
            buf:   Target bytearray (RGBA, TILE_SIZE stride).
            x0:    Left column (inclusive).
            y0:    Top row (inclusive).
            x1:    Right column (exclusive).
            y1:    Bottom row (exclusive).
            color: RGB tuple.
    """
    r, g, b = color
    for y in range(y0, y1):
        for x in range(x0, x1):
            _put(buf, x, y, r, g, b)


def _lerp_color(
    a: tuple[int, int, int],
    b: tuple[int, int, int],
    t: float,
) -> tuple[int, int, int]:
    """
    linearly interpolate between two RGB colours.

    args:
        a: Start colour.
        b: End colour.
        t: Blend factor in [0.0, 1.0] (0 = a, 1 = b).

    returns:
        interpolated RGB tuple.
    """
    return (
        int(a[0] + (b[0] - a[0]) * t),
        int(a[1] + (b[1] - a[1]) * t),
        int(a[2] + (b[2] - a[2]) * t),
    )


def _noisy_fill(
    buf: bytearray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    base: tuple[int, int, int],
    strength: int,
    rng: random.Random,
) -> None:
    """
        fill a rectangle with per-pixel random brightness noise.

        args:
            buf:      Target bytearray.
            x0:       Left column (inclusive).
            y0:       Top row (inclusive).
            x1:       Right column (exclusive).
            y1:       Bottom row (exclusive).
            base:     Base RGB colour.
            strength: Max noise magnitude per channel (±).
            rng:      Random instance for reproducibility.
    """
    br, bg, bb = base
    for y in range(y0, y1):
        for x in range(x0, x1):
            n = rng.randint(-strength, strength)
            _put(buf, x, y,
                 max(0, min(255, br + n)),
                 max(0, min(255, bg + n)),
                 max(0, min(255, bb + n)))


def _bevel(
    buf: bytearray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    base: tuple[int, int, int],
    hi: tuple[int, int, int],
    shadow: tuple[int, int, int],
    depth: int = 5,
) -> None:
    """
        apply a soft bevel gradient on all four edges of a rectangle.

        the top and left edges fade toward hi, the bottom and right toward
        shadow. The effect gives depth to flat wall strips without hard lines.

        args:
            buf:    Target bytearray.
            x0:     Left column (inclusive).
            y0:     Top row (inclusive).
            x1:     Right column (exclusive).
            y1:     Bottom row (exclusive).
            base:   Base wall colour (already drawn in the rectangle).
            hi:     Bright highlight colour.
            shadow: Dark shadow colour.
            depth:  Number of pixels the gradient extends inward.
    """
    for i in range(depth):
        t = (1.0 - i / depth) * 0.7
        hc = _lerp_color(base, hi, t)
        sc = _lerp_color(base, shadow, t)
        # top edge → highlight
        if y0 + i < y1:
            for x in range(x0, x1):
                _put(buf, x, y0 + i, *hc)
        # bottom edge → shadow
        if y1 - 1 - i >= y0:
            for x in range(x0, x1):
                _put(buf, x, y1 - 1 - i, *sc)
        # left edge → highlight
        if x0 + i < x1:
            for y in range(y0, y1):
                _put(buf, x0 + i, y, *hc)
        # right edge → shadow
        if x1 - 1 - i >= x0:
            for y in range(y0, y1):
                _put(buf, x1 - 1 - i, y, *sc)


# -- Tile rendering -------------------------------------------------------

def _draw_wall_strip(
    buf: bytearray,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    theme: Theme,
    seed: int,
) -> None:
    """
        draw one wall strip (or corner fill) into the tile buffer.

        first fills with noisy base colour, then applies a soft bevel.

        args:
            buf:   RGBA bytearray of size TILE_SIZE × TILE_SIZE × 4.
            x0:    Left column (inclusive).
            y0:    Top row (inclusive).
            x1:    Right column (exclusive).
            y1:    Bottom row (exclusive).
            theme: Active colour theme.
            seed:  Noise seed — keeps textures reproducible per tile.
    """
    if x1 <= x0 or y1 <= y0:
        return
    rng = random.Random(seed)
    _noisy_fill(buf, x0, y0, x1, y1, theme.wall, 5, rng)
    _bevel(buf, x0, y0, x1, y1, theme.wall, theme.wall_hi, theme.wall_shadow)


def render_tile(hv: int, theme: Theme) -> bytearray:
    """
        render a single maze tile as a flat RGBA bytearray.

        args:
            hv:    Hex value (0–15) encoding which walls are closed.
            theme: Active colour theme.

        return:
            bytearray of length TILE_SIZE × TILE_SIZE × 4 (RGBA, row-major).
    """
    T  = TILE_SIZE
    wt = WALL_T
    n  = (hv >> 0) & 1
    e  = (hv >> 1) & 1
    s  = (hv >> 2) & 1
    w  = (hv >> 3) & 1

    buf = bytearray(T * T * 4)

    # Floor fills the whole tile first
    _fill_rect(buf, 0, 0, T, T, theme.floor)

    # Seed offset keeps each wall strip independently textured
    sd = hv * 37
    if n:
        _draw_wall_strip(buf, 0,    0,    T,    wt,  theme, sd + 1)
    if s:
        _draw_wall_strip(buf, 0,    T-wt, T,    T,   theme, sd + 2)
    if e:
        _draw_wall_strip(buf, T-wt, 0,    T,    T,   theme, sd + 3)
    if w:
        _draw_wall_strip(buf, 0,    0,    wt,   T,   theme, sd + 4)

    # Corner fills — where two wall strips meet
    if n and w:
        _draw_wall_strip(buf, 0,    0,    wt,   wt,  theme, sd + 5)
    if n and e:
        _draw_wall_strip(buf, T-wt, 0,    T,    wt,  theme, sd + 6)
    if s and w:
        _draw_wall_strip(buf, 0,    T-wt, wt,   T,   theme, sd + 7)
    if s and e:
        _draw_wall_strip(buf, T-wt, T-wt, T,    T,   theme, sd + 8)

    return buf


def build_tile_cache(theme: Theme) -> dict[int, bytearray]:
    """
        pre-render all 16 tiles for the given theme.

        args:
            theme: Active colour theme.

        returns:
        dict mapping hex value 0–15 to an RGBA bytearray.
    """
    return {hv: render_tile(hv, theme) for hv in range(16)}

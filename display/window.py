"""
display/window.py

    MazeDisplay — main window using mlx_CLXV.

    pixel writing:
        mlx_get_data_addr() returns a memoryview cast to bytes ('B').
        Each pixel is 4 bytes at offset (y * size_line + x * 4).
        Byte order: Blue, Green, Red, 0xFF  (alpha must be 255).

    key codes (X11):
        ESC / 4 = quit    2 = path    3 = colour
        +/-     = zoom    arrows = pan
"""

import os
from typing import Optional

try:
    import mlx as mlx_module
except ModuleNotFoundError:
    mlx_module = None  # type: ignore[assignment]

from .parser import parse_maze_file
from .tiles import TILE_SIZE, THEMES, build_tile_cache

HUD_H: int = 46
ENTRY_COLOR = (0, 200, 80)  # green
EXIT_COLOR = (255, 80, 20)  # orange

# window settings
WIN_W: int = 1400
WIN_H: int = 900
PAN_STEP: int = 40
ZOOM_STEP: float = 0.1
ZOOM_MIN: float = 0.2
ZOOM_MAX: float = 4.0

# X11 keycodes
KEY_ESC: int = 65307
KEY_1: int = 49  # regen
KEY_2: int = 50  # toggle path
KEY_3: int = 51  # cycle colour theme
KEY_4: int = 52  # quit
KEY_PLUS: int = 61  # '=' key
KEY_PLUS2: int = 43  # '+' numpad
KEY_MINUS: int = 45
KEY_UP: int = 65362
KEY_DOWN: int = 65364
KEY_LEFT: int = 65361
KEY_RIGHT: int = 65363


# Pixel helpers


def fill_rect(
    buf: memoryview,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    r: int,
    g: int,
    b: int,
    sl: int,
    clip_y1: int = WIN_H,
) -> None:
    """
    fill a rectangle in the MLX buffer with a solid colour.

    Builds one row of BGRX pixels and stamps it into the buffer
    row by row using slice assignment.

    args:
        buf:     MLX image buffer (BGRX, row-major).
        x0:      Left column (inclusive).
        y0:      Top row (inclusive).
        x1:      Right column (exclusive).
        y1:      Bottom row (exclusive).
        r:       Red (0-255).
        g:       Green (0-255).
        b:       Blue (0-255).
        sl:      Size line — row stride in bytes from mlx_get_data_addr().
        clip_y1: Bottom clipping boundary, defaults to WIN_H.
    """
    x0 = max(0, x0)
    x1 = min(WIN_W, x1)
    if x0 >= x1:
        return
    row = bytes([b, g, r, 255] * (x1 - x0))
    for y in range(max(0, y0), min(clip_y1, y1)):
        buf[y * sl + x0 * 4: y * sl + x1 * 4] = row


def blend_rect(
    buf: memoryview,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    r: int,
    g: int,
    b: int,
    a: int,
    sl: int,
    max_y: int,
) -> None:
    """Blend a filled rectangle over the existing buffer contents.

    Unlike _fill_rect which overwrites pixels completely, this mixes
    the new colour with whatever is already in the buffer using the
    alpha value as a blend factor.

    Args:
        buf:    MLX image buffer (BGRX, row-major).
        x0:     Left column (inclusive).
        y0:     Top row (inclusive).
        x1:     Right column (exclusive).
        y1:     Bottom row (exclusive).
        r:      Red (0-255).
        g:      Green (0-255).
        b:      Blue (0-255).
        a:      Opacity (0=fully transparent, 255=fully opaque).
        sl:     Size line — row stride in bytes from mlx_get_data_addr().
        max_y:  Bottom clipping boundary (top of HUD bar).
    """
    t = a / 255.0
    for y in range(max(0, y0), min(max_y, y1)):
        for x in range(max(0, x0), min(WIN_W, x1)):
            i = y * sl + x * 4
            buf[i] = int(b * t + buf[i] * (1 - t))
            buf[i + 1] = int(g * t + buf[i + 1] * (1 - t))
            buf[i + 2] = int(r * t + buf[i + 2] * (1 - t))
            buf[i + 3]


def tile_to_bgr(tile: bytearray) -> bytearray:
    """
    Convert a tile from RGBA to BGRX byte order for MLX.

    tiles.py produces pixels as [R, G, B, A].
    MLX expects pixels as [B, G, R, 255].
    This swaps the red and blue channels and sets alpha to 255.

    args:
        tile: RGBA bytearray from tiles.py.

    redeturns:
        new bytearray with pixels in BGRX order.
    """
    out = bytearray(len(tile))
    for i in range(0, len(tile), 4):
        out[i] = tile[i + 2]
        out[i + 1] = tile[i + 1]
        out[i + 2] = tile[i]
        out[i + 3] = 255
    return out


def blit_tile(
    buf: memoryview,
    tile: bytearray,
    dx: int,
    dy: int,
    tile_px: int,
    sl: int,
    max_y: int,
) -> None:
    """
    copy a tile into the MLX buffer at position (dx, dy).

    handles clipping on all edges — left, right, top and bottom.
    only the visible portion of the tile is copied, row by row,
    using slice assignment for fast memory copies.

    args:
        buf:     MLX image buffer (BGRX, row-major).
        tile:    BGRX tile bytearray from the tile cache.
        dx:      Destination x in pixels (can be negative if tile
        is off-screen left).
        dy:      Destination y in pixels (can be negative if tile
        is off-screen top).
        tile_px: Tile width and height in pixels at current zoom.
        sl:      Size line — row stride in bytes from mlx_get_data_addr().
        max_y:   Bottom clipping boundary (top of HUD bar).
    """
    src_x0 = max(0, -dx)
    src_x1 = min(tile_px, WIN_W - dx)
    if src_x0 >= src_x1:
        return
    dst_x0 = dx + src_x0
    nb = (src_x1 - src_x0) * 4
    for ty in range(tile_px):
        wy = dy + ty
        if not (0 <= wy < max_y):
            continue
        si = (ty * tile_px + src_x0) * 4
        di = wy * sl + dst_x0 * 4
        buf[di: di + nb] = tile[si: si + nb]


def scale_tile(src: bytearray, target_px: int) -> bytearray:
    """
    resize a tile to target_px × target_px using nearest-neighbour scaling.

    for each pixel in the destination, maps back to the nearest pixel
    in the source using a ratio. No blending — just picks the closest
    pixel. Used when zoom changes to a size other than TILE_SIZE.

    args:
        src:       BGRX tile bytearray at TILE_SIZE × TILE_SIZE.
        target_px: Target width and height in pixels.

    returns:
        New bytearray of size target_px × target_px × 4 (BGRX).
    """
    dst = bytearray(target_px * target_px * 4)
    ratio = TILE_SIZE / target_px
    for ty in range(target_px):
        sy = int(ty * ratio)
        for tx in range(target_px):
            sx = int(tx * ratio)
            si = (sy * TILE_SIZE + sx) * 4
            di = (ty * target_px + tx) * 4
            dst[di: di + 4] = src[si: si + 4]
    return dst


class MazeDisplay:
    """
    maze display
    controls:  2=path  3=colour  4/ESC=quit  +/-=zoom  arrows=pan
    """

    def __init__(
            self, filepath: str, theme_idx: int = 0, on_regen=None) -> None:
        self.filepath = filepath
        self.on_regen = on_regen
        self.maze = parse_maze_file(filepath)
        self.theme_idx = max(0, min(theme_idx, len(THEMES) - 1))
        self.show_path = False
        self.zoom = 1.0
        self.offset_x = 0
        self.offset_y = 0

        self.tile_cache: dict[int, bytearray] = {}
        self.cached_tile_px: int = 0
        self.dirty: bool = True

        self.m = None
        self.mlx_ptr = None
        self.win_ptr = None
        self.img_ptr = None
        self.buf: Optional[memoryview] = None
        self.sl: int = 0  # size_line

    # public

    def run(self) -> None:
        """
        initialise MLX, open the window and start the event loop.

        creates the MLX connection, window and image buffer, then
        registers three hooks — keyboard input, window close, and
        per-frame rendering. Calls mlx_loop() which never returns,
        handing control to MLX for the rest of the program's lifetime.
        """
        m = mlx_module.Mlx()
        self.m = m

        mlx_ptr = m.mlx_init()
        win_ptr = m.mlx_new_window(mlx_ptr, WIN_W, WIN_H, "A-Maze-ing")
        # Image covers only the maze area (above HUD)
        img_ptr = m.mlx_new_image(mlx_ptr, WIN_W, WIN_H)
        buf, _bpp, sl, _fmt = m.mlx_get_data_addr(img_ptr)

        self.mlx_ptr = mlx_ptr
        self.win_ptr = win_ptr
        self.img_ptr = img_ptr
        self.buf = buf
        self.sl = sl

        self.fit_to_window()

        m.mlx_key_hook(win_ptr, self.on_key, None)
        m.mlx_hook(win_ptr, 17, 0, self.on_close, None)
        m.mlx_loop_hook(mlx_ptr, self.on_loop, None)
        m.mlx_loop(mlx_ptr)

    # input
    def on_key(self, keycode: int, _param: object) -> None:
        if keycode in (KEY_ESC, KEY_4):
            os._exit(0)
        elif keycode == KEY_1:
            if self.on_regen:
                self.on_regen()
                self.maze = parse_maze_file(self.filepath)
                self.fit_to_window()
            self._dirty = True
        elif keycode == KEY_2:
            self.show_path = not self.show_path
            self._dirty = True
        elif keycode == KEY_3:
            self.theme_idx = (self.theme_idx + 1) % len(THEMES)
            self._tile_cache = {}
            self._dirty = True
        elif keycode in (KEY_PLUS, KEY_PLUS2):
            self.zoom = min(ZOOM_MAX, round(self.zoom + ZOOM_STEP, 1))
            self._tile_cache = {}
            self._dirty = True
        elif keycode == KEY_MINUS:
            self.zoom = max(ZOOM_MIN, round(self.zoom - ZOOM_STEP, 1))
            self._tile_cache = {}
            self._dirty = True
        elif keycode == KEY_UP:
            self.offset_y += PAN_STEP
            self._dirty = True
        elif keycode == KEY_DOWN:
            self.offset_y -= PAN_STEP
            self._dirty = True
        elif keycode == KEY_LEFT:
            self.offset_x += PAN_STEP
            self._dirty = True
        elif keycode == KEY_RIGHT:
            self.offset_x -= PAN_STEP
            self._dirty = True

    def on_close(self, _param: object) -> None:
        os._exit(0)

    def on_loop(self, _param: object) -> None:
        if not self._dirty:
            return
        m = self.m
        if m and self.mlx_ptr and self.img_ptr:
            m.mlx_sync(self.mlx_ptr, m.SYNC_IMAGE_WRITABLE, self.img_ptr)
        self.render()
        if m and self.mlx_ptr and self.win_ptr and self.img_ptr:
            m.mlx_put_image_to_window(
                self.mlx_ptr, self.win_ptr, self.img_ptr, 0, 0)
            # Draw HUD text AFTER image blit so it appears on top
            self.draw_hud_text()
        self._dirty = False

    # layout
    def fit_to_window(self) -> None:
        usable_h = WIN_H - HUD_H
        zoom_x = WIN_W / (self.maze.cols * TILE_SIZE)
        zoom_y = usable_h / (self.maze.rows * TILE_SIZE)
        self.zoom = round(min(zoom_x, zoom_y, 1.5), 1)
        tile_px = self.tile_px()
        self.offset_x = (WIN_W - self.maze.cols * tile_px) // 2
        self.offset_y = (usable_h - self.maze.rows * tile_px) // 2
        self._tile_cache = {}
        self._dirty = True

    def tile_px(self) -> int:
        return max(4, int(TILE_SIZE * self.zoom))

    # cache
    def ensure_cache(self) -> None:
        """
        Build or rebuild the tile cache for the current zoom and theme.

        skips rebuilding if the cache is already valid for the current
        tile size.
        Otherwise renders all 16 tiles, scales them if zoom
        has changed, and converts from RGBA to BGRX for MLX.

        The cache is invalidated (set to {}) by _on_key whenever zoom
        or theme changes.
        """
        tile_px = self.tile_px()
        if self._tile_cache and self._cached_tile_px == tile_px:
            return
        base = build_tile_cache(THEMES[self.theme_idx])
        scaled = (
            base
            if tile_px == TILE_SIZE
            else {hv: scale_tile(t, tile_px) for hv, t in base.items()}
        )
        self._tile_cache = {hv: tile_to_bgr(t) for hv, t in scaled.items()}
        self._cached_tile_px = tile_px

    # rendering
    def render(self) -> None:
        """
        composite one frame into the MLX image buffer.

        drawing order (each layer paints over the previous):
        1. Background  — fill entire buffer with the theme floor colour
        2. Tiles       — blit each maze cell from the tile cache
        3. '42' cells  — paint pattern cells with a fixed highlight colour
        4. Path        — draw solution line if show_path is True
        5. Portals     — draw entry and exit circles
        6. HUD         — fill bottom bar and draw divider line
        """
        if self.buf is None:
            return
        buf = self.buf
        sl = self.sl
        tile_px = self.tile_px()
        max_y = WIN_H - HUD_H
        self.ensure_cache()

        # Background
        fl = THEMES[self.theme_idx].floor
        row = bytes([fl[2], fl[1], fl[0], 255] * WIN_W)
        for y in range(WIN_H):
            buf[y * sl: y * sl + WIN_W * 4] = row

        # Tiles
        for r in range(self.maze.rows):
            for c in range(self.maze.cols):
                tile = self._tile_cache.get(self.maze.grid[r][c])
                if tile:
                    blit_tile(
                        buf,
                        tile,
                        c * tile_px + self.offset_x,
                        r * tile_px + self.offset_y,
                        tile_px,
                        sl,
                        max_y,
                    )

        # '42' highlight
        if self.maze.pattern42_cells:
            # wr, wg, wb = THEMES[self.theme_idx].wall
            for row, col in self.maze.pattern42_cells:
                x0 = col * tile_px + self.offset_x
                y0 = row * tile_px + self.offset_y
                blend_rect(
                    buf,
                    x0,
                    y0,
                    x0 + tile_px,
                    y0 + tile_px,
                    204,
                    204,
                    255,
                    120,
                    sl,
                    max_y,
                )
        # path
        if self.show_path and self.maze.path:
            self.draw_path(tile_px, sl, max_y)

        # portals
        half = tile_px // 2
        er, ec = self.maze.entry
        xr, xc = self.maze.exit_
        self.draw_portal(
            ec * tile_px + self.offset_x + half,
            er * tile_px + self.offset_y + half,
            ENTRY_COLOR,
            sl,
            max_y,
            tile_px
        )
        self.draw_portal(
            xc * tile_px + self.offset_x + half,
            xr * tile_px + self.offset_y + half,
            EXIT_COLOR,
            sl,
            max_y,
            tile_px
        )

        # HUD background drawn into image
        hud_top = WIN_H - HUD_H
        fill_rect(buf, 0, hud_top, WIN_W, WIN_H, 22, 22, 28, sl)
        # divider line
        div = bytes([78, 60, 55, 255] * WIN_W)
        buf[hud_top * sl: hud_top * sl + WIN_W * 4] = div

    def draw_path(self, tile_px: int, sl: int, max_y: int) -> None:
        """
        draw path as rectangles from centre-to-centre
        between consecutive cells.

        for each pair of adjacent path cells, draw a rectangle spanning
        from one cell centre to the next, with thickness 2h.
        corners are seamless because rectangles share endpoints at centres.

        args:
            tile_px: Current tile size in pixels.
            sl:      Size line — row stride in bytes from mlx_get_data_addr().
            max_y:   Bottom clipping boundary (top of HUD bar).
        """
        buf = self.buf
        pr, pg, pb = 80, 160, 255
        half = tile_px // 2
        h = max(3, tile_px // 5)

        path = self.maze.path
        for i in range(len(path) - 1):
            r1, c1 = path[i]
            r2, c2 = path[i + 1]
            ax = c1 * tile_px + self.offset_x + half
            ay = r1 * tile_px + self.offset_y + half
            bx = c2 * tile_px + self.offset_x + half
            by = r2 * tile_px + self.offset_y + half
            if ax == bx:
                x0, x1 = ax - h, ax + h
                y0, y1 = min(ay, by) - h, max(ay, by) + h
            else:
                x0, x1 = min(ax, bx) - h, max(ax, bx) + h
                y0, y1 = ay - h, ay + h
            fill_rect(buf, x0, y0, x1, y1, pr, pg, pb, sl, max_y)

    def draw_portal(
            self, cx: int,
            cy: int, color: tuple, sl: int, max_y: int, tile_px: int) -> None:
        """
        draw a filled circle marking an entry or exit portal.

        uses the equation x² + y² ≤ r² to determine which pixels
        fall inside the circle, then draws each as a single pixel.

        args:
            cx:    Centre x in pixels.
            cy:    Centre y in pixels.
            color: RGB tuple for the circle colour.
            sl:    Size line — row stride in bytes from mlx_get_data_addr().
            max_y: Bottom clipping boundary (top of HUD bar).
        """
        buf = self.buf
        r, g, b = color
        radius = max(4, tile_px // 4)
        for dy2 in range(-radius, radius + 1):
            for dx2 in range(-radius, radius + 1):
                if dx2 * dx2 + dy2 * dy2 <= radius * radius:
                    fill_rect(
                        buf,
                        cx + dx2,
                        cy + dy2,
                        cx + dx2 + 1,
                        cy + dy2 + 1,
                        r,
                        g,
                        b,
                        sl,
                        max_y,
                    )

    def draw_hud_text(self) -> None:
        """Draw control hints onto the HUD bar.

        Called after mlx_put_image_to_window so text appears on top
        of the image. Uses mlx_string_put which writes directly to
        the window rather than the image buffer.

        Items are spaced by character count — each character is 8px wide
        with a 20px gap between items. Stops early if items would overflow
        the window width.
        """
        m = self.m
        if not (m and self.mlx_ptr and self.win_ptr):
            return
        theme = THEMES[self.theme_idx]
        path_s = "ON" if self.show_path else "OFF"
        zoom_s = f"{self.zoom:.1f}x"
        hud_y = WIN_H - HUD_H + (HUD_H - 13) // 2

        items = [
            ("1:regen ", 0xC3C8D7),
            (f"2:path:{path_s} ", 0x4BD750 if self.show_path else 0xC3C8D7),
            (f"3:{theme.name} ", 0x64B4FF),
            ("4:quit ", 0xC85A5A),
            (f"+/-:{zoom_s} ", 0xC3C8D7),
            ("arrows:pan ", 0xC3C8D7),
        ]
        x = 12
        for text, color in items:
            m.mlx_string_put(self.mlx_ptr, self.win_ptr, x, hud_y, color, text)
            x += len(text) * 8 + 20
            if x > WIN_W - 80:
                break

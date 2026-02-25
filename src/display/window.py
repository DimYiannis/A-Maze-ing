"""
display/window.py
=================
MazeDisplay — main window using mlx_CLXV (CLXV Python wrapper for miniLibX).

Pixel writing:
    mlx_get_data_addr() returns a memoryview cast to bytes ('B').
    Each pixel is 4 bytes at offset (y * size_line + x * 4).
    Byte order: Blue, Green, Red, 0x00  (little-endian 0x00RRGGBB).

Key codes (X11):
    ESC   = 65307     SPACE = 32
    C     = 99        4     = 52
    +     = 61 / 43   -     = 45
    Up    = 65362     Down  = 65364
    Left  = 65361     Right = 65363
    Q     = 113
"""

import os
import sys
from typing import Optional

try:
    import mlx as mlx_module
except ModuleNotFoundError:
    mlx_module = None  # type: ignore[assignment]

from .parser import MazeData, parse_maze_file
from .tiles import (
    TILE_SIZE, THEMES, Theme, build_tile_cache,
)
from .overlays import (
    HUD_H,
    draw_path, draw_portal, draw_42_highlight, draw_hud,
    ENTRY_RINGS, EXIT_RINGS,
)


# ── Window settings ───────────────────────────────────────────────────────────

WIN_W:    int   = 1100
WIN_H:    int   = 750
PAN_STEP: int   = 40
ZOOM_STEP: float = 0.1
ZOOM_MIN:  float = 0.2
ZOOM_MAX:  float = 4.0

# ── X11 keycodes ──────────────────────────────────────────────────────────────

KEY_ESC:   int = 65307
KEY_1:     int = 49     # regen — no-op in display-only mode
KEY_2:     int = 50     # toggle path
KEY_3:     int = 51     # cycle colour theme
KEY_4:     int = 52     # quit
KEY_PLUS:  int = 61     # '=' key (same physical key as '+')
KEY_PLUS2: int = 43     # '+' on numpad
KEY_MINUS: int = 45
KEY_UP:    int = 65362
KEY_DOWN:  int = 65364
KEY_LEFT:  int = 65361
KEY_RIGHT: int = 65363


# ── Pixel helpers ─────────────────────────────────────────────────────────────

def _put_pixel(
    buf: memoryview,
    x: int,
    y: int,
    r: int,
    g: int,
    b: int,
    size_line: int,
) -> None:
    """Write one opaque pixel into the MLX image memoryview.

    The miniLibX buffer stores pixels as 0x00RRGGBB in little-endian,
    so the byte order in memory is B, G, R, 0x00.

    Args:
        buf:       Writable memoryview from mlx_get_data_addr().
        x:         Pixel column.
        y:         Pixel row.
        r:         Red channel (0–255).
        g:         Green channel (0–255).
        b:         Blue channel (0–255).
        size_line: Row stride in bytes (from mlx_get_data_addr()).
    """
    i = y * size_line + x * 4
    buf[i]     = b
    buf[i + 1] = g
    buf[i + 2] = r
    buf[i + 3] = 0


def _tile_to_bgr(tile: bytearray, tile_px: int) -> bytearray:
    """Convert a tile RGBA bytearray to BGRX for direct MLX blitting.

    Converts once per tile per theme/zoom change and caches the result.

    Args:
        tile:    RGBA bytearray (R,G,B,A order).
        tile_px: Tile size in pixels.

    Returns:
        BGRX bytearray (B,G,R,0 order), same length.
    """
    out = bytearray(len(tile))
    for i in range(0, len(tile), 4):
        out[i]     = tile[i + 2]  # B
        out[i + 1] = tile[i + 1]  # G
        out[i + 2] = tile[i]      # R
        out[i + 3] = 0
    return out


def _blit_tile(
    buf: memoryview,
    tile: bytearray,
    dx: int,
    dy: int,
    tile_px: int,
    size_line: int,
    win_w: int,
    win_h: int,
) -> None:
    """Copy a pre-converted BGRX tile into the MLX memoryview row by row.

    Args:
        buf:       Writable MLX image memoryview.
        tile:      BGRX bytearray (pre-converted by _tile_to_bgr).
        dx:        Destination left column in the window.
        dy:        Destination top row in the window.
        tile_px:   Tile size in pixels at current zoom.
        size_line: Row stride of the MLX buffer in bytes.
        win_w:     Window width (for clipping).
        win_h:     Window height (for clipping).
    """
    max_y = win_h - HUD_H
    # Clip x range once for all rows
    src_x0 = max(0, -dx)
    src_x1 = min(tile_px, win_w - dx)
    if src_x0 >= src_x1:
        return
    dst_x0 = dx + src_x0
    nbytes  = (src_x1 - src_x0) * 4

    for ty in range(tile_px):
        wy = dy + ty
        if not (0 <= wy < max_y):
            continue
        si = (ty * tile_px + src_x0) * 4
        di = wy * size_line + dst_x0 * 4
        buf[di: di + nbytes] = tile[si: si + nbytes]


def _fill_rect(
    buf: memoryview,
    x0: int,
    y0: int,
    x1: int,
    y1: int,
    r: int,
    g: int,
    b: int,
    size_line: int,
    win_w: int,
    win_h: int,
) -> None:
    """Fill a clipped rectangle in the MLX memoryview.

    Args:
        buf:       Writable MLX image memoryview.
        x0:        Left column (inclusive).
        y0:        Top row (inclusive).
        x1:        Right column (exclusive).
        y1:        Bottom row (exclusive).
        r:         Red.
        g:         Green.
        b:         Blue.
        size_line: Row stride in bytes.
        win_w:     Window width (for clipping).
        win_h:     Window height (for clipping).
    """
    for y in range(max(0, y0), min(win_h, y1)):
        for x in range(max(0, x0), min(win_w, x1)):
            i = y * size_line + x * 4
            buf[i]     = b
            buf[i + 1] = g
            buf[i + 2] = r
            buf[i + 3] = 0


def _blend_pixel(
    buf: memoryview,
    x: int,
    y: int,
    r: int,
    g: int,
    b: int,
    a: int,
    size_line: int,
    win_w: int,
    win_h: int,
) -> None:
    """Alpha-blend one pixel over the current MLX buffer colour.

    Args:
        buf:       Writable MLX image memoryview.
        x:         Column.
        y:         Row.
        r:         Source red.
        g:         Source green.
        b:         Source blue.
        a:         Source alpha (0–255).
        size_line: Row stride in bytes.
        win_w:     Window width.
        win_h:     Window height.
    """
    if not (0 <= x < win_w and 0 <= y < win_h) or a == 0:
        return
    i = y * size_line + x * 4
    t = a / 255.0
    buf[i]     = int(b * t + buf[i]     * (1 - t))
    buf[i + 1] = int(g * t + buf[i + 1] * (1 - t))
    buf[i + 2] = int(r * t + buf[i + 2] * (1 - t))
    buf[i + 3] = 0


# ═══════════════════════════════════════════════════════════════════════════════
# DISPLAY CLASS
# ═══════════════════════════════════════════════════════════════════════════════

class MazeDisplay:
    """Interactive maze window using the mlx_CLXV Python wrapper.

    Reads a maze .txt file, renders tiles into the MLX image buffer,
    and handles all required user interactions.

    Controls:
        SPACE      Show / hide solution path
        C          Cycle colour themes (5 total)
        4          Toggle '42' pattern golden highlight
        + / -      Zoom in / out
        Arrow keys Pan the view
        ESC / Q    Quit

    Example::

        MazeDisplay("maze.txt").run()
        MazeDisplay("maze.txt", theme_idx=2).run()
    """

    def __init__(self, filepath: str, theme_idx: int = 0) -> None:
        """Initialise from a maze output file.

        Args:
            filepath:  Path to the .txt maze output file.
            theme_idx: Starting colour theme index (0–4).

        Raises:
            FileNotFoundError: If the file does not exist.
            ValueError:        If the file format is invalid.
        """
        self.filepath:  str      = filepath
        self.maze:      MazeData = parse_maze_file(filepath)
        self.theme_idx: int      = max(0, min(theme_idx, len(THEMES) - 1))
        self.show_path: bool     = False
        self.show_42:   bool     = False
        self.zoom:      float    = 1.0
        self.offset_x:  int      = 0
        self.offset_y:  int      = 0

        self._tile_cache:     dict[int, bytearray] = {}
        self._cached_tile_px: int = 0
        self._dirty:          bool = True

        # MLX handles — set in run()
        self._m:       Optional[object] = None
        self._mlx_ptr: Optional[int] = None
        self._win_ptr: Optional[int] = None
        self._img_ptr: Optional[int] = None
        self._buf:     Optional[memoryview] = None
        self._size_line: int = 0

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self) -> None:
        """Open the window and start the MLX event loop.

        Blocks until the user presses ESC/Q or closes the window.
        """
        m = mlx_module.Mlx()
        self._m = m

        mlx_ptr = m.mlx_init()
        win_ptr = m.mlx_new_window(
            mlx_ptr, WIN_W, WIN_H,
            f"A-Maze-ing — {os.path.basename(self.filepath)}",
        )
        img_ptr = m.mlx_new_image(mlx_ptr, WIN_W, WIN_H)

        buf, bpp, size_line, fmt = m.mlx_get_data_addr(img_ptr)

        print(f"bpp={bpp} size_line={size_line} fmt={fmt}")

        # Draw a single bright red pixel at (100, 100) every possible way
        i = 100 * size_line + 100 * 4
        buf[i], buf[i+1], buf[i+2], buf[i+3] = 255, 0, 0, 0    # R first
        m.mlx_put_image_to_window(mlx_ptr, win_ptr, img_ptr, 0, 0)

        self._mlx_ptr  = mlx_ptr
        self._win_ptr  = win_ptr
        self._img_ptr  = img_ptr
        self._buf      = buf
        self._size_line = size_line

        self._fit_to_window()

        m.mlx_key_hook(win_ptr, self._on_key, None)
        m.mlx_hook(win_ptr, 17, 0, self._on_close, None)   # WM_DELETE
        m.mlx_loop_hook(mlx_ptr, self._on_loop, None)
        m.mlx_loop(mlx_ptr)

    # ── Input ─────────────────────────────────────────────────────────────────

    def _on_key(self, keycode: int, _param: object) -> None:
        """Handle key press events.

        Args:
            keycode: X11 keycode.
            _param:  Unused hook parameter.
        """
        if keycode in (KEY_ESC, KEY_4):
            os._exit(0)
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

    def _on_close(self, _param: object) -> None:
        """Handle window close (WM_DELETE) event.

        Args:
            _param: Unused hook parameter.
        """
        os._exit(0)

    def _on_loop(self, _param: object) -> None:
        """Called every frame by mlx_loop_hook. Renders if dirty.

        Args:
            _param: Unused hook parameter.
        """
        if not self._dirty:
            return
        self._render()
        if self._m and self._mlx_ptr and self._win_ptr and self._img_ptr:
            self._m.mlx_put_image_to_window(
                self._mlx_ptr, self._win_ptr, self._img_ptr, 0, 0
            )
        self._dirty = False

    # ── Layout ────────────────────────────────────────────────────────────────

    def _fit_to_window(self) -> None:
        """Auto-zoom and centre the maze to fill the window (HUD at bottom)."""
        usable_h = WIN_H - HUD_H
        zoom_x = WIN_W / (self.maze.cols * TILE_SIZE)
        zoom_y = usable_h / (self.maze.rows * TILE_SIZE)
        self.zoom = round(min(zoom_x, zoom_y, 1.5), 1)

        tile_px = self._tile_px()
        self.offset_x = (WIN_W - self.maze.cols * tile_px) // 2
        self.offset_y = (usable_h - self.maze.rows * tile_px) // 2
        self._tile_cache = {}
        self._dirty = True

    def _tile_px(self) -> int:
        """Current tile size in pixels.

        Returns:
            TILE_SIZE × zoom, minimum 4 pixels.
        """
        return max(4, int(TILE_SIZE * self.zoom))

    # ── Tile cache ────────────────────────────────────────────────────────────

    def _ensure_cache(self) -> None:
        """Rebuild tile cache if theme or zoom has changed."""
        tile_px = self._tile_px()
        if self._tile_cache and self._cached_tile_px == tile_px:
            return
        base = build_tile_cache(THEMES[self.theme_idx])
        if tile_px == TILE_SIZE:
            scaled = base
        else:
            scaled = {hv: _scale_tile(buf, tile_px) for hv, buf in base.items()}
        # Pre-convert RGBA → BGRX for fast row-slice blitting
        self._tile_cache = {hv: _tile_to_bgr(buf, tile_px) for hv, buf in scaled.items()}
        self._cached_tile_px = tile_px

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self) -> None:
        """Composite all layers into the MLX image buffer."""
        if self._buf is None:
            return

        buf       = self._buf
        sl        = self._size_line
        tile_px   = self._tile_px()
        self._ensure_cache()

        # Background — fill entire buffer at once using slice assignment
        fl = THEMES[self.theme_idx].floor
        row = bytes([fl[2], fl[1], fl[0], 0] * WIN_W)   # one row BGRX
        for y in range(WIN_H):
            buf[y * sl: y * sl + WIN_W * 4] = row

        # Tiles
        for r in range(self.maze.rows):
            for c in range(self.maze.cols):
                tile = self._tile_cache.get(self.maze.grid[r][c])
                if tile:
                    _blit_tile(
                        buf, tile,
                        c * tile_px + self.offset_x,
                        r * tile_px + self.offset_y,
                        tile_px, sl, WIN_W, WIN_H,
                    )

        # '42' highlight
        if self.show_42 and self.maze.pattern42_cells:
            self._draw_42(tile_px)

        # Path overlay
        if self.show_path and self.maze.path:
            self._draw_path(tile_px)

        # Portals
        half = tile_px // 2
        er, ec = self.maze.entry
        xr, xc = self.maze.exit_
        self._draw_portal(
            ec * tile_px + self.offset_x + half,
            er * tile_px + self.offset_y + half,
            ENTRY_RINGS, arrow_up=False,
        )
        self._draw_portal(
            xc * tile_px + self.offset_x + half,
            xr * tile_px + self.offset_y + half,
            EXIT_RINGS, arrow_up=True,
        )

        # HUD
        self._draw_hud()

    def _draw_42(self, tile_px: int) -> None:
        """Draw golden highlight over '42' pattern cells.

        Args:
            tile_px: Current tile pixel size.
        """
        if self._buf is None:
            return
        pr, pg, pb, pa = 255, 200, 0, 80
        for r, c in self.maze.pattern42_cells:
            x0 = c * tile_px + self.offset_x
            y0 = r * tile_px + self.offset_y
            for y in range(max(0, y0), min(WIN_H - HUD_H, y0 + tile_px)):
                for x in range(max(0, x0), min(WIN_W, x0 + tile_px)):
                    _blend_pixel(
                        self._buf, x, y, pr, pg, pb, pa,
                        self._size_line, WIN_W, WIN_H,
                    )

    def _draw_path(self, tile_px: int) -> None:
        """Draw the solution path as half-cell coloured strips.

        Args:
            tile_px: Current tile pixel size.
        """
        if self._buf is None:
            return
        pr, pg, pb, pa = 80, 160, 255, 160
        half  = tile_px // 2
        strip = max(4, tile_px // 6)
        h     = strip // 2

        for i, (r, c) in enumerate(self.maze.path):
            px = c * tile_px + self.offset_x
            py = r * tile_px + self.offset_y
            cx = px + half
            cy = py + half

            dirs: list[str] = []
            if i > 0:
                pr2, pc2 = self.maze.path[i - 1]
                dr, dc = r - pr2, c - pc2
                if dr == -1:   dirs.append("N")
                elif dr == 1:  dirs.append("S")
                elif dc == -1: dirs.append("W")
                elif dc == 1:  dirs.append("E")
            if i < len(self.maze.path) - 1:
                nr, nc = self.maze.path[i + 1]
                dr2, dc2 = nr - r, nc - c
                if dr2 == -1:   dirs.append("N")
                elif dr2 == 1:  dirs.append("S")
                elif dc2 == -1: dirs.append("W")
                elif dc2 == 1:  dirs.append("E")

            for d in dirs:
                if d == "N":
                    self._blend_rect(cx - h, py, cx + h, cy, pr, pg, pb, pa)
                elif d == "S":
                    self._blend_rect(cx - h, cy, cx + h, py + tile_px, pr, pg, pb, pa)
                elif d == "W":
                    self._blend_rect(px, cy - h, cx, cy + h, pr, pg, pb, pa)
                elif d == "E":
                    self._blend_rect(cx, cy - h, px + tile_px, cy + h, pr, pg, pb, pa)

            self._blend_circle(cx, cy, h + 1, pr, pg, pb, pa)

    def _draw_portal(
        self,
        cx: int,
        cy: int,
        rings: list[tuple[int, int, int]],
        arrow_up: bool,
    ) -> None:
        """Draw a glowing portal with rings and directional arrow.

        Args:
            cx:       Centre column pixel.
            cy:       Centre row pixel.
            rings:    RGB colours for rings, outer to inner.
            arrow_up: True = exit (↑), False = entry (↓).
        """
        if self._buf is None:
            return
        radii = [14, 10, 7, 4, 2]
        for radius, col in zip(radii, rings):
            self._blend_circle(cx, cy, radius, *col, 220)

        ar, ag, ab = (220, 255, 225) if not arrow_up else (255, 235, 190)
        if arrow_up:
            for dy in range(-3, 7):
                _blend_pixel(self._buf, cx - 1, cy + dy, ar, ag, ab, 255, self._size_line, WIN_W, WIN_H)
                _blend_pixel(self._buf, cx,     cy + dy, ar, ag, ab, 255, self._size_line, WIN_W, WIN_H)
            for step in range(6):
                for dx in range(-5 + step, 6 - step):
                    _blend_pixel(self._buf, cx + dx, cy - 3 - step, ar, ag, ab, 255, self._size_line, WIN_W, WIN_H)
        else:
            for dy in range(-6, 4):
                _blend_pixel(self._buf, cx - 1, cy + dy, ar, ag, ab, 255, self._size_line, WIN_W, WIN_H)
                _blend_pixel(self._buf, cx,     cy + dy, ar, ag, ab, 255, self._size_line, WIN_W, WIN_H)
            for step in range(6):
                for dx in range(-5 + step, 6 - step):
                    _blend_pixel(self._buf, cx + dx, cy + 3 + step, ar, ag, ab, 255, self._size_line, WIN_W, WIN_H)

    def _draw_hud(self) -> None:
        """Draw the HUD bar using mlx_string_put for text."""
        if not (self._m and self._mlx_ptr and self._win_ptr and self._buf):
            return

        # HUD background — at the bottom of the window
        hud_top = WIN_H - HUD_H
        _fill_rect(
            self._buf,
            0, hud_top, WIN_W, WIN_H,
            22, 22, 28,
            self._size_line, WIN_W, WIN_H,
        )
        # Divider line at top of HUD
        for x in range(WIN_W):
            i = hud_top * self._size_line + x * 4
            self._buf[i]     = 78
            self._buf[i + 1] = 60
            self._buf[i + 2] = 55
            self._buf[i + 3] = 0

        # Text via mlx_string_put (rendered into the window after image blit)
        theme  = THEMES[self.theme_idx]
        path_s = "ON" if self.show_path else "OFF"
        zoom_s = f"{self.zoom:.1f}x"

        items = [
            ("1:regen",                          0xC3C8D7),
            (f"2:path",                          0x4BD750 if self.show_path else 0xC3C8D7),
            (f"3:color",                         0x64B4FF),
            ("4:quit",                           0xC85A5A),
            (f"[+/-] {zoom_s}",                  0xC3C8D7),
            (f"[arrows] pan",                    0xC3C8D7),
        ]
        x = 10
        y = hud_top + (HUD_H - 13) // 2
        for text, color in items:
            self._m.mlx_string_put(
                self._mlx_ptr, self._win_ptr, x, y, color, text
            )
            x += len(text) * 8 + 16
            if x > WIN_W - 100:
                break

    # ── Drawing helpers ───────────────────────────────────────────────────────

    def _blend_rect(
        self,
        x0: int,
        y0: int,
        x1: int,
        y1: int,
        r: int,
        g: int,
        b: int,
        a: int,
    ) -> None:
        """Alpha-blend a filled rectangle into the buffer.

        Args:
            x0: Left column (inclusive).
            y0: Top row (inclusive).
            x1: Right column (exclusive).
            y1: Bottom row (exclusive).
            r:  Red.
            g:  Green.
            b:  Blue.
            a:  Alpha.
        """
        if self._buf is None:
            return
        for y in range(max(0, y0), min(WIN_H - HUD_H, y1)):
            for x in range(max(0, x0), min(WIN_W, x1)):
                _blend_pixel(
                    self._buf, x, y, r, g, b, a,
                    self._size_line, WIN_W, WIN_H,
                )

    def _blend_circle(
        self,
        cx: int,
        cy: int,
        radius: int,
        r: int,
        g: int,
        b: int,
        a: int,
    ) -> None:
        """Alpha-blend a filled circle into the buffer.

        Args:
            cx:     Centre column.
            cy:     Centre row.
            radius: Radius in pixels.
            r:      Red.
            g:      Green.
            b:      Blue.
            a:      Alpha.
        """
        if self._buf is None:
            return
        for y in range(cy - radius, cy + radius + 1):
            for x in range(cx - radius, cx + radius + 1):
                if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                    _blend_pixel(
                        self._buf, x, y, r, g, b, a,
                        self._size_line, WIN_W, WIN_H,
                    )


# ── Tile scaling ──────────────────────────────────────────────────────────────

def _scale_tile(src: bytearray, target_px: int) -> bytearray:
    """Nearest-neighbour scale a tile bytearray to target_px × target_px.

    Args:
        src:       Source RGBA bytearray (TILE_SIZE × TILE_SIZE × 4).
        target_px: Target tile size in pixels.

    Returns:
        Scaled RGBA bytearray (target_px × target_px × 4).
    """
    dst   = bytearray(target_px * target_px * 4)
    ratio = TILE_SIZE / target_px
    for ty in range(target_px):
        sy = int(ty * ratio)
        for tx in range(target_px):
            sx = int(tx * ratio)
            si = (sy * TILE_SIZE + sx) * 4
            di = (ty * target_px + tx) * 4
            dst[di]     = src[si]
            dst[di + 1] = src[si + 1]
            dst[di + 2] = src[si + 2]
            dst[di + 3] = src[si + 3]
    return dst


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    """Run the display from the command line.

    Usage::

        python3 -m display.window maze.txt
        python3 -m display.window maze.txt --theme 2
    """
    import argparse

    parser = argparse.ArgumentParser(description="A-Maze-ing display")
    parser.add_argument("maze_file", help="Path to the maze .txt file")
    parser.add_argument(
        "--theme", type=int, default=0,
        choices=range(len(THEMES)),
        metavar=f"0-{len(THEMES) - 1}",
        help=", ".join(f"{i}={t.name}" for i, t in enumerate(THEMES)),
    )
    args = parser.parse_args()

    try:
        MazeDisplay(args.maze_file, theme_idx=args.theme).run()
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


# Script entry — adds parent dir to path so relative imports work
# Usage: python3 display/window.py maze.txt
if __name__ == "__main__":
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    main()

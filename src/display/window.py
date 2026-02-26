"""
display/window.py
=================
MazeDisplay — main window using mlx_CLXV (CLXV Python wrapper for miniLibX).

Pixel writing:
    mlx_get_data_addr() returns a memoryview cast to bytes ('B').
    Each pixel is 4 bytes at offset (y * size_line + x * 4).
    Byte order: Blue, Green, Red, 0xFF  (alpha must be 255).

Key codes (X11):
    ESC / 4 = quit    2 = path    3 = colour
    +/-     = zoom    arrows = pan
"""

import os
import sys
from typing import Optional

try:
    import mlx as mlx_module
except ModuleNotFoundError:
    mlx_module = None  # type: ignore[assignment]

from .parser import MazeData, parse_maze_file
from .tiles import TILE_SIZE, THEMES, build_tile_cache
from .overlays import HUD_H, ENTRY_RINGS, EXIT_RINGS


# ── Window settings ───────────────────────────────────────────────────────────

WIN_W:     int   = 1400
WIN_H:     int   = 900
PAN_STEP:  int   = 40
ZOOM_STEP: float = 0.1
ZOOM_MIN:  float = 0.2
ZOOM_MAX:  float = 4.0

# ── X11 keycodes ──────────────────────────────────────────────────────────────

KEY_ESC:   int = 65307
KEY_2:     int = 50     # toggle path
KEY_3:     int = 51     # cycle colour theme
KEY_4:     int = 52     # quit
KEY_PLUS:  int = 61     # '=' key
KEY_PLUS2: int = 43     # '+' numpad
KEY_MINUS: int = 45
KEY_UP:    int = 65362
KEY_DOWN:  int = 65364
KEY_LEFT:  int = 65361
KEY_RIGHT: int = 65363


# ── Pixel helpers ─────────────────────────────────────────────────────────────

def _put(buf: memoryview, x: int, y: int,
         r: int, g: int, b: int, sl: int) -> None:
    i = y * sl + x * 4
    buf[i] = b; buf[i+1] = g; buf[i+2] = r; buf[i+3] = 255


def _fill_row(buf: memoryview, y: int, x0: int, x1: int,
              r: int, g: int, b: int, sl: int) -> None:
    row = bytes([b, g, r, 255] * (x1 - x0))
    buf[y * sl + x0 * 4: y * sl + x1 * 4] = row


def _fill_rect(buf: memoryview, x0: int, y0: int, x1: int, y1: int,
               r: int, g: int, b: int, sl: int,
               clip_y1: int = WIN_H) -> None:
    row = bytes([b, g, r, 255] * (x1 - x0))
    for y in range(max(0, y0), min(clip_y1, y1)):
        buf[y * sl + x0 * 4: y * sl + x1 * 4] = row


def _blend(buf: memoryview, x: int, y: int,
           r: int, g: int, b: int, a: int,
           sl: int, max_y: int) -> None:
    if not (0 <= x < WIN_W and 0 <= y < max_y) or a == 0:
        return
    i = y * sl + x * 4
    t = a / 255.0
    buf[i]   = int(b * t + buf[i]   * (1-t))
    buf[i+1] = int(g * t + buf[i+1] * (1-t))
    buf[i+2] = int(r * t + buf[i+2] * (1-t))
    buf[i+3] = 255


def _tile_to_bgr(tile: bytearray) -> bytearray:
    out = bytearray(len(tile))
    for i in range(0, len(tile), 4):
        out[i] = tile[i+2]; out[i+1] = tile[i+1]
        out[i+2] = tile[i]; out[i+3] = 255
    return out


def _blit_tile(buf: memoryview, tile: bytearray,
               dx: int, dy: int, tile_px: int,
               sl: int, max_y: int) -> None:
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
        buf[di: di+nb] = tile[si: si+nb]


def _scale_tile(src: bytearray, target_px: int) -> bytearray:
    dst = bytearray(target_px * target_px * 4)
    ratio = TILE_SIZE / target_px
    for ty in range(target_px):
        sy = int(ty * ratio)
        for tx in range(target_px):
            sx = int(tx * ratio)
            si = (sy * TILE_SIZE + sx) * 4
            di = (ty * target_px + tx) * 4
            dst[di:di+4] = src[si:si+4]
    return dst


# ═══════════════════════════════════════════════════════════════════════════════

class MazeDisplay:
    """Interactive maze display using mlx_CLXV.

    Controls:  2=path  3=colour  4/ESC=quit  +/-=zoom  arrows=pan
    """

    def __init__(self, filepath: str, theme_idx: int = 0) -> None:
        self.filepath  = filepath
        self.maze      = parse_maze_file(filepath)
        self.theme_idx = max(0, min(theme_idx, len(THEMES) - 1))
        self.show_path = False
        self.show_42   = False
        self.zoom      = 1.0
        self.offset_x  = 0
        self.offset_y  = 0

        self._tile_cache:     dict[int, bytearray] = {}
        self._cached_tile_px: int  = 0
        self._dirty:          bool = True

        self._m        = None
        self._mlx_ptr  = None
        self._win_ptr  = None
        self._img_ptr  = None
        self._buf:     Optional[memoryview] = None
        self._sl:      int = 0   # size_line

    # ── Public ────────────────────────────────────────────────────────────────

    def run(self) -> None:
        m = mlx_module.Mlx()
        self._m = m

        mlx_ptr = m.mlx_init()
        win_ptr = m.mlx_new_window(mlx_ptr, WIN_W, WIN_H,
                                   f"A-Maze-ing")
        # Image covers only the maze area (above HUD)
        img_ptr = m.mlx_new_image(mlx_ptr, WIN_W, WIN_H)
        buf, _bpp, sl, _fmt = m.mlx_get_data_addr(img_ptr)

        self._mlx_ptr = mlx_ptr
        self._win_ptr = win_ptr
        self._img_ptr = img_ptr
        self._buf     = buf
        self._sl      = sl

        self._fit_to_window()

        m.mlx_key_hook(win_ptr, self._on_key, None)
        m.mlx_hook(win_ptr, 17, 0, self._on_close, None)
        m.mlx_loop_hook(mlx_ptr, self._on_loop, None)
        m.mlx_loop(mlx_ptr)

    # ── Input ─────────────────────────────────────────────────────────────────

    def _on_key(self, keycode: int, _param: object) -> None:
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
            self.offset_y += PAN_STEP; self._dirty = True
        elif keycode == KEY_DOWN:
            self.offset_y -= PAN_STEP; self._dirty = True
        elif keycode == KEY_LEFT:
            self.offset_x += PAN_STEP; self._dirty = True
        elif keycode == KEY_RIGHT:
            self.offset_x -= PAN_STEP; self._dirty = True

    def _on_close(self, _param: object) -> None:
        os._exit(0)

    def _on_loop(self, _param: object) -> None:
        if not self._dirty:
            return
        m = self._m
        if m and self._mlx_ptr and self._img_ptr:
            m.mlx_sync(self._mlx_ptr, m.SYNC_IMAGE_WRITABLE, self._img_ptr)
        self._render()
        if m and self._mlx_ptr and self._win_ptr and self._img_ptr:
            m.mlx_put_image_to_window(
                self._mlx_ptr, self._win_ptr, self._img_ptr, 0, 0
            )
            # Draw HUD text AFTER image blit so it appears on top
            self._draw_hud_text()
        self._dirty = False

    # ── Layout ────────────────────────────────────────────────────────────────

    def _fit_to_window(self) -> None:
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
        return max(4, int(TILE_SIZE * self.zoom))

    # ── Cache ─────────────────────────────────────────────────────────────────

    def _ensure_cache(self) -> None:
        tile_px = self._tile_px()
        if self._tile_cache and self._cached_tile_px == tile_px:
            return
        base = build_tile_cache(THEMES[self.theme_idx])
        scaled = base if tile_px == TILE_SIZE else {
            hv: _scale_tile(t, tile_px) for hv, t in base.items()
        }
        self._tile_cache = {hv: _tile_to_bgr(t) for hv, t in scaled.items()}
        self._cached_tile_px = tile_px

    # ── Rendering ─────────────────────────────────────────────────────────────

    def _render(self) -> None:
        if self._buf is None:
            return
        buf     = self._buf
        sl      = self._sl
        tile_px = self._tile_px()
        max_y   = WIN_H - HUD_H
        self._ensure_cache()

        # Background
        fl  = THEMES[self.theme_idx].floor
        row = bytes([fl[2], fl[1], fl[0], 255] * WIN_W)
        for y in range(WIN_H):
            buf[y * sl: y * sl + WIN_W * 4] = row

        # Tiles
        for r in range(self.maze.rows):
            for c in range(self.maze.cols):
                tile = self._tile_cache.get(self.maze.grid[r][c])
                if tile:
                    _blit_tile(buf, tile,
                               c * tile_px + self.offset_x,
                               r * tile_px + self.offset_y,
                               tile_px, sl, max_y)

        # '42' highlight
        if self.show_42 and self.maze.pattern42_cells:
            for r, c in self.maze.pattern42_cells:
                x0 = c * tile_px + self.offset_x
                y0 = r * tile_px + self.offset_y
                for y in range(max(0, y0), min(max_y, y0 + tile_px)):
                    for x in range(max(0, x0), min(WIN_W, x0 + tile_px)):
                        _blend(buf, x, y, 255, 200, 0, 80, sl, max_y)

        # Path
        if self.show_path and self.maze.path:
            self._draw_path(tile_px, sl, max_y)

        # Portals
        half = tile_px // 2
        er, ec = self.maze.entry
        xr, xc = self.maze.exit_
        self._draw_portal(ec*tile_px+self.offset_x+half,
                          er*tile_px+self.offset_y+half,
                          ENTRY_RINGS, False, sl, max_y)
        self._draw_portal(xc*tile_px+self.offset_x+half,
                          xr*tile_px+self.offset_y+half,
                          EXIT_RINGS, True, sl, max_y)

        # HUD background drawn into image
        hud_top = WIN_H - HUD_H
        _fill_rect(buf, 0, hud_top, WIN_W, WIN_H, 22, 22, 28, sl)
        # Divider line
        div = bytes([78, 60, 55, 255] * WIN_W)
        buf[hud_top * sl: hud_top * sl + WIN_W * 4] = div

    def _draw_path(self, tile_px: int, sl: int, max_y: int) -> None:
        buf = self._buf
        pr, pg, pb, pa = 80, 160, 255, 200
        half = tile_px // 2
        # Strip half-width: enough to look solid but not cover whole cell
        h = max(3, tile_px // 5)

        for i, (r, c) in enumerate(self.maze.path):
            px = c * tile_px + self.offset_x
            py = r * tile_px + self.offset_y
            cx = px + half
            cy = py + half

            # Collect directions to neighbours
            dirs = []
            if i > 0:
                pr2, pc2 = self.maze.path[i-1]
                dr, dc = r-pr2, c-pc2
                if dr == -1: dirs.append("N")
                elif dr == 1: dirs.append("S")
                elif dc == -1: dirs.append("W")
                elif dc == 1: dirs.append("E")
            if i < len(self.maze.path) - 1:
                nr, nc = self.maze.path[i+1]
                dr2, dc2 = nr-r, nc-c
                if dr2 == -1: dirs.append("N")
                elif dr2 == 1: dirs.append("S")
                elif dc2 == -1: dirs.append("W")
                elif dc2 == 1: dirs.append("E")

            # Always fill the centre square first — this fills corners automatically
            for y in range(max(0, cy-h), min(max_y, cy+h)):
                for x in range(max(0, cx-h), min(WIN_W, cx+h)):
                    _blend(buf, x, y, pr, pg, pb, pa, sl, max_y)

            # Then extend strips from centre to cell edge in each direction
            for d in dirs:
                if d == "N":
                    for y in range(max(0, py), min(max_y, cy-h)):
                        for x in range(max(0, cx-h), min(WIN_W, cx+h)):
                            _blend(buf, x, y, pr, pg, pb, pa, sl, max_y)
                elif d == "S":
                    for y in range(max(0, cy+h), min(max_y, py+tile_px)):
                        for x in range(max(0, cx-h), min(WIN_W, cx+h)):
                            _blend(buf, x, y, pr, pg, pb, pa, sl, max_y)
                elif d == "W":
                    for y in range(max(0, cy-h), min(max_y, cy+h)):
                        for x in range(max(0, px), min(WIN_W, cx-h)):
                            _blend(buf, x, y, pr, pg, pb, pa, sl, max_y)
                elif d == "E":
                    for y in range(max(0, cy-h), min(max_y, cy+h)):
                        for x in range(max(0, cx+h), min(WIN_W, px+tile_px)):
                            _blend(buf, x, y, pr, pg, pb, pa, sl, max_y)

    def _draw_portal(self, cx: int, cy: int,
                     rings: list, arrow_up: bool,
                     sl: int, max_y: int) -> None:
        buf = self._buf
        for radius, col in zip([14,10,7,4,2], rings):
            for dy2 in range(-radius, radius+1):
                for dx2 in range(-radius, radius+1):
                    if dx2*dx2 + dy2*dy2 <= radius*radius:
                        _blend(buf, cx+dx2, cy+dy2, *col, 220, sl, max_y)
        ar, ag, ab = (220, 255, 225) if not arrow_up else (255, 235, 190)
        if arrow_up:
            for dy2 in range(-3, 7):
                _blend(buf, cx-1, cy+dy2, ar, ag, ab, 255, sl, max_y)
                _blend(buf, cx,   cy+dy2, ar, ag, ab, 255, sl, max_y)
            for s in range(6):
                for dx2 in range(-5+s, 6-s):
                    _blend(buf, cx+dx2, cy-3-s, ar, ag, ab, 255, sl, max_y)
        else:
            for dy2 in range(-6, 4):
                _blend(buf, cx-1, cy+dy2, ar, ag, ab, 255, sl, max_y)
                _blend(buf, cx,   cy+dy2, ar, ag, ab, 255, sl, max_y)
            for s in range(6):
                for dx2 in range(-5+s, 6-s):
                    _blend(buf, cx+dx2, cy+3+s, ar, ag, ab, 255, sl, max_y)

    def _draw_hud_text(self) -> None:
        """Draw HUD text directly to window AFTER image blit — so it's on top."""
        m = self._m
        if not (m and self._mlx_ptr and self._win_ptr):
            return
        theme  = THEMES[self.theme_idx]
        path_s = "ON" if self.show_path else "OFF"
        zoom_s = f"{self.zoom:.1f}x"
        hud_y  = WIN_H - HUD_H + (HUD_H - 13) // 2

        items = [
            (f"1:regen",               0xC3C8D7),
            (f"2:path:{path_s}",       0x4BD750 if self.show_path else 0xC3C8D7),
            (f"3:{theme.name}",        0x64B4FF),
            (f"4:quit",                0xC85A5A),
            (f"+/-:{zoom_s}",          0xC3C8D7),
            (f"arrows:pan",            0xC3C8D7),
        ]
        x = 12
        for text, color in items:
            m.mlx_string_put(self._mlx_ptr, self._win_ptr, x, hud_y, color, text)
            x += len(text) * 8 + 20
            if x > WIN_W - 80:
                break


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> None:
    import argparse
    p = argparse.ArgumentParser(description="A-Maze-ing display")
    p.add_argument("maze_file")
    p.add_argument("--theme", type=int, default=0,
                   choices=range(len(THEMES)),
                   metavar=f"0-{len(THEMES)-1}")
    args = p.parse_args()
    try:
        MazeDisplay(args.maze_file, theme_idx=args.theme).run()
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    import pathlib
    sys.path.insert(0, str(pathlib.Path(__file__).parent.parent))
    main()

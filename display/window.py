"""
    display/window.py

    MazeDisplay — main window using mlx_CLXV.

    pixel writing:
        mlx_get_data_addr() returns a memoryview cast to bytes.
        Each pixel is 4 bytes at offset (y * size_line + x * 4).
        Byte order: Blue, Green, Red, 0xFF  (alpha must be 255).

    key codes (X11):
        ESC / 4 = quit    2 = path    3 = colour
        +/-     = zoom    arrows = pan
"""

import os
from typing import Callable, Optional

try:
    import mlx as mlx_module
except ModuleNotFoundError:
    mlx_module = None

from .parser import parse_maze_file
from .tiles import TILE_SIZE, THEMES, build_tile_cache

HUD_H: int = 46
ENTRY_COLOR = (0, 200, 80)  # green
EXIT_COLOR = (255, 80, 20)  # orange

# window settings
WIN_W: int = 2000
WIN_H: int = 1500
PAN_STEP: int = 40
ZOOM_STEP: float = 0.1
ZOOM_MIN: float = 0.2
ZOOM_MAX: float = 3.0

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


# Pixel helpers #########################################################


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
        # copy with slice
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
    """
        Blend a filled rectangle over the existing buffer contents.

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
    # blend formula: new = foreground * t + background * (1 - t)

    # a = 120
    # t = 120/255 = 0.47
    # new_blue  = 204 * 0.47 + existing_blue  * 0.53
    # new_green = 204 * 0.47 + existing_green * 0.53
    # new_red   = 255 * 0.47 + existing_red   * 0.53
    transparency = a / 255
    for y in range(max(0, y0), min(max_y, y1)):
        for x in range(max(0, x0), min(WIN_W, x1)):
            i = y * sl + x * 4
            buf[i] = int(b * transparency + buf[i] * (1 - transparency))
            buf[i + 1] = int(
                g * transparency + buf[i + 1] * (1 - transparency))
            buf[i + 2] = int(
                r * transparency + buf[i + 2] * (1 - transparency))
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
    result = bytearray(len(tile))
    for i in range(0, len(tile), 4):
        result[i] = tile[i + 2]
        result[i + 1] = tile[i + 1]
        result[i + 2] = tile[i]
        result[i + 3] = 255
    return result


def tile_to_window(
    buf: memoryview,
    tile: bytearray,
    dest_x: int,
    dest_y: int,
    tile_px: int,
    sl: int,
    max_y: int,
) -> None:
    """
        copy a tile into the MLX buffer at position (dx, dy).

        handles clipping on all edges for zoom
        only the visible portion of the tile is copied, row by row
        using slice assignment for fast memory copies.

        args:
            buf:     MLX image buffer (BGRX, row-major).
            tile:    BGRX tile bytearray from the tile cache.
            dest_x:      Destination x in pixels (can be negative if tile
            is off-screen left).
            dest_y:      Destination y in pixels (can be negative if tile
            is off-screen top).
            tile_px: Tile width and height in pixels at current zoom.
            sl:      Size line — row stride in bytes from mlx_get_data_addr().
            max_y:   Bottom clipping boundary (top of HUD bar).
    """
    src_x0 = max(0, -dest_x)
    src_x1 = min(tile_px, WIN_W - dest_x)

    if src_x0 >= src_x1:
        return

    dest_x0 = dest_x + src_x0  # where to start writing in the buffer
    num_bytes = (src_x1 - src_x0) * 4

    for tile_y in range(tile_px):
        window_y = dest_y + tile_y  # destination row in window
        if not (0 <= window_y < max_y):
            continue
        src_i = (tile_y * tile_px + src_x0) * 4  # start byte in tile
        dest_i = window_y * sl + dest_x0 * 4  # start byte in window
        buf[dest_i: dest_i + num_bytes] = tile[src_i: src_i + num_bytes]


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
            self,
            filepath: str,
            theme_idx: int = 0,
            on_regen: Optional[Callable] = None) -> None:
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

    # public ##########################################################

    def run(self) -> None:
        """
            initialise MLX, open the window and start the event loop.

            -creates the MLX connection, window and image buffer
            -registers three hooks — keyboard input, window close,
            per-frame rendering.
            -Calls mlx_loop() which never returns
                handing control to MLX for the rest of the program's lifetime.
        """
        m = mlx_module.Mlx()
        self.m = m

        mlx_ptr = m.mlx_init()
        win_ptr = m.mlx_new_window(mlx_ptr, WIN_W, WIN_H, "A-Maze-ing")

        # off-screen image buffer — same size as the maze area (above HUD)
        # draw to this image first, then pass it to the window
        img_ptr = m.mlx_new_image(mlx_ptr, WIN_W, WIN_H)

        # unpacking to get the direct pointer to the
        # image's raw pixel bytes as a memoryview
        buf, bits_p_pixel, sl, format = m.mlx_get_data_addr(img_ptr)

        self.mlx_ptr = mlx_ptr
        self.win_ptr = win_ptr
        self.img_ptr = img_ptr
        self.buf = buf  # memoryview for mlx
        self.sl = sl  # size of line

        # calculate zoom and center offsets
        self.fit_to_window()

        # callbacks mlx calls them when events occur
        m.mlx_key_hook(win_ptr, self.on_key, None)  # keypress
        m.mlx_hook(win_ptr, 33, 0, self.on_close, None)  # window close button
        m.mlx_loop_hook(mlx_ptr, self.on_loop, None)  # loop for every frame
        m.mlx_loop(mlx_ptr)

    # input #########################################################
    def on_key(self, keycode: int, _param: object) -> None:
        """
            Handle keyboard input and update display state.

            Maps X11 keycodes to display actions. Sets _dirty = True
            on every handled key to trigger a redraw on the next frame.

            Keybindings:
                ESC / 4:    Quit the program immediately.
                1:          Regenerate the maze via on_regen callback,
                            reload the maze file and refit to window.
                2:          Toggle the solution path overlay.
                3:          Cycle to the next colour theme,
                            invalidates tile cache.
                + / =:      Zoom in, invalidates tile cache.
                -:          Zoom out, invalidates tile cache.
                Up:        Pan the view upward.
                Down:      Pan the view downward.
                Left:      Pan the view left.
                Right:     Pan the view right.

            Args:
                keycode: X11 keycode of the pressed key.
                _param:  Unused MLX hook parameter.
    """
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
            self._tile_cache: dict[int, bytearray] = {}
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

    def on_close(self, param: object) -> None:
        os._exit(0)

    def on_loop(self, param: object) -> None:
        """
            Per-frame callback called by mlx_loop on every iteration.

            Skips rendering if nothing has changed (_dirty = False).
            When dirty:
            -syncs the image buffer for writing
            -renders the frame
            -puts the image to the window
            -draws HUD text on top
            -Clears _dirty after rendering.

            Rendering order:
                1. mlx_sync      — acquire write access to the image buffer.
                2. render()      — create maze, path, portals and
                                    HUD background.
                3. mlx_put_image — place the image buffer to the window.
                4. draw_hud_text — draw text directly onto the window on top.

            Args:
                _param: Unused MLX hook parameter.
        """

        #   mlx runs 2 things at the same time:
        #   -GPU/display thread  →  reading  the buffer to show it on screen
        #   -code    →  writing  the buffer to draw the next frame
        #
        #   mlx_sync(SYNC_IMAGE_WRITABLE)
        #   |
        #   |- waits until GPU is done reading
        #   |- locks the buffer
        #   |- now safe to write → render() runs

        if not self._dirty:
            return
        m = self.m
        if m and self.mlx_ptr and self.img_ptr:
            # get buffer write access - lock
            m.mlx_sync(self.mlx_ptr, m.SYNC_IMAGE_WRITABLE, self.img_ptr)
        # build tile cache if needed
        self.render()  # write
        if m and self.mlx_ptr and self.win_ptr and self.img_ptr:
            # place buffer into on to the window
            m.mlx_put_image_to_window(
                self.mlx_ptr, self.win_ptr, self.img_ptr, 0, 0)  # show result
            # Draw HUD text AFTER image blit so it appears on top
            self.draw_hud_text()
        self._dirty = False

    # layout ###########################################################
    def fit_to_window(self) -> None:
        """
            Calculate zoom and offsets to centre the maze in the window.

            Computes the largest zoom level that fits the entire maze in the
            usable area (window height minus HUD bar), capped at 1.5x to avoid
            over-magnification on small mazes. Then centres the maze both
            horizontally and vertically. Invalidates the tile cache since the
            tile size may have changed.
        """
        usable_h = WIN_H - HUD_H
        zoom_x = WIN_W / (self.maze.cols * TILE_SIZE)
        zoom_y = usable_h / (self.maze.rows * TILE_SIZE)
        self.zoom = round(min(zoom_x, zoom_y, 0.7), 1)
        tile_px = self.tile_px()
        self.offset_x = (WIN_W - self.maze.cols * tile_px) // 2
        self.offset_y = (usable_h - self.maze.rows * tile_px) // 2
        self._tile_cache = {}
        self._dirty = True

    def tile_px(self) -> int:
        """
            Calculate the current tile size in pixels based on zoom level.

            Returns:
            Tile width and height in pixels, minimum 4 to ensure
            tiles are always visible even at maximum zoom out.
        """
        return max(4, int(TILE_SIZE * self.zoom))

    # cache ##############################################################
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
        self._cached_tile_px: int = 0
        if self._tile_cache and self._cached_tile_px == tile_px:
            return
        base = build_tile_cache(THEMES[self.theme_idx])
        scaled = (
            base
            if tile_px == TILE_SIZE
            else {
                digit: scale_tile(tile, tile_px)
                for digit, tile in base.items()
            }
        )
        self._tile_cache = {
            digit: tile_to_bgr(tile)
            for digit, tile in scaled.items()
        }
        self._cached_tile_px = tile_px

    # rendering ###########################################################
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
        #                b       g     r
        bg_row = bytes([fl[2], fl[1], fl[0], 255] * WIN_W)
        for y in range(WIN_H):
            buf[y * sl: y * sl + WIN_W * 4] = bg_row

        # Tiles
        for r in range(self.maze.rows):
            for c in range(self.maze.cols):
                tile = self._tile_cache.get(self.maze.grid[r][c])
                if tile:
                    tile_to_window(
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
        entry_row, entry_col = self.maze.entry
        exit_row, exit_col = self.maze.exit_
        self.draw_portal(
            entry_col * tile_px + self.offset_x + half,
            entry_col * tile_px + self.offset_y + half,
            ENTRY_COLOR,
            sl,
            max_y,
            tile_px
        )
        self.draw_portal(
            exit_col * tile_px + self.offset_x + half,
            exit_row * tile_px + self.offset_y + half,
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
        from one cell centre to the next, with thickness 2h
        corners are seamless because rectangles share endpoints at centres.

        args:
            tile_px: Current tile size in pixels.
            sl:      Size line — row stride in bytes from mlx_get_data_addr().
            max_y:   Bottom clipping boundary (top of HUD bar).
        """
        if self.buf is None:
            return
        buf = self.buf
        pr, pg, pb = 80, 160, 255
        half = tile_px // 2
        h = max(3, tile_px // 5)

        path = self.maze.path
        for i in range(len(path) - 1):
            r1, c1 = path[i]
            r2, c2 = path[i + 1]
            center_col_px1 = c1 * tile_px + self.offset_x + half
            center_row_px1 = r1 * tile_px + self.offset_y + half
            center_col_px2 = c2 * tile_px + self.offset_x + half
            center_row_px2 = r2 * tile_px + self.offset_y + half
            if center_col_px1 == center_col_px2:
                x0, x1 = center_col_px1 - h, center_col_px1 + h
                y0, y1 = (min(center_row_px1, center_row_px2) - h,
                          max(center_row_px1, center_row_px2) + h)
            else:
                x0, x1 = (min(center_col_px1, center_col_px2) - h,
                          max(center_col_px1, center_col_px2) + h)
                y0, y1 = center_row_px1 - h, center_row_px1 + h
            fill_rect(buf, x0, y0, x1, y1, pr, pg, pb, sl, max_y)

    def draw_portal(
            self, cx: int,
            cy: int, color: tuple, sl: int, max_y: int, tile_px: int) -> None:
        """
            draw a filled circle marking an entry or exit portal.

            formula x² + y² ≤ r² to determine which pixels
            fall inside the circle, then draws each as a single pixel.

            args:
                cx:    Centre x in pixels.
                cy:    Centre y in pixels.
                color: RGB tuple for the circle colour.
                sl:    Size line — row stride in bytes from mlx_get_data_addr()
                max_y: Bottom clipping boundary (top of HUD bar).
        """
        if self.buf is None:
            return
        buf = self.buf
        r, g, b = color
        radius = max(4, tile_px // 4)
        for y2 in range(-radius, radius + 1):
            for x2 in range(-radius, radius + 1):
                if x2 * x2 + y2 * y2 <= radius * radius:
                    fill_rect(
                        buf,
                        cx + x2,
                        cy + y2,
                        cx + x2 + 1,
                        cy + y2 + 1,
                        r,
                        g,
                        b,
                        sl,
                        max_y,
                    )

    def draw_hud_text(self) -> None:
        """
            draw control hints onto the HUD bar.

            called after mlx_put_image_to_window so text appears on top
            of the image.
            uses mlx_string_put which writes directly to
            the window rather than the image buffer.

            items are spaced by character count — each character is 8px wide
            with a 20px gap between items. stops early if items would overflow
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
            # write directly to the window
            m.mlx_string_put(self.mlx_ptr, self.win_ptr, x, hud_y, color, text)
            x += len(text) * 8 + 20
            if x > WIN_W - 80:
                break

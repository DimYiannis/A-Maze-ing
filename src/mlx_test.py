import sys
sys.path.append("./mlx_CLXV-2.2")
import mlx
import os

def key_hook(keycode, game):
    # exit using esc
    if keycode == 65307:
        os._exit(0)

# needs fix
def close_hook(game):
    os._exit(0)


m = mlx.Mlx()
mlx_ptr = m.mlx_init()
win_ptr = m.mlx_new_window(mlx_ptr, 1400, 1400, "MLX Test")

# Draw a visible 50x50 white square in the middle
for y in range(175, 225):
    for x in range(175, 225):
        m.mlx_pixel_put(mlx_ptr, win_ptr, x, y, 0xFFFFFF)

m.mlx_hook(win_ptr, 17, 0, close_hook, None)
m.mlx_key_hook(win_ptr, key_hook, None)

# Start the loop
m.mlx_loop(mlx_ptr)


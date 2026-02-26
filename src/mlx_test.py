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
print("MLX ptr:", mlx_ptr)
print("WIN ptr:", win_ptr)

#creates image in memory
img_ptr = m.mlx_new_image(mlx_ptr, 400, 400)

#gives raw pixel buffer modify the buffer
buf, bpp, size_line, fmt = m.mlx_get_data_addr(img_ptr)

# Sync before writing
m.mlx_sync(mlx_ptr, m.SYNC_IMAGE_WRITABLE, img_ptr)


row = bytes([0, 0, 255, 255] * 400) # BGRX: B=0 G=0 R=255 
for y in range(400): 
    buf[y * size_line : y * size_line + 400 * 4] = row

# copies image to the window
def render(param):
    m.mlx_put_image_to_window(mlx_ptr, win_ptr, img_ptr, 0, 0)
    return 0


print("bpp:", bpp)
print("size_line:", size_line)
print("format:", fmt)

m.mlx_loop_hook(mlx_ptr, render, None)
m.mlx_hook(win_ptr, 17, 0, close_hook, None)
m.mlx_key_hook(win_ptr, key_hook, None)

# Start the loop
m.mlx_loop(mlx_ptr)




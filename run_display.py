# """Launcher — run from the project root: python3 run_display.py maze.txt"""
# import sys
# import os
#
# sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
#
# from display.window import main
#
# main()

import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
import mlx as mlx_module

m = mlx_module.Mlx()
mlx_ptr = m.mlx_init()
win_ptr = m.mlx_new_window(mlx_ptr, 400, 400, "test")
# img_ptr = m.mlx_new_image(mlx_ptr, 400, 400)
#
# buf, bpp, size_line, fmt = m.mlx_get_data_addr(img_ptr)
# print(f"bpp={bpp} size_line={size_line} fmt={fmt} buf type={type(buf)}")
#
# # Fill entire image bright red
# row = bytes([0, 0, 255, 0] * 400)   # BGRX: B=0 G=0 R=255
# for y in range(400):
#     buf[y * size_line : y * size_line + 400 * 4] = row
# Draw directly to window — no image buffer

for y in range(100, 200):
    for x in range(100, 200):
        m.mlx_pixel_put(mlx_ptr, win_ptr, x, y, 0x0000FF)
m.mlx_do_sync(mlx_ptr)

# m.mlx_put_image_to_window(mlx_ptr, win_ptr, img_ptr, 0, 0)

def close(p): os._exit(0)
m.mlx_hook(win_ptr, 17, 0, close, None)
m.mlx_loop(mlx_ptr)

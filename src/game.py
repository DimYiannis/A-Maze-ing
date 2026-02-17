import sys
sys.path.append("./mlx_CLXV-2.2")

import mlx
print(type(mlx.Mlx()))
print(mlx.Mlx())


# def close(param):
#     sys.exit(0)
#
# def handle_key(keycode, param):
#     if keycode == 65307:  # ESC
#         sys.exit(0)

#Creating instance to access methods of the Mlx class
m = mlx.Mlx()
print(dir(m))

# # Hook the window close (event 17)
# m.mlx_hook(win_ptr, 17, 0, close, None)
# m.mlx_key_hook(win_ptr, handle_key, None)
#
# print("Starting loop...")
# m.mlx_loop(mlx_ptr)

from src.map_loader import load_map
from src.renderer import draw_map
from src.events import register_events

class Game:
    def __init__(self, map_file):
        self.map = load_map(map_file)
        self.mlx_lib = m
        self.mlx = m.mlx_init()
        self.win = m.mlx_new_window(self.mlx, 800, 600, "Maze")

    def run(self):
        draw_map(self)
        register_events(self)
        self.mlx_lib.mlx_loop(self.mlx)

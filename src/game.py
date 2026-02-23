import sys
sys.path.append("./mlx_CLXV-2.2")

import mlx
print(type(mlx.Mlx()))
print(mlx.Mlx())


#Creating instance to access methods of the Mlx class
m = mlx.Mlx()
print(dir(m))


from src.map_loader import load_map
from src.renderer import draw_map
from src.events import register_events

class Game:
    def __init__(self, map_file):
        self.map = load_map(map_file)

        self.mlx_lib = m
        self.mlx =  self.mlx_lib.mlx_init()
        self.win =  self.mlx_lib.mlx_new_window(self.mlx, 1800, 1600, "Maze")

    def run(self):
        # draw big visible square
        for y in range(100, 200):
            for x in range(100, 200):
                self.mlx_lib.mlx_pixel_put(self.mlx, self.win, x, y, 0xFF0000)
        #draw_map(self)
        register_events(self)
        self.mlx_lib.mlx_loop(self.mlx)

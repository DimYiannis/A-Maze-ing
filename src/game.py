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

        self.mlx_lib = mlx.Mlx()

        self.mlx = self.mlx_lib.mlx_init()

        self.win = self.mlx_lib.mlx_new_window(
            self.mlx, 1800, 1600, "Maze"
        )

        self.img = self.mlx_lib.mlx_new_image(
            self.mlx, 1800, 1600
        )

        self.buffer = bytearray(1800 * 1600 * 4)

    def render(self):

        self.render()

        draw_map(self)

        self.mlx_lib.mlx_put_image_to_window(
            self.mlx, self.win, self.img, 0, 0
        )

    def run(self):

        register_events(self)

        self.mlx_lib.mlx_loop(self.mlx)

import sys
sys.path.append("./mlx_CLXV-2.2")

from mlx import *
from src.map_loader import load_map
from src.renderer import draw_map
from src.events import register_events

class Game:
    def __init__(self, map_file):
        self.map = load_map(map_file)

        self.mlx = mlx_init()
        self.win = mlx_new_window(self.mlx, 800, 600, "Maze")

    def run(self):
        draw_map(self)
        register_events(self)
        mlx_loop(self.mlx)

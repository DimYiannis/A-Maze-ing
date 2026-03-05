import sys
from maze.maze_algo import main as generate
from display.window import MazeDisplay


def regenerate():
    generate()


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 a_maze_ing.py config.txt")
        sys.exit(1)
    generate()
    display = MazeDisplay("maze.txt", on_regen=regenerate)
    display.run()

import sys
from maze.maze_algo import main as _generate
from display.window import main as display


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 a_maze_ing.py config.txt")
        sys.exit(1)
    _generate()        # reads sys.argv[1] itself
    display("maze.txt")  # reads the output file

import sys
import random
from typing import Optional
from mazegen import MazeGenerator
from mazegen.maze_algo import parse_config, validate_config
from display.window import MazeDisplay


def regenerate() -> None:
    """
        Regenerate the maze with a new random seed.

        Called by MazeDisplay when the user presses key 1.
        run() with a fresh random seed so the
        new maze is different from the previous one.
    """
    run(config, seed=random.randint(0, 999999))


def run(config: dict, seed: Optional[int] = None) -> None:
    """
        Generate, solve and write the maze to disk.

        Sets the recursion limit based on maze size to prevent
        stack overflow during DFS generation. If no solution is
        found, retries with a new random seed.

        Args:
            config: Parsed configuration dictionary from parse_config().
            seed:   Random seed for the maze generator. If None, uses
                    SEED from config or a random value.
    """
    if seed is None:
        seed = config.get("SEED", random.randint(0, 999999))
    print(f"Seed: {seed}")
    sys.setrecursionlimit(config["WIDTH"] * config["HEIGHT"] * 2)
    mg = MazeGenerator(config["WIDTH"], config["HEIGHT"], seed)
    mg.generate(perfect=config["PERFECT"])
    path = mg.solve(enter_maze, exit_maze)
    if not path:
        run(config, seed=random.randint(0, 999999))
        return
    print("Maze generated!")
    mg.write(
        enter_maze,
        exit_maze,
        path,
        config["OUTPUT_FILE"]
    )


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2:
            print("Usage: python3 a_maze_ing.py config.txt")
            sys.exit(1)
        filename = sys.argv[1]
        config = parse_config(filename)
        validate_config(config)
        run(config, config["SEED"])
        display = MazeDisplay("maze.txt", on_regen=regenerate)
        display.run()
    except Exception:
        print("wrong config.txt")


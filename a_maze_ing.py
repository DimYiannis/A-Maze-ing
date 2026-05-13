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


def run(config: dict, seed: Optional[int] = None, _retries: int = 0) -> None:
    """
        Generate, solve and write the maze to disk.

        Sets the recursion limit based on maze size to prevent
        stack overflow during DFS generation. If no solution is
        found, retries with a new random seed.

        Args:
            config:   Parsed configuration dictionary from parse_config().
            seed:     Random seed for the maze generator. If None, uses
                      SEED from config or a random value.
            _retries: Internal retry counter to prevent infinite recursion.
    """
    if _retries > 10:
        print("Error: could not generate solvable maze after 10 attempts")
        sys.exit(1)
    if seed is None:
        seed = config.get("SEED", random.randint(0, 999999))
    print(f"Seed: {seed}")
    sys.setrecursionlimit(config["WIDTH"] * config["HEIGHT"] * 2)
    mg = MazeGenerator(config["WIDTH"], config["HEIGHT"], seed)
    mg.generate(perfect=config["PERFECT"])
    path = mg.solve(config["ENTRY"], config["EXIT"])
    if not path:
        run(config, seed=random.randint(0, 999999), _retries=_retries + 1)
        return
    print("Maze generated!")
    mg.write(
        config["ENTRY"],
        config["EXIT"],
        path,
        config["OUTPUT_FILE"]
    )


if __name__ == "__main__":
        if len(sys.argv) != 2:
            print("Usage: python3 a_maze_ing.py config.txt")
            sys.exit(1)
        filename = sys.argv[1]
        config = parse_config(filename)
        validate_config(config)
        run(config, config.get("SEED"))
        display = MazeDisplay(config["OUTPUT_FILE"], on_regen=regenerate)
        display.run()


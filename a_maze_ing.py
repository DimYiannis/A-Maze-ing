import sys
import random
from typing import Optional
from mazegen import MazeGenerator
from mazegen.maze_algo import parse_config, validate_config
from display.window import MazeDisplay


def regenerate() -> None:
    run(config, seed=random.randint(0, 999999))


def run(config: dict, seed: Optional[int] = None) -> None:
    enter_maze = config["ENTRY"]
    exit_maze = config["EXIT"]
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
        config["OUTPUT_FILE"],
    )


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python3 a_maze_ing.py config.txt")
        sys.exit(1)
    filename = sys.argv[1]
    config = parse_config(filename)
    validate_config(config)
    run(config, config["SEED"])
    display = MazeDisplay("maze.txt", on_regen=regenerate)
    display.run()

*This project has been created as part of the 42 curriculum by glieuw-a and ydimitra.*

# A-Maze-ing

## Description

A-Maze-ing is a maze generation and visualisation project. The goal is to generate
random mazes from a configuration file, solve them, and display them in an interactive
graphical window. The maze contains a hidden "42" pattern made of fully walled cells.

The project is split into two parts:
- **mazegen** — a reusable Python package for maze generation and solving
- **display** — an interactive visualiser built on top of miniLibX (mlx_CLXV)

## Instructions

### Requirements
- Python 3.10+
- miniLibX (mlx_CLXV 2.2)

### Installation
```bash
pip install -r requirements.txt
```

### Run
```bash
make run
```
or directly:
```bash
python3 a_maze_ing.py config.txt
```

### Controls
| Key | Action |
|-----|--------|
| 1 | Regenerate maze |
| 2 | Toggle solution path |
| 3 | Cycle colour theme |
| 4 / ESC | Quit |
| + / - | Zoom in / out |
| Arrow keys | Pan |

### Config file format
```
WIDTH=40          # maze width in cells
HEIGHT=30         # maze height in cells
ENTRY=0,0         # entry point (x,y)
EXIT=39,29        # exit point (x,y)
SEED=42           # random seed (optional, random if omitted)
PERFECT=True      # True = perfect maze, False = maze with loops
OUTPUT_FILE=maze.txt  # output file path
```

## Maze Generation Algorithm

This project uses a **recursive backtracker** (depth-first search).

### How it works
1. Start at cell (0,0), mark it visited
2. Shuffle the 4 directions randomly
3. For each unvisited neighbour, remove the wall between them and recurse
4. Backtrack when no unvisited neighbours remain

### Why this algorithm
- Produces perfect mazes by default (one path between any two cells)
- Simple to implement and understand
- Generates mazes with long, winding corridors which are visually interesting
- Easy to extend for imperfect mazes by removing extra walls after generation

## Reusable Package — mazegen

The `mazegen` package is available as a standalone pip-installable package.

### Installation
```bash
pip install mazegen-1.0.0-py3-none-any.whl
```

### Usage
```python
from mazegen import MazeGenerator

mg = MazeGenerator(width=40, height=30, seed=42)
mg.generate(perfect=True)
path = mg.solve((0, 0), (39, 29))
mg.write((0, 0), (39, 29), path, "maze.txt")
```

### Build from source
```bash
pip install build
python -m build
# or
uv build --out-dir .
```

## Team and Project Management

### Team
- glieuw-a - maze generation algorithm, solver
- **ydimitra** -  package structure, display

### Planning
- Week 1: maze generation and file format, visualiser
- Week 2: display, package, Makefile, README, testing

### What worked well
- The recursive backtracker was straightforward to implement
- The display pipeline (tiles, overlays, MLX) came together cleanly

### What could be improved
- More maze generation algorithms (Prim's, Kruskal's)
- Adding animations
- Better display of the maze (adding depth)
- A player mode where you navigate the maze yourself

### Tools used
- Python 3.12
- miniLibX (mlx_CLXV)
- mypy + flake8 for type checking and linting
- uv for package management
- Claude (Anthropic) — used for code review, debugging, explaining concepts,
  docstrings, and refactoring suggestions throughout the project

## Resources

- [Maze generation algorithms — Wikipedia](https://en.wikipedia.org/wiki/Maze_generation_algorithm)
- [Python packaging guide](https://packaging.python.org/en/latest/tutorials/packaging-projects/)
- [miniLibX documentation](https://harm-smits.github.io/42docs/libs/minilibx)
- [mypy documentation](https://mypy.readthedocs.io)

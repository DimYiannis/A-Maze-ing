import random
from collections import deque
import sys
from typing import Any, Optional

NORTH = 1
EAST = 2
SOUTH = 4
WEST = 8


def parse_config(filename: str) -> dict[str, Any]:
    """
        Parse a maze configuration file into a dictionary.

        Reads key=value pairs from a text file, skipping blank lines
        and lines starting with '#'. Converts values to the appropriate
        Python type based on the key name.

        Args:
            filename: Path to the configuration file.

        Returns:
            Dictionary with keys WIDTH, HEIGHT, SEED (int),
            ENTRY, EXIT (tuple[int, int]), PERFECT (bool),
            and OUTPUT_FILE (str).
    """
    parse: dict[str, Any] = {}
    key: str
    value: int | str | tuple[int, int] | bool
    with open(filename, "r") as file:
        for line in file:
            if line.startswith("#"):
                continue
            line = line.strip()
            if line == "":
                continue
            key, value = line.split("=")
            if key == "WIDTH" or key == "HEIGHT" or key == "SEED":
                value = int(value)
            elif key == "ENTRY" or key == "EXIT":
                digit1, digit2 = value.split(",")
                value = (int(digit1), int(digit2))
            elif key == "PERFECT":
                value = value == "True"
            parse[key] = value
    return parse


def validate_config(config: dict) -> None:
    """
        Validate maze configuration values.

        Checks that entry and exit coordinates are within the maze bounds
        and that they are not the same cell. Prints an error and exits
        with code 1 if any check fails.

        Args:
            config: Parsed configuration dictionary from parse_config().
    """
    w, h = config["WIDTH"], config["HEIGHT"]
    ex, ey = config["ENTRY"]
    xx, xy = config["EXIT"]
    try:
        if not (0 <= ey < h and 0 <= ex < w):
            raise ValueError(
                f"ENTRY ({ex},{ey}) out of bounds for {w}×{h} grid")
        if not (0 <= xy < h and 0 <= xx < w):
            raise ValueError(
                f"EXIT ({xx},{xy}) out of bounds for {w}×{h} grid")
        if config["ENTRY"] == config["EXIT"]:
            raise ValueError("ENTRY and EXIT must be different")
    except ValueError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"{e}")
        sys.exit(1)


class MazeGenerator:
    def __init__(self, width: int, height: int, seed: Optional[int] = None):
        """
            Initialise the maze grid and random seed.

            Args:
                width:  Number of columns.
                height: Number of rows.
                seed:   Optional random seed. If None, a random seed is chosen
                    and stored in self.seed for reproducibility.
        """
        self.width = width
        self.height = height
        self.seed = seed if seed is not None else random.randint(0, 999999)
        self.maze = self._create_grid()
        self.visited = [[False for _ in range(width)] for _ in range(height)]
        random.seed(self.seed)

    def generate(self, perfect: bool = True) -> list[list[int]]:
        """
            Generate the maze and return the grid.

            -runs the recursive backtracker
            -optionally adds loops for an imperfect maze
            -enforces outer border walls
            -places the '42' pattern at the centre.

            Args:
                perfect: If True, generates a perfect maze (one path between
                    any two cells). If False, removes extra walls to
                    create loops and multiple paths.

            Returns:
                2D list of integers representing the maze grid.
        """
        self._generate(0, 0)
        if not perfect:
            self._add_loops()
        self._enforce_borders()
        self._place_42_pattern()
        return self.maze

    def solve(self, entry: tuple, exit_: tuple) -> str:
        """
            Solve the maze and return the path string.
                -finds the shortest path from entry to exit using BFS.

            Args:
                entry:  Entry cell as (x, y) tuple.
                exit_:  Exit cell as (x, y) tuple.

            Returns:
                String of N/E/S/W direction letters from entry to exit,
                or empty string if no path exists.
        """
        return self._solve_maze(entry[1], entry[0], exit_[1], exit_[0])

    def write(
            self,
            entry: tuple, exit_: tuple, path: str, filename: str) -> None:
        """
            Write the maze to a file.

            Args:
                entry:    Entry cell as (x, y) tuple.
                exit_:    Exit cell as (x, y) tuple.
                path:     Solution path string from solve().
                filename: Output file path.
        """
        self._write_output(
            entry[1], entry[0], exit_[1], exit_[0], path, filename)

    # private

    def _create_grid(self) -> list[list[int]]:
        """
            Create a fully walled grid.

            Returns:
                2D list of size height × width filled with 15 (all walls set).
        """
        return [[15 for _ in range(self.width)] for _ in range(self.height)]

    def _place_42_pattern(self) -> bool:
        """
            Place the '42' pattern at the centre of the maze.

            Sets a pixel-art '4' and '2' made of fully walled cells (value 15)
            at the centre of the grid. These cells are also marked as visited
            so the generator never carves through them.

            Returns:
                True if the pattern was placed, False if the maze is too small.
        """
        if self.height < 7 or self.width < 11:
            print("Maze is too small to display 42")
            return False

        # centre the pattern
        start_row = (self.height - 7) // 2
        start_col = (self.width - 9) // 2
        pattern = [
            (0, 0),
            (1, 0),
            (2, 0),
            (2, 1),
            (1, 2),
            (2, 2),
            (3, 2),
            (4, 2),  # "4"
            (0, 4),
            (0, 5),
            (0, 6),
            (1, 6),
            (2, 4),
            (2, 5),
            (2, 6),
            (3, 4),
            (4, 4),
            (4, 5),
            (4, 6),  # "2"
        ]

        for row, col in pattern:
            r = start_row + row
            c = start_col + col
            if 0 <= r < self.height and 0 <= c < self.width:
                self.maze[r][c] = 15
                self.visited[r][c] = True
        return True

    def _remove_wall(self, yindex: int, xindex: int, direction: int) -> None:
        """
            Remove a wall between a cell and its neighbour.

            Clears the wall bit on both sides — the cell and the neighbouring
            cell — to keep the maze coherent.

            Args:
                yindex:    Row of the cell.
                xindex:    Column of the cell.
                direction: Wall to remove (NORTH, EAST, SOUTH or WEST).
        """
        self.maze[yindex][xindex] &= ~direction
        if direction == NORTH and yindex > 0:
            self.maze[yindex - 1][xindex] &= ~SOUTH
        if direction == EAST and xindex < self.width - 1:
            self.maze[yindex][xindex + 1] &= ~WEST
        if direction == SOUTH and yindex < self.height - 1:
            self.maze[yindex + 1][xindex] &= ~NORTH
        if direction == WEST and xindex > 0:
            self.maze[yindex][xindex - 1] &= ~EAST

    def _add_loops(self) -> None:
        """
            Remove random interior walls to create loops in the maze.

            Removes approximately 10% of walls to create an imperfect maze
            with multiple paths between cells. Never removes outer border
            walls or walls belonging to the '42' pattern cells.
        """
        num_loops = (self.width * self.height) // 10
        for _ in range(num_loops):
            row = random.randint(0, self.height - 1)
            col = random.randint(0, self.width - 1)
            if self.maze[row][col] == 15 and self.visited[row][col]:
                continue
            direction = random.choice([NORTH, EAST, SOUTH, WEST])
            if direction == NORTH and row == 0:
                continue
            if direction == EAST and row == self.height - 1:
                continue
            if direction == SOUTH and col == 0:
                continue
            if direction == WEST and col == self.width - 1:
                continue
            self._remove_wall(row, col, direction)

    def _enforce_borders(self) -> None:
        """
            Ensure all outer border walls are always present.

            Sets wall bits on all cells at the edges of the maze facing
            outward.
            Called after generation and loop-adding to restore
            any border walls that were accidentally removed.
        """
        for c in range(self.width):
            self.maze[0][c] |= NORTH
            self.maze[self.height - 1][c] |= SOUTH
        for r in range(self.height):
            self.maze[r][0] |= WEST
            self.maze[r][self.width - 1] |= EAST

    def _generate(self, start_y: int, start_x: int) -> None:
        """
            Recursively carve passages using depth-first search.

            -marks the current cell as visited
            -shuffles the 4 directions
            -recursively visits each unvisited neighbour by removing
            the wall between them.

            Args:
                start_y: Row of the current cell.
                start_x: Column of the current cell.
        """
        direction_list = [NORTH, EAST, SOUTH, WEST]
        random.shuffle(direction_list)
        self.visited[start_y][start_x] = True
        for direction in direction_list:
            if direction == NORTH:
                neighbour_y, neighbour_x = start_y - 1, start_x
            elif direction == EAST:
                neighbour_y, neighbour_x = start_y, start_x + 1
            elif direction == SOUTH:
                neighbour_y, neighbour_x = start_y + 1, start_x
            elif direction == WEST:
                neighbour_y, neighbour_x = start_y, start_x - 1
            if (
                0 <= neighbour_y < self.height
                and 0 <= neighbour_x < self.width
                and not self.visited[neighbour_y][neighbour_x]
            ):
                self._remove_wall(start_y, start_x, direction)
                self._generate(neighbour_y, neighbour_x)

    def _reconstruct_path(
            self, traveled_to: list, exit_y: int, exit_x: int) -> str:
        """
            Reconstruct the solution path by backtracking from the exit.

            Walks backwards from the exit cell to the entry using the
            direction stored in traveled_to at each cell, building the
            forward path string.

            Args:
                traveled_to: 2D grid storing the direction taken to reach
                    each cell, or "START" for the entry cell.
                exit_y:      Row of the exit cell.
                exit_x:      Column of the exit cell.

            Returns:
                String of N/E/S/W letters from entry to exit.
        """
        path = ""
        y, x = exit_y, exit_x
        while traveled_to[y][x] != "START":
            letter = traveled_to[y][x]

            if letter == "N":
                y += 1
                path += "N"
            elif letter == "E":
                x -= 1
                path += "E"
            elif letter == "S":
                y -= 1
                path += "S"
            elif letter == "W":
                x += 1
                path += "W"
        return path[::-1]

    def _solve_maze(
            self, entry_y: int, entry_x: int, exit_y: int, exit_x: int) -> str:
        """
            Find the shortest path from entry to exit using BFS.

            Explores the maze level by level from the entry cell, following
            only open walls. Returns the path as soon as the exit is reached.

            Args:
                entry_y: Row of the entry cell.
                entry_x: Column of the entry cell.
                exit_y:  Row of the exit cell.
                exit_x:  Column of the exit cell.

            Returns:
                String of N/E/S/W direction letters, or "" if no path exists.
        """
        traveled_to: list[
            list[Optional[str]]] = [[
                None] * self.width for _ in range(self.height)]
        queue: deque[tuple[int, int]] = deque()
        queue.append((entry_y, entry_x))
        traveled_to[entry_y][entry_x] = "START"
        direction_list = {NORTH: "N", EAST: "E", SOUTH: "S", WEST: "W"}
        while queue:
            y, x = queue.popleft()
            if y == exit_y and x == exit_x:
                return self._reconstruct_path(
                    traveled_to,
                    exit_y,
                    exit_x,
                )
            for direction, letter in direction_list.items():
                if direction == NORTH:
                    neighbour_y, neighbour_x = y - 1, x
                elif direction == EAST:
                    neighbour_y, neighbour_x = y, x + 1
                elif direction == SOUTH:
                    neighbour_y, neighbour_x = y + 1, x
                elif direction == WEST:
                    neighbour_y, neighbour_x = y, x - 1
                if (
                    0 <= neighbour_y < self.height
                    and 0 <= neighbour_x < self.width
                    and not traveled_to[neighbour_y][neighbour_x]
                    and not self._has_wall(self.maze[y][x], direction)
                ):
                    queue.append((neighbour_y, neighbour_x))
                    traveled_to[neighbour_y][neighbour_x] = letter
        return ""

    def _has_wall(self, cell: int, direction: int) -> bool:
        """Checks whether a cell has a wall in the given direction.

        Args:
            cell (int): Bitmask representing the walls present in the cell.
            direction (int): Bitmask value of the direction to check.

        Returns:
            bool: True if the wall in the given direction is present,
            False otherwise.
        """
        return bool(cell & direction)

    def _write_output(
        self,
        entry_y: int,
        entry_x: int,
        exit_y: int,
        exit_x: int,
        path: str,
        filename: str,
    ) -> None:
        """
            Write the maze grid and metadata to a file.

            Format:
                - One hex character per cell, one row per line
                - Blank line separator
                - Entry coordinates as x,y
                - Exit coordinates as x,y
                - Solution path string

            Args:
                entry_y:  Row of the entry cell.
                entry_x:  Column of the entry cell.
                exit_y:   Row of the exit cell.
                exit_x:   Column of the exit cell.
                path:     Solution path string from _solve_maze().
                filename: Output file path.

            Raises:
                ValueError: If path is empty.
        """
        if not path:
            raise ValueError("Cannot write maze with empty path")
        with open(filename, "w") as content:
            for row in range(self.height):
                for col in range(self.width):
                    content.write(f"{self.maze[row][col]:X}")
                content.write("\n")
            content.write("\n")
            content.write(f"{entry_x},{entry_y}\n")
            content.write(f"{exit_x},{exit_y}\n")
            content.write(f"{path}\n")

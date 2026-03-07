"""
    display/parser.py

    parses the maze output .txt file into a MazeData dataclass.

"""

import os
from dataclasses import dataclass, field


# data class
@dataclass
class MazeData:
    """
        all data parsed from a maze output file.

        attributes:
            grid:            2D list of hex values (0–15) per cell.
            rows:            Number of rows.
            cols:            Number of columns.
            entry:           Entry cell as (row, col).
            exit_:           Exit cell as (row, col).
            path:            Solution as ordered list of (row, col).
            path_cells:      Set of path cells for O(1) lookup.
            pattern42_cells: fully-walled (0xF) cells for the '42' pattern.
    """

    grid: list[list[int]]
    rows: int
    cols: int
    entry: tuple[int, int]
    exit_: tuple[int, int]
    path: list[tuple[int, int]]
    path_cells: set[tuple[int, int]] = field(default_factory=set)
    pattern42_cells: set[tuple[int, int]] = field(default_factory=set)

    def __post_init__(self) -> None:
        """
            it precomputes:
            path_cells → fast lookup for path positions
            pattern42_cells → fast lookup for cells with value 15
            so that later rendering becomes faster.
        """
        self.path_cells = set(self.path)
        self.pattern42_cells = {
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.grid[r][c] == 0xF
        }


# helpers

DIRECTION_OFFSETS: dict[str, tuple[int, int]] = {
    "N": (-1, 0),
    "S": (1, 0),
    "E": (0, 1),
    "W": (0, -1),
}


def parse_coord(
    raw: str,
    label: str,
    rows: int,
    cols: int,
) -> tuple[int, int]:
    """
        Parse an 'x,y' string into (row, col).

        The file uses x = column, y = row convention.

        args:
            raw:   raw string e.g. '0,0' or '19,14'.
            label: name used in error messages.
            rows:  grid height for bounds check.
            cols:  grid width for bounds check.

        returns:
            (row, col) tuple.

    """
    parts = raw.strip().split(",")
    if len(parts) != 2:
        raise ValueError(f"{label}: expected 'x,y', got {raw!r}")
    try:
        col, row = int(parts[0]), int(parts[1])
    except ValueError:
        raise ValueError(f"{label}: non-integer values in {raw!r}")
    if not (0 <= row < rows and 0 <= col < cols):
        raise ValueError(
            f"{label} ({col},{row}) out of bounds " f"for {cols}×{rows} grid"
        )
    return (row, col)


def path_from_directions(
    start: tuple[int, int],
    directions: str,
    rows: int,
    cols: int,
) -> list[tuple[int, int]]:
    """
        convert a direction string into an ordered list of cells.

        args:
            start:      starting (row, col).
            directions: string of N/S/E/W characters.
            rows:       grid height for bounds checking.
            cols:       grid width for bounds checking.

        returns:
            list of (row, col) from start through each step.

    """
    path: list[tuple[int, int]] = [start]
    r, c = start
    for i, ch in enumerate(directions):
        if ch not in DIRECTION_OFFSETS:
            raise ValueError(f"Invalid direction {ch!r} at position {i}")
        dr, dc = DIRECTION_OFFSETS[ch]
        r, c = r + dr, c + dc
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError(f"Direction {ch!r} at step {i} leaves the grid")
        path.append((r, c))
    return path


# Parsing
def parse_maze_file(filepath: str) -> MazeData:
    """
        parse a maze output file and return a MazeData instance.

        args:
            filepath: Path to the .txt maze output file.

        returns:
            populated MazeData instance.
    """
    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"Maze file not found: '{filepath}'")

    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            content = fh.read()
    except OSError as exc:
        raise ValueError(f"Cannot read maze file: {exc}") from exc

    parts = content.strip().split("\n\n")
    if len(parts) != 2:
        raise ValueError(
            f"Expected one blank-line separator, found {len(parts) - 1}")
    grid_part, meta_part = parts

    # Grid
    lines = grid_part.strip().splitlines()
    if not lines:
        raise ValueError("Grid section is empty.")
    rows, cols = len(lines), len(lines[0])
    grid: list[list[int]] = []

    for lineno, line in enumerate(lines, start=1):
        if len(line) != cols:
            raise ValueError(
                f"Row {lineno}: expected {cols} cells, got {len(line)}")
        row: list[int] = []
        for ch in line.upper():
            if ch not in "0123456789ABCDEF":
                raise ValueError(f"Row {lineno}: invalid hex character {ch!r}")
            row.append(int(ch, 16))
        grid.append(row)

    # Metadata

    meta = meta_part.strip().splitlines()
    if len(meta) < 3:
        raise ValueError(
            f"Need 3 metadata lines (entry, exit, path), found {len(meta)}"
        )

    entry = parse_coord(meta[0], "ENTRY", rows, cols)
    exit_ = parse_coord(meta[1], "EXIT", rows, cols)

    try:
        path = path_from_directions(entry, meta[2].strip(), rows, cols)
    except ValueError as exc:
        raise ValueError(f"Invalid path: {exc}") from exc

    return MazeData(
        grid=grid,
        rows=rows,
        cols=cols,
        entry=entry,
        exit_=exit_,
        path=path,
    )

"""
display/parser.py
=================
Parses the maze output .txt file into a MazeData dataclass.

No display dependencies — purely data. Can be imported and tested
independently of any graphics library.

Expected file format::

    9A5C...          <- hex grid, one row per line
    <blank line>
    0,0              <- entry as x,y  (col, row)
    19,14            <- exit  as x,y  (col, row)
    SSEEENNW...      <- shortest path as N/E/S/W letters
"""

import os
from dataclasses import dataclass, field


# ── Data class ────────────────────────────────────────────────────────────────

@dataclass
class MazeData:
    """All data parsed from a maze output file.

    Attributes:
        grid:            2D list of hex values (0–15) per cell.
        rows:            Number of rows.
        cols:            Number of columns.
        entry:           Entry cell as (row, col).
        exit_:           Exit cell as (row, col).
        path:            Solution as ordered list of (row, col).
        path_cells:      Set of path cells for O(1) lookup.
        pattern42_cells: All fully-walled (0xF) cells — the '42' pattern.
    """

    grid:            list[list[int]]
    rows:            int
    cols:            int
    entry:           tuple[int, int]
    exit_:           tuple[int, int]
    path:            list[tuple[int, int]]
    path_cells:      set[tuple[int, int]] = field(default_factory=set)
    pattern42_cells: set[tuple[int, int]] = field(default_factory=set)

    def __post_init__(self) -> None:
        """Derive lookup sets after initialisation."""
        self.path_cells = set(self.path)
        self.pattern42_cells = {
            (r, c)
            for r in range(self.rows)
            for c in range(self.cols)
            if self.grid[r][c] == 0xF
        }


# ── Internal helpers ──────────────────────────────────────────────────────────

_DELTA: dict[str, tuple[int, int]] = {
    "N": (-1,  0),
    "S": ( 1,  0),
    "E": ( 0,  1),
    "W": ( 0, -1),
}


def _parse_coord(
    raw: str,
    label: str,
    rows: int,
    cols: int,
) -> tuple[int, int]:
    """Parse an 'x,y' string into (row, col).

    The file uses x = column, y = row convention.

    Args:
        raw:   Raw string e.g. '0,0' or '19,14'.
        label: Name used in error messages.
        rows:  Grid height for bounds check.
        cols:  Grid width for bounds check.

    Returns:
        (row, col) tuple.

    Raises:
        ValueError: If format is wrong or coords are out of bounds.
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
            f"{label} ({col},{row}) out of bounds "
            f"for {cols}×{rows} grid"
        )
    return (row, col)


def _path_from_directions(
    start: tuple[int, int],
    directions: str,
    rows: int,
    cols: int,
) -> list[tuple[int, int]]:
    """Convert a direction string into an ordered list of cells.

    Args:
        start:      Starting (row, col).
        directions: String of N/S/E/W characters.
        rows:       Grid height for bounds checking.
        cols:       Grid width for bounds checking.

    Returns:
        List of (row, col) from start through each step.

    Raises:
        ValueError: If a character is invalid or a step leaves the grid.
    """
    path: list[tuple[int, int]] = [start]
    r, c = start
    for i, ch in enumerate(directions):
        if ch not in _DELTA:
            raise ValueError(f"Invalid direction {ch!r} at position {i}")
        dr, dc = _DELTA[ch]
        r, c = r + dr, c + dc
        if not (0 <= r < rows and 0 <= c < cols):
            raise ValueError(
                f"Direction {ch!r} at step {i} leaves the grid"
            )
        path.append((r, c))
    return path


# ── Public API ────────────────────────────────────────────────────────────────

def parse_maze_file(filepath: str) -> MazeData:
    """Parse a maze output file and return a MazeData instance.

    Args:
        filepath: Path to the .txt maze output file.

    Returns:
        Populated MazeData instance.

    Raises:
        FileNotFoundError: If the file does not exist.
        ValueError:        If the file format is invalid.
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
            f"Expected one blank-line separator, found {len(parts) - 1}"
        )
    grid_part, meta_part = parts

    # ── Grid ──────────────────────────────────────────────────────────────────
    lines = grid_part.strip().splitlines()
    if not lines:
        raise ValueError("Grid section is empty.")
    rows, cols = len(lines), len(lines[0])
    grid: list[list[int]] = []

    for lineno, line in enumerate(lines, start=1):
        if len(line) != cols:
            raise ValueError(
                f"Row {lineno}: expected {cols} cells, got {len(line)}"
            )
        row: list[int] = []
        for ch in line.upper():
            if ch not in "0123456789ABCDEF":
                raise ValueError(
                    f"Row {lineno}: invalid hex character {ch!r}"
                )
            row.append(int(ch, 16))
        grid.append(row)

    # ── Metadata ──────────────────────────────────────────────────────────────
    meta = meta_part.strip().splitlines()
    if len(meta) < 3:
        raise ValueError(
            f"Need 3 metadata lines (entry, exit, path), found {len(meta)}"
        )

    entry = _parse_coord(meta[0], "ENTRY", rows, cols)
    exit_ = _parse_coord(meta[1], "EXIT",  rows, cols)

    try:
        path = _path_from_directions(entry, meta[2].strip(), rows, cols)
    except ValueError as exc:
        raise ValueError(f"Invalid path: {exc}") from exc

    return MazeData(
        grid=grid, rows=rows, cols=cols,
        entry=entry, exit_=exit_, path=path,
    )

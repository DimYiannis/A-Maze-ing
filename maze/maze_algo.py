NORTH = 1
EAST = 2
SOUTH = 4
WEST = 8


def has_wall(cell: int, direction: int) -> bool:
    """Checks whether a cell has a wall in the given direction.

    Args:
        cell (int): Bitmask representing the walls present in the cell.
        direction (int): Bitmask value of the direction to check.

    Returns:
        bool: True if the wall in the given direction is present, False otherwise.
    """
    return bool(cell & direction)


def add_wall(maze: list, yindex: int, xindex: int, direction: int) -> None:
    cell = maze[yindex][xindex]
    maze[yindex][xindex] = cell | direction


def main() -> None:
    maze = [[1, 0, 0], [0, 0, 0], [0, 0, 0]]
    add_wall(maze, 0, 0, WEST)
    cell = maze[0][0]
    print(cell)


if __name__ == "__main__":
    main()

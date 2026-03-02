import random

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
    maze[yindex][xindex] |= direction
    if direction == NORTH and yindex > 0:
        maze[yindex - 1][xindex] |= SOUTH
    if direction == EAST and xindex < len(maze[yindex]) - 1:
        maze[yindex][xindex + 1] |= WEST
    if direction == SOUTH and yindex < len(maze) - 1:
        maze[yindex + 1][xindex] |= NORTH
    if direction == WEST and xindex > 0:
        maze[yindex][xindex - 1] |= EAST


def remove_wall(maze: list, yindex: int, xindex: int, direction: int) -> None:
    maze[yindex][xindex] &= ~direction
    if direction == NORTH and yindex > 0:
        maze[yindex - 1][xindex] &= ~SOUTH
    if direction == EAST and xindex < len(maze[yindex]) - 1:
        maze[yindex][xindex + 1] &= ~WEST
    if direction == SOUTH and yindex < len(maze) - 1:
        maze[yindex + 1][xindex] &= ~NORTH
    if direction == WEST and xindex > 0:
        maze[yindex][xindex - 1] &= ~EAST


def create_grid(width: int, height: int) -> list[list]:
    return [[15 for _ in range(width)] for _ in range(height)]


def generate(maze: list, y: int, x: int, visited: list[list]) -> None:
    width = len(maze[0])
    height = len(maze)

    direction_list = [NORTH, EAST, SOUTH, WEST]
    random.shuffle(direction_list)
    for direction in direction_list:
        if direction 
    if 0 <= y < height and 0 <= x < width and not visited[y][x]:
            remove_wall(maze, x, y, random.choice(direction_list))
            visited[x][y]
            generate(maze, neighboury_y, neighbour_x, visited)


def main() -> None:
    maze = [[1, 0, 0], [0, 0, 0], [0, 0, 0]]
    add_wall(maze, 0, 0, WEST)
    cell = maze[0][0]
    print(cell)


if __name__ == "__main__":
    main()

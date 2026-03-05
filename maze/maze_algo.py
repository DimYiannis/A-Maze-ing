import random
from collections import deque
import sys

NORTH = 1
EAST = 2
SOUTH = 4
WEST = 8


def parse_config(filename: str) -> dict:
    parse = {}
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


def has_wall(cell: int, direction: int) -> bool:
    """Checks whether a cell has a wall in the given direction.

    Args:
        cell (int): Bitmask representing the walls present in the cell.
        direction (int): Bitmask value of the direction to check.

    Returns:
        bool: True if the wall in the given direction is present,
        False otherwise.
    """
    return bool(cell & direction)


def add_wall(
        maze:
        list[list[int]], yindex: int, xindex: int, direction: int) -> None:
    maze[yindex][xindex] |= direction
    if direction == NORTH and yindex > 0:
        maze[yindex - 1][xindex] |= SOUTH
    if direction == EAST and xindex < len(maze[yindex]) - 1:
        maze[yindex][xindex + 1] |= WEST
    if direction == SOUTH and yindex < len(maze) - 1:
        maze[yindex + 1][xindex] |= NORTH
    if direction == WEST and xindex > 0:
        maze[yindex][xindex - 1] |= EAST


def remove_wall(
    maze: list[list[int]], yindex: int, xindex: int, direction: int
) -> None:
    maze[yindex][xindex] &= ~direction
    if direction == NORTH and yindex > 0:
        maze[yindex - 1][xindex] &= ~SOUTH
    if direction == EAST and xindex < len(maze[yindex]) - 1:
        maze[yindex][xindex + 1] &= ~WEST
    if direction == SOUTH and yindex < len(maze) - 1:
        maze[yindex + 1][xindex] &= ~NORTH
    if direction == WEST and xindex > 0:
        maze[yindex][xindex - 1] &= ~EAST


def create_grid(width: int, height: int) -> list[list[int]]:
    return [[15 for _ in range(width)] for _ in range(height)]


def place_42_pattern(maze: list[list[int]], visited: list[list[int]]) -> bool:
    height = len(maze)
    width = len(maze[0])

    if height < 5 or width < 9:
        print("Maze is too small to display 42")
        return False
    pattern = [
        (2, 2),
        (3, 2),
        (4, 2),
        (4, 3),
        (3, 4),
        (4, 4),
        (5, 4),
        (6, 4),
        (2, 6),
        (2, 7),
        (2, 8),
        (3, 8),
        (4, 6),
        (4, 7),
        (4, 8),
        (5, 6),
        (6, 6),
        (6, 7),
        (6, 8),
    ]

    for row, col in pattern:
        maze[row][col] = 15
        visited[row][col] = True
    return True


def generate(
    maze: list[list[int]], start_y: int, start_x: int, visited: list[list[int]]
) -> None:
    width = len(maze[0])
    height = len(maze)
    direction_list = [NORTH, EAST, SOUTH, WEST]
    random.shuffle(direction_list)
    visited[start_y][start_x] = True
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
            0 <= neighbour_y < height
            and 0 <= neighbour_x < width
            and not visited[neighbour_y][neighbour_x]
        ):
            remove_wall(maze, start_y, start_x, direction)
            generate(maze, neighbour_y, neighbour_x, visited)


def reconstruct_path(
        traveled_to: list[list[int]], exit_y: int, exit_x: int) -> str:

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


def solve_maze(
    maze: list[list[int]], entry_y: int, entry_x: int, exit_y: int, exit_x: int
) -> str:
    width = len(maze[0])
    height = len(maze)
    traveled_to = [[None for _ in range(width)] for _ in range(height)]
    queue = deque()
    queue.append((entry_y, entry_x))
    traveled_to[entry_y][entry_x] = "START"
    direction_list = {NORTH: "N", EAST: "E", SOUTH: "S", WEST: "W"}
    while queue:
        y, x = queue.popleft()
        if y == exit_y and x == exit_x:
            return reconstruct_path(
                traveled_to,
                exit_y,
                exit_x,
            )
        for direction in direction_list:
            if direction == NORTH:
                neighbour_y, neighbour_x = y - 1, x
            elif direction == EAST:
                neighbour_y, neighbour_x = y, x + 1
            elif direction == SOUTH:
                neighbour_y, neighbour_x = y + 1, x
            elif direction == WEST:
                neighbour_y, neighbour_x = y, x - 1
            if (
                0 <= neighbour_y < height
                and 0 <= neighbour_x < width
                and not traveled_to[neighbour_y][neighbour_x]
                and not has_wall(maze[y][x], direction)
            ):
                queue.append((neighbour_y, neighbour_x))
                direction_letter = direction_list[direction]
                traveled_to[neighbour_y][neighbour_x] = direction_letter
    return ""


def write_output(
    maze: list[list[int]],
    entry_y: int,
    entry_x: int,
    exit_y: int,
    exit_x: int,
    path: str,
    filename: str,
) -> None:
    height = len(maze)
    width = len(maze[0])

    with open(filename, "w") as content:
        for i in range(height):
            for j in range(width):
                content.write(f"{maze[i][j]:x}")
            content.write("\n")
        content.write("\n")
        content.write(f"{entry_x},{entry_y}\n")
        content.write(f"{exit_x},{exit_y}\n")
        content.write(f"{path}\n")


def main(seed: int = None) -> None:
    if len(sys.argv) != 2:
        print("Usage: python3 a_mazing.py config.txt")
        return
    filename = sys.argv[1]
    config = parse_config(filename)
    enter_maze = config["ENTRY"]
    exit_maze = config["EXIT"]
    maze = create_grid(config["WIDTH"], config["HEIGHT"])
    visited = [[
        False for _ in range(config["WIDTH"])]
            for _ in range(config["HEIGHT"])]
    if seed is None:
        seed = config.get("SEED", random.randint(0, 999999))
    random.seed(seed)
    print(f"Seed: {seed}")
    place_42_pattern(maze, visited)
    generate(maze, 0, 0, visited)
    print("Maze generated!")
    path = solve_maze(
        maze, enter_maze[1], enter_maze[0], exit_maze[1], exit_maze[0])
    write_output(
        maze,
        enter_maze[1],
        enter_maze[0],
        exit_maze[1],
        exit_maze[0],
        path,
        config["OUTPUT_FILE"],
    )


if __name__ == "__main__":
    main()

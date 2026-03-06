from maze_algo import has_wall, add_wall, remove_wall, NORTH, EAST, SOUTH, WEST


def test_wall_north() -> None:
    assert has_wall(9, NORTH)


def test_wall_east() -> None:
    assert has_wall(3, EAST)


def test_wall_south() -> None:
    assert has_wall(6, SOUTH)


def test_wall_west() -> None:
    assert has_wall(9, WEST)


def test_add_wall_north() -> None:
    maze = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    add_wall(maze, 1, 0, NORTH)
    assert maze[1][0] & NORTH
    assert maze[0][0] & SOUTH


def test_add_wall_east() -> None:
    maze = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    add_wall(maze, 0, 1, EAST)
    assert maze[0][1] & EAST
    assert maze[0][2] & WEST


def test_add_wall_south() -> None:
    maze = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    add_wall(maze, 1, 0, SOUTH)
    assert maze[1][0] & SOUTH
    assert maze[2][0] & NORTH


def test_add_wall_west() -> None:
    maze = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    add_wall(maze, 0, 1, WEST)
    assert maze[0][1] & WEST
    assert maze[0][0] & EAST


def test_no_neighbour_north() -> None:
    maze = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    add_wall(maze, 0, 0, NORTH)
    assert maze[0][0] & NORTH


def test_no_neighbour_east() -> None:
    maze = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    add_wall(maze, 0, len(maze[0]) - 1, EAST)
    assert maze[0][len(maze[0]) - 1] & EAST


def test_remove_wall_north() -> None:
    maze = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    add_wall(maze, 1, 0, NORTH)
    assert maze[1][0] & NORTH
    remove_wall(maze, 1, 0, NORTH)
    assert not (maze[1][0] & NORTH)
    assert not (maze[0][0] & SOUTH)


def test_remove_wall_east() -> None:
    maze = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
    add_wall(maze, 0, 1, EAST)
    assert maze[0][1] & EAST
    remove_wall(maze, 1, 0, EAST)
    assert not (maze[0][1] & EAST)
    assert not (maze[0][0] & WEST)

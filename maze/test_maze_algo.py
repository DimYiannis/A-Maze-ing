from maze_algo import has_wall, NORTH, EAST, SOUTH, WEST


def test_wall_north():
    assert has_wall(9, NORTH)


def test_wall_east():
    assert has_wall(3, EAST)


def test_wall_south():
    assert has_wall(6, SOUTH)


def test_wall_west():
    assert has_wall(9, WEST)

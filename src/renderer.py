TILE = 40

def draw_square(game, x, y, size, color):
    for i in range(size):
        for j in range(size):
            game.mlx_lib.mlx_pixel_put(
                game.mlx,
                game.win,
                x + i,
                y + j,
                color
            )

def draw_map(game):
    for y in range(len(game.map)):
        for x in range(len(game.map[y])):

            if game.map[y][x] == "1":
                color = 0xFFFFFF  # white
            else:
                color = 0x000000  # black

            draw_square(
                game,
                x * TILE,
                y * TILE,
                TILE,
                color
            )

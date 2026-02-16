TILE = 40

def draw_square(game, x, y, size, color):
    for i in range(size):
        for j in range(size):
            mlx_pixel_put(game.mlx, game.win, x+i, y+i, color)

def draw_map(game):
    for y in range(len(game.map)):
        for x in range(len(game.map[y])):
            if game.map[y][x] == "1":
                draw_square(game, x*TILE, y*TILE, TILE, 0xFFFFFF)
            else:
                draw_square(game, x*TILE, y*TILE, TILE, 0x000000)

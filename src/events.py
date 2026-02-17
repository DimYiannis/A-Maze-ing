import os

def key_hook(keycode, game):
    # exit using esc
    if keycode == 65307:
        os._exit(0)

# needs fix
def close_hook(game):
    game.mlx_lib.mlx_destroy_window(game.mlx, game.win)
    os._exit(0)

def register_events(game):
    game.mlx_lib.mlx_hook(game.win, 17, 0, close_hook, game)
    game.mlx_lib.mlx_key_hook(game.win, key_hook, game)


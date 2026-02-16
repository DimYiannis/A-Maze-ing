def key_hook(keycode, game):
    print("Key:", keycode)

def close_hook(param):
    exit(0)

def register_events(game):
    mlx_key_hook(game.win, key_hook, game)
    mlx_hook(game.win, 17, 0, close_hook, None)


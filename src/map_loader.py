#return a list of lines to display the map
def load_map(filename):
    with open(filename, "r") as fd:
        return [line.strip() for line in fd]

# generator to display the map
def load__map(filename):
    with open(filename, "r") as fd:
        for line in fd:
            yield line.strip()


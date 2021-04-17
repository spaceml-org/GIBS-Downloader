# Stores tiling information
class Tile():
    def __init__(self, width, height, overlap, handling):
        self.width = width
        self.height = height
        self.overlap = overlap
        self.handling = handling
class Tile():
    """
    Stores tiling information
    
    Attributes:
        width (int): tile width
        height (int): tile height
        overlap (float): tile overlap
        handling (Handling): method for tiling at boundary of original image
    """
    def __init__(self, width, height, overlap, handling):
        self.width = width
        self.height = height
        self.overlap = overlap
        self.handling = handling
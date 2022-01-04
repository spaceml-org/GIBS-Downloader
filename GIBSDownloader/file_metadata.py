import os

from GIBSDownloader.coordinate_utils import Rectangle
from GIBSDownloader.product import Product

class TileMetadata():
    """
    Extracts metadata from a tile's file name

    Attributes:
        date (str): Date of the tile
        region (Rectangle): Coordinate region of the tile
    """
    def __init__(self, tile_path):
        filename = os.path.basename(tile_path)
        components = filename.split('_')
        date_str = components[0] 
        region_str = os.path.splitext(components[1])[0]
        region = Rectangle.from_str(region_str)
        self.date = date_str
        self.region = region

class TiffMetadata():
    """
    Extracts metadata from the original downloaded image's file name 

    Attributes:
        name (str): base file name without the path
        date (str): date of the image
        product_name (str): name of the downloaded imagery product
    """
    def __init__(self, tiff_path):
        filename = os.path.basename(tiff_path)
        components = filename.split('_')
        date = os.path.splitext(components[1])[0]
        self.name = filename
        self.date = date
        self.product_name = components[0]

class IntermediateMetadata():
    """
    Extracts metadata from an intermediate image's file name

    The extracted metadata is useful in determining which intermediate image
    contains a given tile based on the intermediate image's pixel coordinates in
    the original image. The metadata stores these pixel coordinates.

    Attributes:
        start_x (int): x-pixel coordinate of the top left of the intermediate
        start_y (int): y-pixel coordinate of the top left of the intermediate
        end_x (int): x-pixel coordinate of the bottom right of the intermediate
        end_y (int): y-pixel coordinate of the bottom right of the intermediate
    """
    def __init__(self, inter_path):
        filename = os.path.basename(inter_path)
        components = filename.split("_")
        self.name = filename
        self.start_x = int(components[1])
        self.start_y = int(components[2])
        self.end_x = int(components[3])
        self.end_y = int(os.path.splitext(components[4])[0])
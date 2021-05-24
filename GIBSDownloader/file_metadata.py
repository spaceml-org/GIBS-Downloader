import os

from GIBSDownloader.coordinate_utils import Rectangle
from GIBSDownloader.product import Product

class TileMetadata():
    def __init__(self, tile_path):
        filename = os.path.basename(tile_path)
        components = filename.split('_')
        date_str = components[0] # "2020-09-15"
        region_str = os.path.splitext(components[1])[0] # "038.1579,-121.3758,037.0042,-122.8529"
        region = Rectangle.from_str(region_str)
        self.date = date_str
        self.region = region

class TiffMetadata():
    def __init__(self, tiff_path):
        filename = os.path.basename(tiff_path)
        components = filename.split('_')
        date = os.path.splitext(components[1])[0]
        self.name = filename
        self.date = date
        self.product_name = components[0]

class IntermediateMetadata():
    def __init__(self, inter_path):
        filename = os.path.basename(inter_path)
        components = filename.split("_")
        self.name = filename
        self.start_x = int(components[1])
        self.start_y = int(components[2])
        self.end_x = int(components[3])
        self.end_y = int(os.path.splitext(components[4])[0])
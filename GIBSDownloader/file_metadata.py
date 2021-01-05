import os

from coordinate_utils import Rectangle
from product import Product

class TileMetadata():
    def __init__(self, filename):
        # 2020-09-15_038.1579_-121.3758_037.0042_-122.8529.jpeg
        # 2020-09-15_038.1579,-121.3758,037.0042,-122.8529.jpeg
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
        self.date = date
        self.product = Product(components[0])
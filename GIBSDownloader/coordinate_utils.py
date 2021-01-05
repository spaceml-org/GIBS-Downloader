import numpy as np

# stores coordinate information 
class Coordinate():
    def __init__(self, coords):
        """coords: (latitude, longitude)"""
        self.x = coords[1]
        self.y = coords[0]

# Stores information about the desired downloading region
class Rectangle():
    def __init__(self, bl_coords, tr_coords):
        self.bl_coords = bl_coords
        self.tr_coords = tr_coords

    # Calculates the necessary width and height of image encompassing Rectangle's bounding box
    # Taken from https://github.com/NASA-IMPACT/data_share
    def calculate_width_height(self, resolution: float):
        """
        resolution: represents the pixel resolution, i.e. km/pixel. Should be a value from this list: [0.03, 0.06, 0.125, 0.25, 0.5, 1, 5, 10]
        """
        KM_PER_DEG_AT_EQ = 111.
        km_per_deg_at_lat = KM_PER_DEG_AT_EQ * np.cos(np.pi * np.mean([self.bl_coords.y, self.tr_coords.y]) / 180.)
        width = int((self.tr_coords.x - self.bl_coords.x) * km_per_deg_at_lat / resolution)
        height = int((self.tr_coords.y - self.bl_coords.y) * KM_PER_DEG_AT_EQ / resolution)
        print(width, height)
        return (width, height)
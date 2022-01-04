import math

import numpy as np
import pyproj
from pyproj import Proj, Transformer

class Coordinate():
    """
    Stores coordinate information
    
    Attributes:
        x (float): longitude
        y (float): latitude
    """
    def __init__(self, coords):
        """coords: (latitude, longitude)"""
        self.x = coords[1]
        self.y = coords[0]

class Rectangle():
    """
    Stores information about the desired downloading region.

    Represents a rectangular region of the world, containing the region's
    bottom left and top right coordinates.

    Attributes:
        bl_coords (Coordinate): coordinates of the bottom left corner of region
        tr_coords (Coordinate): coordinates of the top right corner of region
    """
    def __init__(self, bl_coords, tr_coords):
        self.bl_coords = bl_coords
        self.tr_coords = tr_coords

    @classmethod
    def from_str(cls, input_str):
        """
        Creates Rectangle from coordinate strings.
        
        Parameters:
            input_str (str): The format of string should be: 
                'bottom left y, bottom left x, top right y, top right x'

        Returns:
            Rectangle representing the cooordinate region in the string
        """
        components = input_str.split(',')
        bl_y = float(components[0])
        bl_x = float(components[1])
        tr_y = float(components[2])
        tr_x = float(components[3])

        bl_coords = Coordinate((bl_y, bl_x))
        tr_coords = Coordinate((tr_y, tr_x))

        return Rectangle(bl_coords, tr_coords)

    def calculate_width_height(self, resolution):
        """ 
        Approximates the necessary width and height of image encompassing Rectangle's bounding box.

        The width is found by taking the difference of the longitudes of the corners of the bounding
        box and multiplying the result by `km_per_deg_at_lat`. This approximates the distance
        in kilometers between the two longitudes. `km_per_deg_at_lat` depends on the latitude of the 
        region, as the distance in kilometers between longitudes differs based on where you are in the 
        globe. The height is found in a similar manner, except it is multiplied by a constant, 111,
        as the distance between latitudes is fairly constant throughout the globe. 
        Then, the pixel width and height is obtained by dividing by the pixel resolution (i.e. km/pixel).
        
        Read more about the constants used here: 
        https://www.thoughtco.com/degree-of-latitude-and-longitude-distance-4070616

        Parameters:
            resolution (float): represents the pixel resolution, i.e. km/pixel. 
                resolution should be a value from this list: 
                    [0.03, 0.06, 0.125, 0.25, 0.5, 1, 5, 10]

        Returns:
            (width, height) of Rectangle object given `resolution`
        
        Code taken from: https://github.com/NASA-IMPACT/data_share
        """
        KM_PER_DEG_AT_EQ = 111.
        km_per_deg_at_lat = KM_PER_DEG_AT_EQ * np.cos(np.pi * np.mean([self.bl_coords.y, self.tr_coords.y]) / 180.)
        width = int((self.tr_coords.x - self.bl_coords.x) * km_per_deg_at_lat / resolution)
        height = int((self.tr_coords.y - self.bl_coords.y) * KM_PER_DEG_AT_EQ / resolution)
        return (width, height)
    
    def lat_lon_to_modis(self):
        """ 
        Finds the corresponding MODIS Grid tile from the Rectangle's bottom left coordinates.

        Code taken from: https://gis.stackexchange.com/questions/265400/getting-tile-number-of-sinusoidal-modis-product-from-lat-long 
        All credit to response by user @renatoc
        """
        # Constants for MODIS grid tile conversion
        CELLS = 2400
        VERTICAL_TILES = 18
        HORIZONTAL_TILES = 36
        EARTH_RADIUS = 6371007.181
        EARTH_WIDTH = 2 * math.pi * EARTH_RADIUS
        TILE_WIDTH = EARTH_WIDTH / HORIZONTAL_TILES
        TILE_HEIGHT = TILE_WIDTH
        CELL_SIZE = TILE_WIDTH / CELLS
        MODIS_GRID = Proj(f'+proj=sinu +R={EARTH_RADIUS} +nadgrids=@null +wktext')
        
        x, y = MODIS_GRID(self.bl_coords.x, self.bl_coords.y)
        h = (EARTH_WIDTH * .5 + x) / TILE_WIDTH
        v = -(EARTH_WIDTH * .25 + y - (VERTICAL_TILES - 0) * TILE_HEIGHT) / TILE_HEIGHT

        return 'h{}v{}'.format(str(f'{int(h):02d}'), str(f'{int(v):02d}'))
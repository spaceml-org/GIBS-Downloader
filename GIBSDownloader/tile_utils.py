import argparse
import os

import numpy as np
import rasterio
from matplotlib import pyplot as plt
from osgeo import gdal
from PIL import Image

from GIBSDownloader.tile import Tile
from GIBSDownloader.handling import Handling
from GIBSDownloader.file_metadata import TiffMetadata

class TileUtils():
    @classmethod
    def generate_tile_name_with_coordinates(cls, date, x, x_min, x_size, y, y_min, y_size, tile):
        tr_x = x * x_size + x_min 
        tr_y = (y + tile.height) * y_size + y_min 
        bl_x = (x + tile.width) * x_size + x_min
        bl_y = y * y_size + y_min
        filename = "{d}_{by},{bx},{ty},{tx}".format(d=date, ty=str(f'{round(bl_y, 4):08}'), tx=str(f'{round(bl_x, 4):09}'), by=str(f'{round(tr_y, 4):08}'), bx=str(f'{round(tr_x, 4):09}'))
        return filename

    @classmethod
    def img_to_tiles(cls, tiff_path, tile, output_path):
        metadata = TiffMetadata(tiff_path)

        # Open GeoTiff in gdal in order to get coordinate information
        tif = gdal.Open(tiff_path)
        band = tif.GetRasterBand(1)
        WIDTH = band.XSize
        HEIGHT = band.YSize

        # Use the following to get the coordinates of each tile
        gt = tif.GetGeoTransform()
        x_min = gt[0]
        x_size = gt[1]
        y_min = gt[3]
        y_size = gt[5]

        # Open GeoTiff as numpy array in order to tile from the array
        src = rasterio.open(tiff_path)
        arr = src.read()
        img_arr = np.dstack(arr)

        x_step, y_step = int(tile.width * (1 - tile.overlap)), int(tile.height * (1 - tile.overlap))
        x = 0 
        done_x = False

        if (tile.width > WIDTH or tile.height > HEIGHT):
            raise argparse.ArgumentTypeError("Tiling dimensions greater than image dimensions")
        
        while(x < WIDTH and not done_x):
            if(WIDTH - x < tile.width):
                done_x = True
                if tile.handling == Handling.discard_incomplete_tiles:
                    continue
                if tile.handling == Handling.complete_tiles_shift:
                    x = WIDTH - tile.width
            done_y = False
            y = 0
            while (y < HEIGHT and not done_y):
                if(HEIGHT - y < tile.height):
                    done_y = True
                    if tile.handling == Handling.discard_incomplete_tiles:
                        continue
                    if tile.handling == Handling.complete_tiles_shift:
                        y = HEIGHT - tile.height  
                        
                output_filename = TileUtils.generate_tile_name_with_coordinates(metadata.date, x, x_min, x_size, y, y_min, y_size, tile)

                if tile.handling == Handling.include_incomplete_tiles and (done_x or done_y):
                    incomplete_tile = img_arr[y:min(y + tile.height, HEIGHT), x:min(x + tile.width, WIDTH)]
                    empty_array = np.zeros((tile.height, tile.height, 3), dtype=np.uint8)
                    empty_array[0:incomplete_tile.shape[0], 0:incomplete_tile.shape[1]] = incomplete_tile
                    incomplete_img = Image.fromarray(empty_array)
                    incomplete_img.save(output_path + output_filename + ".jpeg")
                else: 
                    tile_array = img_arr[y:y+tile.height, x:x+tile.width]
                    tile_img = Image.fromarray(tile_array)
                    tile_img.save(output_path + output_filename + ".jpeg")

                y += y_step
            x += x_step

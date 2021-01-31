import argparse
import os
import math
import warnings

import numpy as np
from matplotlib import pyplot as plt
from osgeo import gdal
from PIL import Image
from tqdm import tqdm

from GIBSDownloader.tile import Tile
from GIBSDownloader.handling import Handling
from GIBSDownloader.file_metadata import TiffMetadata
from GIBSDownloader.coordinate_utils import Coordinate, Rectangle

warnings.simplefilter('ignore', Image.DecompressionBombWarning)

MAX_INTERMEDIATE_LENGTH = int(math.sqrt(2 * Image.MAX_IMAGE_PIXELS)) # Maximum width and height for an intermediate tile to guarantee num pixels less than PIL's max

class TileUtils():
    @classmethod
    def generate_tile_name_with_coordinates(cls, date, x, x_min, x_size, y, y_min, y_size, tile):
        tr_x = x * x_size + x_min 
        tr_y = (y + tile.height) * y_size + y_min 
        bl_x = (x + tile.width) * x_size + x_min
        bl_y = y * y_size + y_min
        filename = "{d}_{by},{bx},{ty},{tx}".format(d=date, ty=str(f'{round(bl_y, 4):08}'), tx=str(f'{round(bl_x, 4):09}'), by=str(f'{round(tr_y, 4):08}'), bx=str(f'{round(tr_x, 4):09}'))
        return filename, Rectangle(Coordinate((bl_y, bl_x)), Coordinate((tr_y, tr_x)))

    @classmethod
    def generate_intermediate_images(cls, tiff_path, tile, width, height, date):
        output_dir = os.path.join(os.path.dirname(tiff_path), 'inter_{}'.format(date))
        os.mkdir(output_dir)

        # used to find the lengths of the max height and width
        width_k = MAX_INTERMEDIATE_LENGTH // tile.width
        height_k = MAX_INTERMEDIATE_LENGTH // tile.height
        
        # LOOP THOUGH AND GENERATE THE INTERMEDIATE TILES
        width_current = 0
        done_width = False
        width_length = (width_k - 1) * tile.width # (width_k - 1) to guarantee last image has at least 1 tile to avoid problems with tiling at boundaries
        index = 0
        while width_current < width and not done_width:
            if width - width_current < width_length:
                width_length = width - width_current
                done_width = True
            height_current = 0
            done_height = False
            height_length = (height_k - 1) * tile.height 
            while height_current < height and not done_height:
                if height - height_current < height_length: 
                    height_length = height - height_current
                    done_height = True
                output_path = os.path.join(output_dir, str(index))
                command = "gdal_translate -of GTiff -srcwin --config GDAL_PAM_ENABLED NO {x}, {y}, {t_width}, {t_height} {tif_path} {out_path}.tif".format(x=str(width_current), y=str(height_current), t_width=width_length, t_height=height_length, tif_path=tiff_path, out_path=output_path)
                os.system(command)
                index += 1
                height_current = height_current + height_length - tile.overlap * tile.width
            width_current = width_current + width_length - tile.overlap * tile.height
        return output_dir

    @classmethod
    def img_to_tiles(cls, tiff_path, tile, tile_date_path, inter_path=None):
        # Get metadata from original tif image
        metadata = TiffMetadata(tiff_path)

        # Check if tiling an intermediate tile
        if not inter_path == None:
            tiler_path = inter_path
        else:
            tiler_path = tiff_path

        # Open GeoTiff in gdal in order to get coordinate information
        tif = gdal.Open(tiler_path)
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
        src = Image.open(tiler_path)
        img_arr = np.array(src)

        x_step, y_step = int(tile.width * (1 - tile.overlap)), int(tile.height * (1 - tile.overlap))
        x = 0 
        done_x = False

        # Check for valid tiling
        if (tile.width > WIDTH or tile.height > HEIGHT):
            raise argparse.ArgumentTypeError("Tiling dimensions greater than image dimensions")

        # Calculate the number of tiles to be generated
        if tile.handling == Handling.discard_incomplete_tiles:
            num_iterations = (WIDTH // tile.width) * (HEIGHT // tile.height)
        else:
            num_iterations = math.ceil(WIDTH / tile.width) * math.ceil(HEIGHT / tile.height)
        pbar = tqdm(total=num_iterations) # Create a progress bar for tiling one image
        
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

                # Find which MODIS grid location the current tile fits into
                output_filename, region = TileUtils.generate_tile_name_with_coordinates(metadata.date, x, x_min, x_size, y, y_min, y_size, tile)
                output_path = tile_date_path + region.lat_lon_to_modis() + '/'
                if not os.path.exists(output_path):
                    os.mkdir(output_path)

                # Tiling past boundaries 
                if tile.handling == Handling.include_incomplete_tiles and (done_x or done_y):
                    incomplete_tile = img_arr[y:min(y + tile.height, HEIGHT), x:min(x + tile.width, WIDTH)]
                    empty_array = np.zeros((tile.height, tile.height, 3), dtype=np.uint8)
                    empty_array[0:incomplete_tile.shape[0], 0:incomplete_tile.shape[1]] = incomplete_tile
                    incomplete_img = Image.fromarray(empty_array)
                    incomplete_img.save(output_path + output_filename + ".jpeg")
                else: # Tiling within boundaries
                    tile_array = img_arr[y:y+tile.height, x:x+tile.width]
                    tile_img = Image.fromarray(tile_array)
                    tile_img.save(output_path + output_filename + ".jpeg")

                pbar.update(1)
                y += y_step
            x += x_step
        pbar.close()
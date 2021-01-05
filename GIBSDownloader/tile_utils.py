import argparse
import os

from osgeo import gdal

from tile import Tile
from handling import Handling
from file_metadata import TiffMetadata

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
                command = "gdal_translate -of JPEG -srcwin --config GDAL_PAM_ENABLED NO {x}, {y}, {t_width}, {t_height} {tif_path} {out_path}{out_name}.jpeg".format(x=str(x), y=str(y), t_width=tile.width, t_height=tile.height, tif_path=tiff_path, out_path=output_path, out_name=output_filename)
                os.system(command)
                y += y_step
            x += x_step

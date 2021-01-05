#!/usr/bin/env python

import os
import shutil
import argparse
from argparse import ArgumentParser

import numpy as np
import pandas as pd
import tensorflow as tf
from osgeo import gdal

from coordinate_utils import Coordinate, Rectangle
from tile import Tile
from handling import Handling

# Constants
MAX_FILE_SIZE = 100_000_000 # 100 MB recommended TFRecord file size

###### FUNCTIONS TO WRITE TO TFRECORDS ######
def _bytes_feature(value):
    """Returns a bytes_list from a string / byte."""
    if isinstance(value, type(tf.constant(0))):
        value = value.numpy()
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

def _float_feature(value):
    """Returns a float_list from a float / double."""
    return tf.train.Feature(float_list=tf.train.FloatList(value=[value]))

def _int64_feature(value):
    """Returns an int64_list from a bool / enum / int / uint."""
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))

def image_example(date: str, img_path: str, region: Rectangle):
    image_raw = open(img_path, 'rb').read()
    image_shape = tf.image.decode_png(image_raw).shape

    feature = {
        'date': _bytes_feature(bytes(date, 'utf-8')),
        'image_raw': _bytes_feature(image_raw),
        'width': _int64_feature(image_shape[0]),
        'height': _int64_feature(image_shape[1]),
        'top_left_lat' : _float_feature(region.tl_coords.y),
        'top_left_long' :_float_feature(region.tl_coords.x),
        'bot_right_lat' : _float_feature(region.br_coords.y),
        'bot_right_long' : _float_feature(region.br_coords.x),
    }

    return tf.train.Example(features=tf.train.Features(feature=feature))
###### END OF TFRECORD HELPER FUNCTIONS ######

###### MAIN DOWNLOADING FUNCTION ######
def download_area_tiff(region, date, output):
    """
    region: rectangular region to be downloaded
    date: YYYY-MM-DD
    output: path/to/filename (do not specify extension)
    returns tuple with dowloaded width and height
    """

    width, height = region.calculate_width_height(0.25)
    lon_lat = "{tl_x} {tl_y} {br_x} {br_y}".format(tl_x=region.tl_coords.x, tl_y=region.tl_coords.y, br_x=region.br_coords.x, br_y=region.br_coords.y)

    base = "gdal_translate -of GTiff -outsize {w} {h} -projwin {ll} '<GDAL_WMS><Service name=\"TMS\"><ServerUrl>https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/{d}/250m/".format(w=width, h=height, ll=lon_lat, d=date)
    end = "${z}/${y}/${x}.jpg</ServerUrl></Service><DataWindow><UpperLeftX>-180.0</UpperLeftX><UpperLeftY>90</UpperLeftY><LowerRightX>396.0</LowerRightX><LowerRightY>-198</LowerRightY><TileLevel>8</TileLevel><TileCountX>2</TileCountX><TileCountY>1</TileCountY><YOrigin>top</YOrigin></DataWindow><Projection>EPSG:4326</Projection><BlockSizeX>512</BlockSizeX><BlockSizeY>512</BlockSizeY><BandsCount>3</BandsCount></GDAL_WMS>' "
    filename = "{}modis_{}.tif".format(output, date)
    command = base + end + filename
    os.system(command)
    return filename

###### Helper function to generate file names for each tile ######
def generate_tile_name_with_coordinates(date, x, x_min, x_size, y, y_min, y_size, tile):
    tl_x = x * x_size + x_min # find longitude of top left corner
    tl_y = y * y_size + y_min # find latitude of top left corner
    br_x = (x + tile.width) * x_size + x_min # find longitude of bottom right corner
    br_y = (y + tile.height) * y_size + y_min # find latitude of bottom right corner
    filename = "{d}_{ty}_{tx}_{by}_{bx}".format(d=date, ty=str(f'{round(tl_y, 4):08}'), tx=str(f'{round(tl_x, 4):09}'), by=str(f'{round(br_y, 4):08}'), bx=str(f'{round(br_x, 4):09}'))
    return filename

###### Main tiling function ######
def img_to_tiles(tiff_path, tile, output_path):
    date = tiff_path[-14:-4]
        
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
            if tile.handling == Handling.discard_incomplete_tiles:
                done_x = True
                continue
            if tile.handling == Handling.complete_tiles_shift:
                x = WIDTH - tile.width
            done_x = True
        done_y = False
        y = 0
        while (y < HEIGHT and not done_y):
            if(HEIGHT - y < tile.height):
                if tile.handling == Handling.discard_incomplete_tiles:
                    done_y = True
                    continue
                if tile.handling == Handling.complete_tiles_shift:
                    y = HEIGHT - tile.height
                done_y = True
            output_filename = generate_tile_name_with_coordinates(date, x, x_min, x_size, y, y_min, y_size, tile)
            command = "gdal_translate -of JPEG -srcwin --config GDAL_PAM_ENABLED NO {x}, {y}, {t_width}, {t_height} {tif_path} {out_path}{out_name}.jpeg".format(x=str(x), y=str(y), t_width=tile.width, t_height=tile.height, tif_path=tiff_path, out_path=output_path, out_name=output_filename)
            os.system(command)
            y += y_step
        x += x_step

###### MAIN WRITING TO TFRECORD FUNCTION ######
def write_to_tfrecords(input_path, output_path):
    for directory, subdirectories, files in os.walk(input_path):
        count = 0
        version = 0
        while(count < len(files)):
            total_file_size = 0
            with tf.io.TFRecordWriter("{path}modis_tf{v}.tfrecord".format(path=output_path, v=str(version))) as writer:
                while(total_file_size < MAX_FILE_SIZE and count < len(files)):    
                    filename = files[count]
                    date = filename[-53:-42]
                    # following lines get top left and bottom right coords from filename
                    region = Rectangle(
                        Coordinate(     # Top left coords
                            (float(filename[-41:-34]), float(filename[-33:-24]))),
                        Coordinate(     # Bottom right coords
                            (float(filename[-23:-15]), float(filename[-14:-5]))))
                    total_file_size += os.path.getsize(directory + '/' + filename)
                    tf_example = image_example(date, directory + '/' + filename, region)
                    writer.write(tf_example.SerializeToString())
                    count += 1
            version += 1

def generate_download_path(start_date, end_date, tl_coords, output):
    base = "modis_{u_lat}_{lft_lon}_{st_date}-{end_date}".format(u_lat=str(round(tl_coords.y, 4)), lft_lon=str(round(tl_coords.x, 4)), st_date=start_date.replace('-',''), end_date=end_date.replace('-', ''))
    return os.path.join(output, base)

def download_originals(download_path, originals_path, tiled_path, tfrecords_path, start_date, end_date, logging, region):
    if not os.path.isdir(download_path):
        os.mkdir(download_path)
        os.mkdir(originals_path)
        os.mkdir(tiled_path)
        os.mkdir(tfrecords_path)
        dates = pd.date_range(start=start_date, end=end_date)
        for date in dates:
            if logging: 
                print('Downloading:', date)
            download_area_tiff(region, date.strftime("%Y-%m-%d"), originals_path)
    else:
        print("The specified region and set of dates has already been downloaded")

def tile_originals(tile_res_path, originals_path, tile, logging):
    if not os.path.isdir(tile_res_path):
            os.mkdir(tile_res_path)
            for directory, subdirectory, files in os.walk(originals_path):
                for filename in files:
                    tiff_path = os.path.join(directory, filename)
                    if logging:
                        print("Tiling image at:", tiff_path)
                    img_to_tiles(tiff_path, tile, tile_res_path)
    else:
        print("The specified tiles for these images have already been generated")

def tile_to_tfrecords(tile_res_path, tfrecords_res_path, logging):
    if os.path.isdir(tile_res_path):
            if not os.path.isdir(tfrecords_res_path):
                os.mkdir(tfrecords_res_path)
                if logging: 
                    print("Writing files at:", tile_res_path, " to TFRecords")
                write_to_tfrecords(tile_res_path, tfrecords_res_path)
            else:
                print("The specified TFRecords have already been written")
    else: 
        print("Unable to write to TFRecords due to nonexistent tile path")

def remove_originals(originals_path, logging):
    if logging: 
        print("Removing original images...")
    shutil.rmtree(originals_path)
    os.mkdir(originals_path)

def main():
    parser = ArgumentParser()
    parser.add_argument("start_date", metavar='start-date', type=str, help="starting date for downloads")
    parser.add_argument("end_date", metavar='end-date',type=str, help="ending date for downloads")
    parser.add_argument("top_left_coords", metavar='top-left-coords', type=str, help="coordinates for top left corner formatted lat,lon (NO SPACE)")
    parser.add_argument("bottom_right_coords", metavar='bottom-right-coords', type=str, help="coordinates for left longitude formatted lat,lon (NO SPACE)")    
    parser.add_argument("--output-path", default=os.getcwd(), type=str, help="path to output directory")
    parser.add_argument("--tile", default=False, type=bool, help="Tiling flag")
    parser.add_argument("--tile-width", default=512, type=int, help="tiled image width")
    parser.add_argument("--tile-height", default=512, type=int, help="tiled image height")
    parser.add_argument("--tile-overlap", default=0.5, type=float, help="percent overlap for each tile")
    parser.add_argument("--boundary-handling", default=Handling.complete_tiles_shift, type=Handling, help="define how to handle tiles at image boundaries", choices=list(Handling))
    parser.add_argument("--remove-originals", default=False, type=bool, help="keep/delete original downloaded images")
    parser.add_argument("--generate-tfrecords", default=False, type=bool, help="generate tfrecords for image tiles")
    parser.add_argument("--verbose", default=False, type=bool, help="log downloading process")

    # get the user input
    args = parser.parse_args()
    start_date = args.start_date
    end_date = args.end_date
    output_path = args.output_path
    logging = args.verbose
    rm_originals = args.remove_originals
    write_tfrecords = args.generate_tfrecords
    tiling = args.tile
    tile = Tile(args.tile_width, args.tile_height, args.tile_overlap, args.boundary_handling)

    # get the latitude, longitude values from the user input
    tl_coords = Coordinate([float(i) for i in args.top_left_coords.split(',')])
    br_coords = Coordinate([float(i) for i in args.bottom_right_coords.split(',')])
    region = Rectangle(tl_coords, br_coords)
    
    # check if inputted coordinates are valid
    if (br_coords.x < tl_coords.x or tl_coords.y < br_coords.y):
        raise argparse.ArgumentTypeError('Inputted coordinates are invalid: order should be (upper_latitude,left_longitude lower_latitude,right_longitude)')
    
    # gets paths for downloads
    download_path = generate_download_path(start_date, end_date, tl_coords, output_path)
    originals_path = download_path + '/original_images/'
    tiled_path = download_path + '/tiled_images/'
    tfrecords_path = download_path + '/tfrecords/'
    resolution = "{t_width}x{t_height}_{t_overlap}".format(t_width=str(tile.width), t_height=str(tile.height), t_overlap=str(tile.overlap))
    tile_res_path = os.path.join(tiled_path, resolution) + '/'
    tfrecords_res_path = os.path.join(tfrecords_path, resolution) + '/'

    download_originals(download_path, originals_path, tiled_path, tfrecords_path, start_date, end_date, logging, region)

    if tiling:
        tile_originals(tile_res_path, originals_path, tile, logging)

    if write_tfrecords:
        tile_to_tfrecords(tile_res_path, tfrecords_res_path, logging)
        
    if rm_originals:
        remove_originals(originals_path, logging)

if __name__ == "__main__":
    main()
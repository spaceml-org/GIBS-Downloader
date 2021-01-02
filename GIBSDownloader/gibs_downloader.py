#!/usr/bin/env python

import os
import shutil
import argparse
from argparse import ArgumentParser
from enum import Enum

import numpy as np
import pandas as pd
import tensorflow as tf

from osgeo import gdal

# Constants
MAX_FILE_SIZE = 100_000_000 # 100 MB recommended TFRecord file size

# Enum to decide how to handle images at boundaries
class Handling(Enum):
    complete_tiles_shift = 'complete-tiles-shift'
    include_incomplete_tiles = 'include-incomplete-tiles'
    discard_incomplete_tiles = 'discard-incomplete-tiles'
    
    def __str__(self):
        return self.value

###### Helper function to calculate the proper width/height for requested image ######
# Taken from https://github.com/NASA-IMPACT/data_share
def calculate_width_height(extent, resolution):
    """
    extent: [lower_latitude, left_longitude, higher_latitude, right_longitude], EG: [51.46162974683544,-22.94768591772153,53.03698575949367,-20.952234968354432]
    resolution: represents the pixel resolution, i.e. km/pixel. Should be a value from this list: [0.03, 0.06, 0.125, 0.25, 0.5, 1, 5, 10]
    """
    KM_PER_DEG_AT_EQ = 111.
    lats = extent[::2]
    lons = extent[1::2]
    km_per_deg_at_lat = KM_PER_DEG_AT_EQ * np.cos(np.pi * np.mean(lats) / 180.)
    width = int((lons[1] - lons[0]) * km_per_deg_at_lat / resolution)
    height = int((lats[1] - lats[0]) * KM_PER_DEG_AT_EQ / resolution)
    print(width, height)
    return (width, height)

###### FUNCTIONS TO WRITE TO TFRECORDS ######
def _bytes_feature(value):
    """Returns a bytes_list from a string / byte."""
    if isinstance(value, type(tf.constant(0))):
        value = value.numpy() # BytesList won't unpack a string from an EagerTensor.
    return tf.train.Feature(bytes_list=tf.train.BytesList(value=[value]))

def _float_feature(value):
    """Returns a float_list from a float / double."""
    return tf.train.Feature(float_list=tf.train.FloatList(value=[value]))

def _int64_feature(value):
    """Returns an int64_list from a bool / enum / int / uint."""
    return tf.train.Feature(int64_list=tf.train.Int64List(value=[value]))

def image_example(date, img_path, coords):
    image_raw = open(img_path, 'rb').read()

    tl_x = coords[0]
    tl_y = coords[1]
    br_x = coords[2]
    br_y = coords[3]

    image_shape = tf.image.decode_png(image_raw).shape

    feature = {
        'date': _bytes_feature(bytes(date, 'utf-8')),
        'image_raw': _bytes_feature(image_raw),
        'width': _int64_feature(image_shape[0]),
        'height': _int64_feature(image_shape[1]),
        'top_left_lat' : _float_feature(tl_y),
        'top_left_long' :_float_feature(tl_x),
        'bot_right_lat' : _float_feature(br_y),
        'bot_right_long' : _float_feature(br_x),
    }

    return tf.train.Example(features=tf.train.Features(feature=feature))
###### END OF TFRECORD HELPER FUNCTIONS ######

###### MAIN DOWNLOADING FUNCTION ######
def download_area_tiff(extent: tuple, date: str, output: str):
    """
    extent: (upper latitude, left longtitude, lower latitude, right longitude)
    date: YYYY-MM-DD
    output: path/to/filename (don't specify extension)
    returns tuple with dowloaded width and height
    """
    tl_y = extent[0]
    tl_x = extent[1]
    br_y = extent[2]
    br_x = extent[3]

    width, height = calculate_width_height([br_y, tl_x, tl_y, br_x], .25)
    lat_lon = "{tx} {ty} {bx} {by}".format(tx=tl_x, ty=tl_y, bx=br_x, by=br_y)

    base = "gdal_translate -of GTiff -outsize {w} {h} -projwin {ll} '<GDAL_WMS><Service name=\"TMS\"><ServerUrl>https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/MODIS_Terra_CorrectedReflectance_TrueColor/default/{d}/250m/".format(w=width, h=height, ll=lat_lon, d=date)
    end = "${z}/${y}/${x}.jpg</ServerUrl></Service><DataWindow><UpperLeftX>-180.0</UpperLeftX><UpperLeftY>90</UpperLeftY><LowerRightX>396.0</LowerRightX><LowerRightY>-198</LowerRightY><TileLevel>8</TileLevel><TileCountX>2</TileCountX><TileCountY>1</TileCountY><YOrigin>top</YOrigin></DataWindow><Projection>EPSG:4326</Projection><BlockSizeX>512</BlockSizeX><BlockSizeY>512</BlockSizeY><BandsCount>3</BandsCount></GDAL_WMS>' "
    filename = output + "modis_" + date + ".tif"
    command = base + end + filename
    os.system(command)
    return filename

###### Helper function to generate file names for each tile ######
def generate_tile_name_with_coordinates(base, x, x_min, x_size, y, y_min, y_size, tile_width, tile_height):
    tl_x = x * x_size + x_min # find longitude of top left corner
    tl_y = y * y_size + y_min # find latitude of top left corner
    br_x = (x + tile_width) * x_size + x_min # find longitude of bottom right corner
    br_y = (y + tile_height) * y_size + y_min # find latitude of bottom right corner
    filename = base + str(f'{round(tl_y, 4):08}') + '_' + str(f'{round(tl_x, 4):09}') + '_' + str(f'{round(br_y, 4):08}') + '_' + str(f'{round(br_x, 4):09}')
    return filename


###### Main tiling function ######
def img_to_tiles(tiff_path, tile_width, tile_height, overlap, output_path, handling):
    date = tiff_path[-14:-4]
    output_base = date + "_"
        
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

    x_step, y_step = int(tile_width * (1 - overlap)), int(tile_height * (1 - overlap))
    x = 0 
    done_x = False

    if (tile_width > WIDTH or tile_height > HEIGHT):
        raise argparse.ArgumentTypeError("Tiling dimensions greater than image dimensions")
    
    while(x < WIDTH and not done_x):
        if(WIDTH - x < tile_width):
            if handling == Handling.discard_incomplete_tiles:
                done_x = True
                continue
            if handling == Handling.complete_tiles_shift:
                x = WIDTH - tile_width
            done_x = True
        done_y = False
        y = 0
        while (y < HEIGHT and not done_y):
            if(HEIGHT - y < tile_height):
                if handling == Handling.discard_incomplete_tiles:
                    done_y = True
                    continue
                if handling == Handling.complete_tiles_shift:
                    y = HEIGHT - tile_height
                done_y = True
            output_filename = generate_tile_name_with_coordinates(output_base, x, x_min, x_size, y, y_min, y_size, tile_width, tile_height)
            command = "gdal_translate -of JPEG -srcwin --config GDAL_PAM_ENABLED NO " + str(x)+ ", " + str(y) + ", " + str(tile_width) + ", " + str(tile_height) + " " + str(tiff_path) + " " + str(output_path) + str(output_filename) + ".jpeg"
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
            with tf.io.TFRecordWriter(output_path + 'modis_tf' + str(version) + '.tfrecord') as writer:
                while(total_file_size < MAX_FILE_SIZE and count < len(files)):    
                    filename = files[count]
                    date = filename[-53:-42]
                    # following lines get top left and bottom right coordinates from filename
                    tl_y = float(filename[-41:-34])
                    tl_x = float(filename[-33:-24])
                    br_y = float(filename[-23:-15])
                    br_x = float(filename[-14:-5])
                    total_file_size += os.path.getsize(directory + '/' + filename)
                    tf_example = image_example(date, directory + '/' + filename, (tl_y, tl_x, br_y, br_x))
                    writer.write(tf_example.SerializeToString())
                    count += 1
            version += 1

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
    args = parser.parse_args()

    start_date = args.start_date
    end_date = args.end_date

    output_path = args.output_path

    # get the latitude, longitude values from the user input
    top_left_coords = [float(i) for i in args.top_left_coords.split(',')]
    bottom_right_coords = [float(i) for i in args.bottom_right_coords.split(',')]
    upper_lat = top_left_coords[0]
    left_lon = top_left_coords[1]
    lower_lat = bottom_right_coords[0]
    right_lon = bottom_right_coords[1]
    
    # check if inputted coordinates are valid
    if (right_lon < left_lon or upper_lat < lower_lat):
        raise argparse.ArgumentTypeError('Inputted coordinates are invalid: order should be (upper latitude,left longitude lower latitude,right longitude)')
    
    tiling = args.tile
    tile_width = args.tile_width
    tile_height = args.tile_height
    tile_overlap = args.tile_overlap
    boundary_handling = args.boundary_handling

    logging = args.verbose

    remove_originals = args.remove_originals
    write_tfrecords = args.generate_tfrecords

    # gets paths for downloads
    download_base = "modis_" + str(round(upper_lat, 2)) + "_" + str(round(left_lon, 2)) + "_" + start_date.replace('-','') + '-' + end_date.replace('-', '')
    download_path = os.path.join(output_path, download_base)
    originals_path = download_path + '/original_images/'
    tiled_path = download_path + '/tiled_images/'
    tfrecords_path = download_path + '/tfrecords/'

    # download the original images if not already downloaded
    if not os.path.isdir(download_path):
        os.mkdir(download_path)
        os.mkdir(originals_path)
        os.mkdir(tiled_path)
        os.mkdir(tfrecords_path)
        dates = pd.date_range(start=args.start_date, end=args.end_date)
        for date in dates:
            if logging: 
                print('Downloading:', date)
            download_area_tiff((upper_lat, left_lon, lower_lat, right_lon), date.strftime("%Y-%m-%d"), originals_path)

    # tile the downloaded images
    resolution = str(tile_width) + 'x' + str(tile_height) + '_' + str(tile_overlap)
    tile_res_path = os.path.join(tiled_path, resolution) + '/'
    if tiling:
        if not os.path.isdir(tile_res_path):
            os.mkdir(tile_res_path)
            for directory, subdirectory, files in os.walk(originals_path):
                for filename in files:
                    tiff_path = os.path.join(directory, filename)
                    if logging:
                        print("Tiling image at:", tiff_path)
                    img_to_tiles(tiff_path, tile_width, tile_height, tile_overlap, tile_res_path, boundary_handling)

    #write tiles to TFRecords
    tfrecords_res_path = os.path.join(tfrecords_path, resolution) + '/'
    if write_tfrecords:
        if os.path.isdir(tile_res_path):
            if not os.path.isdir(tfrecords_res_path):
                os.mkdir(tfrecords_res_path)
                if logging: 
                    print("Writing files at:", tile_res_path, " to TFRecords")
                write_to_tfrecords(tile_res_path, tfrecords_res_path)
        else: 
            print("Unable to write to TFRecords due to nonexistent tile path")

    if remove_originals:
        if logging: 
            print("Removing original images...")
        shutil.rmtree(originals_path)
        os.mkdir(originals_path)

if __name__ == "__main__":
    main()
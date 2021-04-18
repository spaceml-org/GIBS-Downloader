#!/usr/bin/env python

import os
import shutil
import argparse
from argparse import ArgumentParser

from PIL import Image

from GIBSDownloader.coordinate_utils import Coordinate, Rectangle
from GIBSDownloader.tile import Tile
from GIBSDownloader.handling import Handling
from GIBSDownloader.product import Product
from GIBSDownloader.tile_utils import TileUtils
from GIBSDownloader.tiff_downloader import TiffDownloader
from GIBSDownloader.file_metadata import TiffMetadata
from GIBSDownloader.animator import Animator

def generate_download_path(start_date, end_date, bl_coords, output, name):
    base = "{name}_{lower_lat}_{lft_lon}_{st_date}-{end_date}".format(name=name.replace(" ","-"), lower_lat=str(round(bl_coords.y, 4)), lft_lon=str(round(bl_coords.x, 4)), st_date=start_date.replace('-',''), end_date=end_date.replace('-', ''))
    return os.path.join(output, base)

def download_originals(download_path, xml_path, originals_path, tiled_path, tfrecords_path, dates, logging, region, name, res):
    if not os.path.isdir(download_path):
        os.mkdir(download_path)
        os.mkdir(originals_path)
        os.mkdir(tiled_path)
        os.mkdir(tfrecords_path)

    if not os.path.isdir(xml_path):
        os.mkdir(xml_path)

    for date in dates:
        tiff_output = TiffDownloader.generate_download_filename(originals_path, name.replace(" ","-"), date)
        if not os.path.isfile(tiff_output + '.tif'):
            if logging:
                print('Downloading:', date)
            TiffDownloader.download_area_tiff(region, date.strftime("%Y-%m-%d"), xml_path, tiff_output, name, res)
            
    print("The specified region and set of dates have been downloaded")

def tile_originals(tile_res_path, originals_path, tile, logging, region, res):
    if not os.path.isdir(tile_res_path):
        os.mkdir(tile_res_path)

    ultra_large = False
    width, height = region.calculate_width_height(res)
    if width * height > 2 * Image.MAX_IMAGE_PIXELS:
        ultra_large = True

    files = [f for f in os.listdir(originals_path) if f.endswith('tif')]
    files.sort() # tile in chronological order

    for count, filename in enumerate(files):
        tiff_path = os.path.join(originals_path, filename) # path to GeoTiff file
        metadata = TiffMetadata(tiff_path)
        tile_date_path = tile_res_path + metadata.date + '/' # path to tiles for specific date
        if not os.path.exists(tile_date_path):
            os.mkdir(tile_date_path)
            print("Tiling day {} of {}".format(count + 1, len(files)))
            TileUtils.img_to_tiles(tiff_path, tile, tile_date_path, ultra_large)
        else: 
            print("Tiles for day {} have already been generated. Moving on to the next day".format(count + 1))
    print("The specified tiles have been generated")

def tile_to_tfrecords(tile_res_path, tfrecords_res_path, logging, name):
    from GIBSDownloader.tfrecord_utils import TFRecordUtils
    if os.path.isdir(tile_res_path):
            if not os.path.isdir(tfrecords_res_path):
                os.mkdir(tfrecords_res_path)
                if logging: 
                    print("Writing files at:", tile_res_path, " to TFRecords")
                TFRecordUtils.write_to_tfrecords(tile_res_path, tfrecords_res_path, name)
            else:
                print("The specified TFRecords have already been written")
    else: 
        print("Unable to write to TFRecords due to nonexistent tile path")

def remove_originals(originals_path, logging):
    if logging: 
        print("Removing original images...")
    shutil.rmtree(originals_path)
    os.mkdir(originals_path)

def generate_video(originals_path, region, dates, video_path, xml_path, name, res):
    if not os.path.isdir(video_path):
        if not os.path.isdir(xml_path):
            os.mkdir(xml_path)
        print("Generating video...")
        os.mkdir(video_path)
        Animator.format_images(originals_path, region, dates, video_path, xml_path, name, res)
        Animator.create_video(video_path)
        print("Video generation has finished!")
    else:
        print("The video has already been generated")

def main():
    parser = ArgumentParser()
    parser.add_argument("start_date", metavar='start-date', type=str, help="starting date for downloads")
    parser.add_argument("end_date", metavar='end-date',type=str, help="ending date for downloads")
    parser.add_argument("bottom_left_coords", metavar='bottom-left-coords', type=str, help='coordinates for bottom left corner formatted "lat, lon"')
    parser.add_argument("top_right_coords", metavar='top-right-coords', type=str, help='coordinates for top right corner formatted "lat, lon"')    
    parser.add_argument("--output-path", default=os.getcwd(), type=str, help="path to output directory")
    parser.add_argument("--tile", default=False, type=bool, help="tiling flag")
    parser.add_argument("--tile-width", default=512, type=int, help="tiled image width")
    parser.add_argument("--tile-height", default=512, type=int, help="tiled image height")
    parser.add_argument("--tile-overlap", default=0.5, type=float, help="percent overlap for each tile")
    parser.add_argument("--boundary-handling", default=Handling.complete_tiles_shift, type=Handling, help="define how to handle tiles at image boundaries", choices=list(Handling))
    parser.add_argument("--remove-originals", default=False, type=bool, help="keep/delete original downloaded images")
    parser.add_argument("--generate-tfrecords", default=False, type=bool, help="generate tfrecords for image tiles")
    parser.add_argument("--verbose", default=False, type=bool, help="log downloading process")
    parser.add_argument("--product", default=None, type=Product, help="select the NASA imagery product", choices=list(Product))
    parser.add_argument("--keep-xml", default=False, type=bool, help="preserve the xml files generated to download images")
    parser.add_argument("--animate", default=False, type=bool, help="Generate a timelapse video of the downloaded region")
    parser.add_argument("--name", default=str(Product.viirs)+",0.25", type=str, help="enter the full name of the NASA imagery product and its image resolution separated by comma")
    

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
    product = args.product
    keep_xml = args.keep_xml
    animate = args.animate
    
    # check if user used "product" argument for shortened products list
    if product is not None:
        name = product.get_long_name().replace("_"," ")
        res = .25
    else:
        name, res = args.name.replace("_"," ").split(",")
        res = float(res)

    # get the latitude, longitude values from the user input
    bl_coords = Coordinate([float(i) for i in args.bottom_left_coords.replace(" ","").split(',')])
    tr_coords = Coordinate([float(i) for i in args.top_right_coords.replace(" ", "").split(',')])
    region = Rectangle(bl_coords, tr_coords)
    
    # check if inputted coordinates are valid
    if (bl_coords.x > tr_coords.x or bl_coords.y > tr_coords.y):
        raise argparse.ArgumentTypeError('Inputted coordinates are invalid: order should be (lower_latitude,left_longitude upper_latitude,right_longitude)')

    # gets paths for downloads
    download_path = generate_download_path(start_date, end_date, bl_coords, output_path, name)
    xml_path = download_path + '/xml_configs/'
    originals_path = download_path + '/original_images/'
    tiled_path = download_path + '/tiled_images/'
    tfrecords_path = download_path + '/tfrecords/'
    video_path = download_path + '/video/'
    resolution = "{t_width}x{t_height}_{t_overlap}".format(t_width=str(tile.width), t_height=str(tile.height), t_overlap=str(tile.overlap))
    tile_res_path = os.path.join(tiled_path, resolution) + '/'
    tfrecords_res_path = os.path.join(tfrecords_path, resolution) + '/'

    # get range of dates
    dates = TiffDownloader.get_dates_range(start_date, end_date)

    download_originals(download_path, xml_path, originals_path, tiled_path, tfrecords_path, dates, logging, region, name, res)

    if tiling:
        tile_originals(tile_res_path, originals_path, tile, logging, region, res)

    if write_tfrecords:
        tile_to_tfrecords(tile_res_path, tfrecords_res_path, logging, name)
        
    if animate:
        generate_video(originals_path, region, dates, video_path, xml_path, name, res)
    
    if rm_originals:
        remove_originals(originals_path, logging)

    if not keep_xml:
        if os.path.exists(xml_path):
            shutil.rmtree(xml_path)

if __name__ == "__main__":
    main()
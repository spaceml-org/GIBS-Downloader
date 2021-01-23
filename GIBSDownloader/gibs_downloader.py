#!/usr/bin/env python

import os
import shutil
import argparse
from argparse import ArgumentParser

from GIBSDownloader.coordinate_utils import Coordinate, Rectangle
from GIBSDownloader.tile import Tile
from GIBSDownloader.handling import Handling
from GIBSDownloader.product import Product
from GIBSDownloader.tile_utils import TileUtils
from GIBSDownloader.tiff_downloader import TiffDownloader
from GIBSDownloader.file_metadata import TiffMetadata

def generate_download_path(start_date, end_date, bl_coords, output, product):
    base = "{name}_{lower_lat}_{lft_lon}_{st_date}-{end_date}".format(name=str(product), lower_lat=str(round(bl_coords.y, 4)), lft_lon=str(round(bl_coords.x, 4)), st_date=start_date.replace('-',''), end_date=end_date.replace('-', ''))
    return os.path.join(output, base)

def download_originals(download_path, xml_path, originals_path, tiled_path, tfrecords_path, start_date, end_date, logging, region, product):
    if not os.path.isdir(download_path):
        os.mkdir(download_path)
        os.mkdir(xml_path)
        os.mkdir(originals_path)
        os.mkdir(tiled_path)
        os.mkdir(tfrecords_path)
        dates = TiffDownloader.get_dates_range(start_date, end_date)
        for date in dates:
            if logging: 
                print('Downloading:', date)
            TiffDownloader.download_area_tiff(region, date.strftime("%Y-%m-%d"), download_path, xml_path, originals_path, product)
    else:
        print("The specified region and set of dates has already been downloaded")

def tile_originals(tile_res_path, originals_path, tile, logging):
    if not os.path.isdir(tile_res_path):
            os.mkdir(tile_res_path)
            for directory, subdirectory, files in os.walk(originals_path):
                for count, filename in enumerate(files):
                    tiff_path = os.path.join(directory, filename)
                    metadata = TiffMetadata(tiff_path)
                    tile_date_path = tile_res_path + metadata.date + '/'
                    if not os.path.exists(tile_date_path):
                        os.mkdir(tile_date_path)
                    print("Tiling {} of {} images".format(count+1, len(files)))
                    TileUtils.img_to_tiles(tiff_path, tile, tile_date_path)
    else:
        print("The specified tiles for these images have already been generated")

def tile_to_tfrecords(tile_res_path, tfrecords_res_path, logging, product):
    from GIBSDownloader.tfrecord_utils import TFRecordUtils
    if os.path.isdir(tile_res_path):
            if not os.path.isdir(tfrecords_res_path):
                os.mkdir(tfrecords_res_path)
                if logging: 
                    print("Writing files at:", tile_res_path, " to TFRecords")
                TFRecordUtils.write_to_tfrecords(tile_res_path, tfrecords_res_path, product)
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
    parser.add_argument("--product", default=Product.viirs, type=Product, help="select the NASA imagery product", choices=list(Product))
    parser.add_argument("--keep-xml", default=False, type=bool, help="keep the xml files generated to download images")

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

    # get the latitude, longitude values from the user input
    bl_coords = Coordinate([float(i) for i in args.bottom_left_coords.replace(" ","").split(',')])
    tr_coords = Coordinate([float(i) for i in args.top_right_coords.replace(" ", "").split(',')])
    region = Rectangle(bl_coords, tr_coords)
    
    # check if inputted coordinates are valid
    if (bl_coords.x > tr_coords.x or bl_coords.y > tr_coords.y):
        raise argparse.ArgumentTypeError('Inputted coordinates are invalid: order should be (lower_latitude,left_longitude upper_latitude,right_longitude)')

    # gets paths for downloads
    download_path = generate_download_path(start_date, end_date, bl_coords, output_path, product)
    xml_path = download_path + '/xml_configs/'
    originals_path = download_path + '/original_images/'
    tiled_path = download_path + '/tiled_images/'
    tfrecords_path = download_path + '/tfrecords/'
    resolution = "{t_width}x{t_height}_{t_overlap}".format(t_width=str(tile.width), t_height=str(tile.height), t_overlap=str(tile.overlap))
    tile_res_path = os.path.join(tiled_path, resolution) + '/'
    tfrecords_res_path = os.path.join(tfrecords_path, resolution) + '/'

    download_originals(download_path, xml_path, originals_path, tiled_path, tfrecords_path, start_date, end_date, logging, region, product)

    if tiling:
        tile_originals(tile_res_path, originals_path, tile, logging)

    if write_tfrecords:
        tile_to_tfrecords(tile_res_path, tfrecords_res_path, logging, product)
        
    if rm_originals:
        remove_originals(originals_path, logging)

    if not keep_xml:
        shutil.rmtree(xml_path)

if __name__ == "__main__":
    main()
#!/usr/bin/env python
import argparse
from argparse import ArgumentParser
import logging
import os
import sys
import shutil

from PIL import Image

from GIBSDownloader.coordinate_utils import Coordinate, Rectangle
from GIBSDownloader.tile import Tile
from GIBSDownloader.handling import Handling
from GIBSDownloader.product import Product
from GIBSDownloader.tile_utils import TileUtils
from GIBSDownloader.tiff_downloader import TiffDownloader
from GIBSDownloader.file_metadata import TiffMetadata
from GIBSDownloader.animator import Animator
from GIBSDownloader.dataset_searcher import DatasetSearcher
from GIBSDownloader.log_utils import init_log
from GIBSDownloader import log

# Constants
MAX_JPEG_SIZE = 65500
LOGFILENAME = "gdl.log"

def generate_download_path(start_date, end_date, bl_coords, tr_coords, output, name):
    """
    Creates path name to general download directory for all download files.

    Every unique (product, region, dates) combination that the user downloads 
    should generate a unique download path. If the user selects the same 
    product, region, and range of dates, then the same path should be returned,
    granted that the user specifies the same `output`

    Parameters:
        start_date (str): starting date for range of downloads
        end_date (str): ending date for range of downloads
        bl_coords (Coordinate): bottom left coordinates of the requested region
        tr_coords (Coordinate): top right coordinates of the requested region
        output (str): path to where the directory should be created
        name (str): name of the product being downloaded

    Returns:
        path to output directory where everything should be downloaded
    """
    base = "{name}_{lower_lat}_{lft_lon}_{upper_lat}_{rgt_lon}_{st_date}-{end_date}".format(
        name=name.replace(" ","-"), 
        lower_lat=str(round(bl_coords.y, 2)), 
        lft_lon=str(round(bl_coords.x, 2)), 
        upper_lat=str(round(tr_coords.y, 2)), 
        rgt_lon=str(round(tr_coords.x, 2)), 
        st_date=start_date.replace('-',''), 
        end_date=end_date.replace('-', '')
        )
    return os.path.join(output, base)

def download_originals(download_path, xml_path, originals_path, tiled_path, tfrecords_path, dates, region, name, res, img_format, logfile):
    """ 
    Downloads the specified region for the range of dates

    If a dimension of the image of the region being downloaded exceeds the max 
    JPEG size limit, GeoTiff is chosen as the image format since it offers a
    sufficiently large size.

    After this function is executed, the user will have a directory set up as
    follows:
    download_path/
      |> original_images/
      |> tiled_images/
      |> tfrecords/
      |> xml_configs/

    Parameters:
        download_path (str): path to all output
        xml_path (str): path to xml configs subdirectory
        originals_path (str): path to original image downloads subdirectory
        tiled_path (str): path to tiles subdirectory
        tfrecords_path (str): path to tfrecords subdirectory
        dates (date list): list of dates in the download range
        region (Rectangle): rectangular download region
        name (str): product name
        res (float): product resolution
        img_format: product image format
        logfile (str): path to log file tracking download's progress

    Returns:
        img_format (str): the format of the downloaded images 
        (might be different than what is specified by the product if the 
        region is too large)
    """
    if not os.path.isdir(download_path):
        os.mkdir(download_path)
        os.mkdir(originals_path)
        os.mkdir(tiled_path)
        os.mkdir(tfrecords_path)

    if not os.path.isdir(xml_path):
        os.mkdir(xml_path)

    width, height = region.calculate_width_height(res)
    if width > MAX_JPEG_SIZE or height > MAX_JPEG_SIZE:
        img_format = 'tif'

    for date in dates:
        tiff_output = TiffDownloader.generate_download_filename(originals_path, name.replace(" ","-"), date) + '.' + img_format
        if not os.path.isfile(tiff_output):
            log.info('Downloading: %s', date.strftime("%Y-%m-%d"))
            TiffDownloader.download_area_tiff(region, date.strftime("%Y-%m-%d"), xml_path, tiff_output, name, res, img_format, logfile)
            
    log.info("The specified region and set of dates have been downloaded")
    return img_format

def tile_originals(originals_path, tile_res_path, tile, region, res, img_format, mp, ext=None):
    """
    Tiles all the downloaded images.

    After this function is executed, there will be a subdirectory inside of 
    `tiled_images/` specifying the dimensions of the tiles and their resolution.
    This subdirectory (`tile_res_path`) contains all the generated tiles.

    Parameters:
        tile_res_path (str): target output subdirectory for tiles
        originals_path (originals_path): path to downloaded images
        tile (Tile): Tile object storing tiling information
        region (Rectangle): rectangular download region
        img_format (str): image format specified by the product
        mp (bool): multiprocessing flag
        ext (str): image format actually downloaded
    """
    if not os.path.isdir(tile_res_path):
        os.mkdir(tile_res_path)

    files = [f for f in os.listdir(originals_path) if f.endswith(ext)]
    files.sort() # tile in chronological order

    for count, filename in enumerate(files):
        tiff_path = os.path.join(originals_path, filename) # path to GeoTiff file
        metadata = TiffMetadata(tiff_path)
        tile_date_path = tile_res_path + metadata.date + '/' # path to tiles for specific date
        if not os.path.exists(tile_date_path):
            os.mkdir(tile_date_path)
            msg = "Tiling day {} of {}".format(count + 1, len(files))
            log.info(msg)
            TileUtils.img_to_tiles(tiff_path, region, res, tile, tile_date_path, img_format, mp)
        else: 
            msg = "Tiles for day {} have already been generated. Moving on to the next day".format(count + 1)
            log.info(msg)
    log.info("The specified tiles have been generated")

def tile_to_tfrecords(tile_res_path, tfrecords_res_path, name, img_format):
    """
    Writes the generated tiles to TFRecords for efficient training in machine 
    learning pipelines

    Parameters:
        tile_res_path (str): path to tiles
        tfrecords_res_path (str): target output subdirectory for tfrecords
        name (str): product name
        img_format (str): product image format
    """
    from GIBSDownloader.tfrecord_utils import TFRecordUtils
    if os.path.isdir(tile_res_path):
            if not os.path.isdir(tfrecords_res_path):
                os.mkdir(tfrecords_res_path)
                msg = "Writing files at: {} to TFRecords".format(tile_res_path)
                log.info(msg)
                TFRecordUtils.write_to_tfrecords(tile_res_path, tfrecords_res_path, name, img_format)
            else:
                log.info("The specified TFRecords have already been written")
    else: 
        log.info("Unable to write to TFRecords due to nonexistent tile path")

def remove_originals(originals_path):
    """Delete the original downloaded images"""
    log.info("Removing original images...")
    shutil.rmtree(originals_path)
    os.mkdir(originals_path)

def generate_video(originals_path, region, dates, video_path, xml_path, name, res, img_format):
    """
    Create a video of the original images across the range of downloaded dates.

    Parameters:
        originals_path (str): path to original image downloads subdirectory
        region (Rectangle): rectangular download region
        dates (date list): list of dates in the download range
        video_path (str): path to video ouput subdirectory
        xml_path (str): path to xml configs subdirectory
        name (str): product name
        res (float): product resolution
        img_format: product image format
    """
    if not os.path.isdir(video_path):
        if not os.path.isdir(xml_path):
            os.mkdir(xml_path)
        log.info("Generating video...")
        os.mkdir(video_path)
        Animator.format_images(originals_path, region, dates, video_path, xml_path, name, res, img_format)
        Animator.create_video(video_path, img_format)
        log.info("Video generation has finished!")
    else:
        log.info("The video has already been generated")

def main():
    """
    Parses user arguments and carries out command.

    If user inputted invalid arguments, program exits and logs error.
    See README.md for expected argument values
    """
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
    parser.add_argument("--gen-tfrecords", default=False, type=bool, help="generate tfrecords for image tiles")
    parser.add_argument("--product", default=None, type=Product, help="select the NASA imagery product", choices=list(Product))
    parser.add_argument("--keep-xml", default=False, type=bool, help="preserve the xml files generated to download images")
    parser.add_argument("--animate", default=False, type=bool, help="Generate a timelapse video of the downloaded region")
    parser.add_argument("--name", default="VIIRS_SNPP_CorrectedReflectance_TrueColor", type=str, help="enter the full name of the NASA imagery product and its image resolution separated by comma")
    parser.add_argument("--mp", default=False, type=bool, help="utilize multiprocessing to generate tiles")
    parser.add_argument("--res", default=None, type=float, help="set the download resolution from these values [0.03, 0.06, 0.125, 0.25, 0.5, 1, 5, 10]")

    # Get the user input
    args = parser.parse_args()
    
    # Select the imagery product
    name = args.name
    if args.product is not None:
        name = args.product.get_long_name()
    name, res, img_format = DatasetSearcher.getProductInfo(name)
    if args.res is not None:
        res = args.res

    # Get the latitude, longitude, and tiling values from the user input
    bl_coords = Coordinate([float(i) for i in args.bottom_left_coords.replace(" ","").split(',')])
    tr_coords = Coordinate([float(i) for i in args.top_right_coords.replace(" ", "").split(',')])
    region = Rectangle(bl_coords, tr_coords)
    tile = Tile(args.tile_width, args.tile_height, args.tile_overlap, args.boundary_handling)
    
    # Check if inputted coordinates are valid
    if (bl_coords.x > tr_coords.x or bl_coords.y > tr_coords.y):
        log.error('Inputted coordinates are invalid: order should be (lower_latitude,left_longitude upper_latitude,right_longitude)')
        sys.exit(1)

    # Gets paths for downloads
    download_path = generate_download_path(args.start_date, args.end_date, bl_coords, tr_coords, args.output_path, name)
    xml_path = download_path + '/xml_configs/'
    originals_path = download_path + '/original_images/'
    tiled_path = download_path + '/tiled_images/'
    tfrecords_path = download_path + '/tfrecords/'
    video_path = download_path + '/video/'
    resolution = "{t_width}x{t_height}_{t_overlap}".format(t_width=str(tile.width), t_height=str(tile.height), t_overlap=str(tile.overlap))
    tile_res_path = os.path.join(tiled_path, resolution) + '/'
    tfrecords_res_path = os.path.join(tfrecords_path, resolution) + '/'

    # Create subdirectories
    if not os.path.isdir(download_path):
        os.mkdir(download_path)
        os.mkdir(originals_path)
        os.mkdir(tiled_path)
        os.mkdir(tfrecords_path)

    # Add a file handler to the log
    logfile = os.path.join(download_path, LOGFILENAME)
    init_log(log, logfile)

    # Get range of dates
    dates = TiffDownloader.get_dates_range(args.start_date, args.end_date)

    # Find the format of the image actually downloaded (may differ from the product's specified format if image too large)
    img_format_cmd = download_originals(download_path, xml_path, originals_path, tiled_path, tfrecords_path, dates, region, name, res, img_format, logfile)

    if args.tile:
        tile_originals(originals_path, tile_res_path, tile, region, res, img_format, args.mp, ext=img_format_cmd)

    if args.gen_tfrecords:
        tile_to_tfrecords(tile_res_path, tfrecords_res_path, name, img_format)

    if args.animate:
        generate_video(originals_path, region, dates, video_path, xml_path, name, res, img_format)

    if args.remove_originals:
        remove_originals(originals_path)

    if not args.keep_xml and os.path.exists(xml_path):
        shutil.rmtree(xml_path)

if __name__ == "__main__":
    main()
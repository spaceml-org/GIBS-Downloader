#!/usr/bin/env python
import argparse
from argparse import ArgumentParser
import logging
import os
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

# Constants
MAX_JPEG_SIZE = 65500

def generate_download_path(start_date, end_date, bl_coords, tr_coords, output, name):
    """
    Creates path name to general download directory for all download files.

    Every unique (product, region, dates) combination that the user downloads 
    should generate a unique download path. If the user selects the same 
    product, region, and range of dates, then the same path should be returned,
    granted that the user specifies the same `output`

    Parameters:
        start_date (string): starting date for range of downloads
        end_date (string): ending date for range of downloads
        bl_coords (Coordinate): bottom left coordinates of the requested region
        tr_coords (Coordinate): top right coordinates of the requested region
        output (string): path to where the directory should be created
        name (string): name of the product being downloaded

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

"""TODO remove logging and use logger"""
def download_originals(download_path, xml_path, originals_path, tiled_path, tfrecords_path, dates, logging, region, name, res, img_format):
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
        download_path (string): path to all output
        xml_path (string): path to xml configs subdirectory
        originals_path (string): path to original image downloads subdirectory
        tiled_path (string): path to tiles subdirectory
        tfrecords_path (string): path to tfrecords subdirectory
        dates (date list): list of dates in the download range
        region (Rectangle): rectangular download region
        name (string): product name
        res (float): product resolution
        img_format: product image format

    Returns:
        img_format (string): the format of the downloaded images 
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
            print('Downloading:', date)
            TiffDownloader.download_area_tiff(region, date.strftime("%Y-%m-%d"), xml_path, tiff_output, name, res, img_format)

    print("The specified region and set of dates have been downloaded")
    return img_format

def tile_originals(originals_path, tile_res_path, tile, logging, region, res, img_format, mp, ext=None):
    """
    Tiles all the downloaded images.

    After this function is executed, there will be a subdirectory inside of 
    `tiled_images/` specifying the dimensions of the tiles and their resolution.
    This subdirectory (`tile_res_path`) contains all the generated tiles.

    Parameters:
        tile_res_path (string): target output subdirectory for tiles
        originals_path (originals_path): path to downloaded images
        tile (Tile): Tile object storing tiling information
        region (Rectangle): rectangular download region
        img_format (string): image format specified by the product
        mp (bool): multiprocessing flag
        ext (string): image format actually downloaded
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
            print("Tiling day {} of {}".format(count + 1, len(files)), flush=True)
            TileUtils.img_to_tiles(tiff_path, region, res, tile, tile_date_path, img_format, mp)
        else: 
            print("Tiles for day {} have already been generated. Moving on to the next day".format(count + 1))
    print("The specified tiles have been generated")

def tile_to_tfrecords(tile_res_path, tfrecords_res_path, logging, name, img_format):
    """
    Writes the generated tiles to TFRecords for efficient training in machine 
    learning pipelines

    Parameters:
        tile_res_path (string): path to tiles
        tfrecords_res_path (string): target output subdirectory for tfrecords
        name (string): product name
        img_format (string): product image format
    """
    from GIBSDownloader.tfrecord_utils import TFRecordUtils
    if os.path.isdir(tile_res_path):
            if not os.path.isdir(tfrecords_res_path):
                os.mkdir(tfrecords_res_path)
                if logging:
                    print("Writing files at:", tile_res_path, " to TFRecords")
                TFRecordUtils.write_to_tfrecords(tile_res_path, tfrecords_res_path, name, img_format)
            else:
                print("The specified TFRecords have already been written")
    else:
        print("Unable to write to TFRecords due to nonexistent tile path")

def remove_originals(originals_path, logging):
    """Delete the original downloaded images"""
    if logging: 
        print("Removing original images...")
    shutil.rmtree(originals_path)
    os.mkdir(originals_path)

def generate_video(originals_path, region, dates, video_path, xml_path, name, res, img_format):
    """
    Create a video of the original images across the range of downloaded dates.

    Parameters:
        originals_path (string): path to original image downloads subdirectory
        region (Rectangle): rectangular download region
        dates (date list): list of dates in the download range
        video_path (string): path to video ouput subdirectory
        xml_path (string): path to xml configs subdirectory
        name (string): product name
        res (float): product resolution
        img_format: product image format
    """
    if not os.path.isdir(video_path):
        if not os.path.isdir(xml_path):
            os.mkdir(xml_path)
        print("Generating video...")
        os.mkdir(video_path)
        Animator.format_images(originals_path, region, dates, video_path, xml_path, name, res, img_format)
        Animator.create_video(video_path, img_format)
        print("Video generation has finished!")
    else:
        print("The video has already been generated")

def main():
    """
    Parses user arguments and carries out command.

    If user inputted invalid arguments, program exits with argparse.ArgumentTypeError.
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
    parser.add_argument("--verbose", default=False, type=bool, help="log downloading process")
    parser.add_argument("--product", default=None, type=Product, help="select the NASA imagery product", choices=list(Product))
    parser.add_argument("--keep-xml", default=False, type=bool, help="preserve the xml files generated to download images")
    parser.add_argument("--animate", default=False, type=bool, help="Generate a timelapse video of the downloaded region")
    parser.add_argument("--name", default="VIIRS_SNPP_CorrectedReflectance_TrueColor", type=str, help="enter the full name of the NASA imagery product and its image resolution separated by comma")
    parser.add_argument("--mp", default=False, type=bool, help="utilize multiprocessing to generate tiles")

    # Get the user input
    args = parser.parse_args()
    start_date = args.start_date
    end_date = args.end_date
    output_path = args.output_path
    logging = args.verbose
    rm_originals = args.remove_originals
    write_tfrecords = args.gen_tfrecords
    tiling = args.tile
    tile = Tile(args.tile_width, args.tile_height, args.tile_overlap, args.boundary_handling)
    product = args.product
    keep_xml = args.keep_xml
    animate = args.animate
    name = args.name
    mp = args.mp

    if product is not None:
        name = product.get_long_name()

    name, res, img_format = DatasetSearcher.getProductInfo(name)

    # Get the latitude, longitude values from the user input
    bl_coords = Coordinate([float(i) for i in args.bottom_left_coords.replace(" ","").split(',')])
    tr_coords = Coordinate([float(i) for i in args.top_right_coords.replace(" ", "").split(',')])
    region = Rectangle(bl_coords, tr_coords)

    # Check if inputted coordinates are valid
    if (bl_coords.x > tr_coords.x or bl_coords.y > tr_coords.y):
        raise argparse.ArgumentTypeError('Inputted coordinates are invalid: order should be (lower_latitude,left_longitude upper_latitude,right_longitude)')

    # Gets paths for downloads
    download_path = generate_download_path(start_date, end_date, bl_coords, tr_coords, output_path, name)
    xml_path = download_path + '/xml_configs/'
    originals_path = download_path + '/original_images/'
    tiled_path = download_path + '/tiled_images/'
    tfrecords_path = download_path + '/tfrecords/'
    video_path = download_path + '/video/'
    resolution = "{t_width}x{t_height}_{t_overlap}".format(t_width=str(tile.width), t_height=str(tile.height), t_overlap=str(tile.overlap))
    tile_res_path = os.path.join(tiled_path, resolution) + '/'
    tfrecords_res_path = os.path.join(tfrecords_path, resolution) + '/'

    # Get range of dates
    dates = TiffDownloader.get_dates_range(start_date, end_date)

    # Find the format of the image actually downloaded (may differ from the product's specified format if image too large)
    img_format_cmd = download_originals(download_path, xml_path, originals_path, tiled_path, tfrecords_path, dates, logging, region, name, res, img_format)

    if tiling:
        tile_originals(originals_path, tile_res_path, tile, logging, region, res, img_format, mp, ext=img_format_cmd)

    if write_tfrecords:
        tile_to_tfrecords(tile_res_path, tfrecords_res_path, logging, name, img_format)

    if animate:
        generate_video(originals_path, region, dates, video_path, xml_path, name, res, img_format)

    if rm_originals:
        remove_originals(originals_path, logging)

    if not keep_xml and os.path.exists(xml_path):
        shutil.rmtree(xml_path)

if __name__ == "__main__":
    main()

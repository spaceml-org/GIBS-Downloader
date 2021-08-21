import argparse
import os
import math
import warnings
import shutil
import itertools
from itertools import repeat
import multiprocessing
from multiprocessing import RawArray
from multiprocessing import Pool

import numpy as np
from matplotlib import pyplot as plt
from PIL import Image
from tqdm import tqdm 
from bs4 import BeautifulSoup as bs

from GIBSDownloader.tile import Tile
from GIBSDownloader.handling import Handling
from GIBSDownloader.file_metadata import TiffMetadata, IntermediateMetadata
from GIBSDownloader.coordinate_utils import Coordinate, Rectangle

warnings.simplefilter('ignore', Image.DecompressionBombWarning) # ignore image size warnings

MAX_INTERMEDIATE_LENGTH = int(math.sqrt(2 * Image.MAX_IMAGE_PIXELS)) # Maximum width and height for an intermediate tile to guarantee num pixels less than PIL's max
NUM_CORES = multiprocessing.cpu_count()

arr_dict = {}

def init_worker(X, X_shape, Y, Y_shape):
    """ X and Y are RawArrays that are shared between child processes """
    arr_dict['X'] = X
    arr_dict['X_shape'] = X_shape
    arr_dict['Y'] = Y
    arr_dict['Y_shape'] = Y_shape

def get_tiling_split_coords_tuple(metadata, tile, WIDTH, HEIGHT, geotran_d, tile_date_path, num_rows, num_cols, index):
    row = index // num_cols
    col = index % num_cols

    x_step, y_step = int(tile.width * (1 - tile.overlap)), int(tile.height * (1 - tile.overlap))

    x = col * x_step
    y = row * y_step
    done_x, done_y = WIDTH - x < tile.width, HEIGHT - y < tile.height

    if (done_x or done_y) and tile.handling == Handling.discard_incomplete_tiles:
        return None

    if done_x and tile.handling == Handling.complete_tiles_shift:
        x = WIDTH - tile.width
    if done_y and tile.handling == Handling.complete_tiles_shift:
        y = HEIGHT - tile.height

    path = TileUtils.generate_tile_directories(metadata, tile, x, y, geotran_d, tile_date_path)
    return (x,y, done_x, done_y, path)

def get_tiling_split_coords_MP(args):
    """ Wrapper function to unpack args """
    (metadata, index) = args
    return get_tiling_split_coords_tuple(*metadata, index)

def process_doubles_tuple(t_width, t_height, inter_dir, img_format, double_inter_imgs):
    filename_left = double_inter_imgs[0][0]
    filename_right = double_inter_imgs[0][1]

    inter_metadata_left = IntermediateMetadata(filename_left)
    inter_metadata_right = IntermediateMetadata(filename_right)

    img_path_left = os.path.join(inter_dir, filename_left)
    img_path_right = os.path.join(inter_dir, filename_right)

    src_left = Image.open(img_path_left)
    img_arr_left = np.array(src_left)

    src_right = Image.open(img_path_right)
    img_arr_right = np.array(src_right)

    # Sequentially generate tiles
    for _, _, x, y, done_x, done_y, path in double_inter_imgs:
        TileUtils.generate_tile_between_two_images(t_width, t_height, inter_metadata_left.end_x - inter_metadata_left.start_x, inter_metadata_left.end_y - inter_metadata_left.start_y, x, y, done_x, done_y, x - inter_metadata_left.start_x, y - inter_metadata_left.start_y, path, img_format, img_arr_left=img_arr_left, img_arr_right=img_arr_right)
    
    # Close the images
    src_left.close()
    src_right.close()
    return 1

def process_doubles_MP(args):
    """ Wrapper function to unpack args """
    (metadata, double_inter_imgs) = args
    return process_doubles_tuple(*metadata, double_inter_imgs)

def process_quads_tuple(t_width, t_height, inter_dir, img_format, quad_inter_imgs):
    filename_TL = quad_inter_imgs[0][0]
    filename_BL = quad_inter_imgs[0][1]
    filename_TR = quad_inter_imgs[0][2]
    filename_BR = quad_inter_imgs[0][3]       

    inter_metadata_TL = IntermediateMetadata(filename_TL)
    inter_metadata_TR = IntermediateMetadata(filename_TR)
    inter_metadata_BL = IntermediateMetadata(filename_BL)
    inter_metadata_BR = IntermediateMetadata(filename_BR)

    img_path_TL = os.path.join(inter_dir, filename_TL)
    img_path_TR = os.path.join(inter_dir, filename_TR)
    img_path_BL = os.path.join(inter_dir, filename_BL)
    img_path_BR = os.path.join(inter_dir, filename_BR)

    src_TL = Image.open(img_path_TL)
    img_arr_TL = np.array(src_TL)

    src_TR = Image.open(img_path_TR)
    img_arr_TR = np.array(src_TR)

    src_BL = Image.open(img_path_BL)
    img_arr_BL = np.array(src_BL)
    
    src_BR = Image.open(img_path_BR)
    img_arr_BR = np.array(src_BR)

    # Sequentially generate the tiles between four images since overhead in allocating the four RawArrays is not worth it for the few tiles that lie between four images
    for _, _, _, _, x, y, done_x, done_y, path in quad_inter_imgs:
        TileUtils.generate_tile_between_four_images(t_width, t_height, img_arr_TL, img_arr_TR, img_arr_BL, img_arr_BR, inter_metadata_TL.end_x - inter_metadata_TL.start_x, inter_metadata_TL.end_y - inter_metadata_TL.start_y, x, y, done_x, done_y, x - inter_metadata_TL.start_x, y - inter_metadata_TL.start_y, path, img_format)

    # Close the images
    src_TL.close()
    src_TR.close()
    src_BL.close()
    src_BR.close()
    return 1

def process_quads_MP(args):
    """ Wrapper function to unpack args """
    (metadata, quad_inter_imgs) = args
    return process_quads_tuple(*metadata, quad_inter_imgs)

class TileUtils():
    @classmethod
    def get_geotransform(cls, path):
        filename, ext = os.path.splitext(path)
        content = []
        if ext == ".tif": # Read the tfw file
            with open(filename + ".tfw", "r") as f:
                # Read each line in the file, readlines() returns a list of lines
                content = f.readlines()
                geotran_d = {"x_min":float(content[4]),"x_size": float(content[0]), "y_min":float(content[5]),"y_size": float(content[3])}
        else: # Read the auxiliary XML file
            with open(path + ".aux.xml", "r") as f:
                content = f.readlines()
                # Combine the lines in the list into a string
                content = "".join(content)
                bs_content = bs(content, "lxml")
                values = str(bs_content.find("geotransform")).replace("<geotransform> ", "").replace("</geotransform>","").split(",")
                geotran_d = {"x_min":float(values[0]),"x_size": float(values[1]), "y_min":float(values[3]),"y_size": float(values[5])}
        return geotran_d

    @classmethod
    def get_num_rows_cols(cls, tile, width, height):
        """ Compute the number of tiles per row and column in the image """
        if tile.handling == Handling.discard_incomplete_tiles:
            num_rows = (height - tile.height * tile.overlap) // (tile.height * (1 -  tile.overlap))
            num_cols = (width - tile.width * tile.overlap) // (tile.width * (1 - tile.overlap))
        else:
            num_rows = math.ceil((height - tile.height * tile.overlap) / (tile.height * (1 -  tile.overlap)))
            num_cols = math.ceil((width - tile.width * tile.overlap) / (tile.width * (1 - tile.overlap)))
        return num_rows, num_cols

    @classmethod
    def img_to_tiles(cls, tiff_path, region, res, tile, tile_date_path, img_format, mp):
        """
            Thanks to Mianzhi Wang for publishing a great article explaining shared memory for multiprocessing
            https://research.wmz.ninja/articles/2018/03/on-sharing-large-arrays-when-using-pythons-multiprocessing.htmlfor
        """

        # Get metadata from original image
        metadata = TiffMetadata(tiff_path)
        WIDTH, HEIGHT = region.calculate_width_height(res)

        # Check for valid tiling dimensions
        if (tile.width > WIDTH or tile.height > HEIGHT):
            raise argparse.ArgumentTypeError("Tiling dimensions greater than image dimensions")

        # Check the number of pixels in the image
        ultra_large = WIDTH * HEIGHT > 2 * Image.MAX_IMAGE_PIXELS

        # Use the following dictionary to get the coordinates of each tile
        geotran_d = TileUtils.get_geotransform(tiff_path)

        num_rows, num_cols =  TileUtils.get_num_rows_cols(tile, WIDTH, HEIGHT)

        print("Gathering tiling information...", end="", flush=True)
        pixel_coords = TileUtils.generate_pixel_coords(tile, WIDTH, HEIGHT, num_rows, num_cols, metadata, geotran_d, tile_date_path, mp)
        print("done!")

        if mp:
            print("Generating {} tiles using {} processes...".format(len(pixel_coords), NUM_CORES), flush=True)
        else:
            print("Generating {} tiles sequentially...".format(len(pixel_coords)), flush=True)

        if ultra_large: 
            TileUtils.generate_ultra_large_tiles(tiff_path, tile, WIDTH, HEIGHT, pixel_coords, img_format, mp, metadata.date)
        else: 
            TileUtils.generate_regular_tiles(tiff_path, tile, WIDTH, HEIGHT, pixel_coords, img_format, mp)
        print("done!")

    @classmethod
    def generate_pixel_coords(cls, tile, WIDTH, HEIGHT, num_rows, num_cols, metadata, geotran_d, tile_date_path, mp):
        """
            @returns a list with all pixel coordinate information for the tiles that will be generated
        """
        num_tiles = num_rows * num_cols
        if mp:
            with Pool(processes=NUM_CORES) as pool:
                args = zip(repeat((metadata, tile, WIDTH, HEIGHT, geotran_d, tile_date_path, num_rows, num_cols)), list(range(num_tiles)))
                pixel_coords = pool.map(get_tiling_split_coords_MP, args)
        else:
            pixel_coords = [
                get_tiling_split_coords_tuple(
                    metadata,
                    tile,
                    WIDTH,
                    HEIGHT,
                    geotran_d,
                    tile_date_path,
                    num_rows,
                    num_cols,
                    index
                )
                for index in range(num_tiles)
            ]
        return pixel_coords

    @classmethod
    def generate_regular_tiles(cls, tiff_path, tile, WIDTH, HEIGHT, pixel_coords, img_format, mp):
        """
            Generates tiles for non-ultra-large images
        """
        # Open image as a numpy array in order to tile from the array
        src = Image.open(tiff_path)
        img_arr = np.array(src)

        if mp:
            # Create a shared array
            X_shape = img_arr.shape
            X = RawArray('B', X_shape[0] * X_shape[1] * X_shape[2])

            # Wrap shared array as numpy array
            X_np = np.frombuffer(X, dtype='uint8').reshape(X_shape)

            # Copy image to the shared array
            np.copyto(X_np, img_arr)

            # Use multiprocessing to tile the numpy array
            with Pool(processes=NUM_CORES, initializer=init_worker, initargs=(X, X_shape, None, None)) as pool:
                multi = [pool.apply_async(TileUtils.generate_tile_from_arr, args=(tile, WIDTH, HEIGHT, x, y, done_x, done_y, path, img_format)) for (x, y, done_x, done_y, path) in pixel_coords]
                f = [p.get() for p in tqdm(multi)]
                pool.close()
                pool.join()
        else:
            for x, y, done_x, done_y, path in tqdm(pixel_coords):
                TileUtils.generate_tile_from_arr(tile, WIDTH, HEIGHT, x, y, done_x, done_y, path, img_format, img_arr=img_arr)

        # Close the image
        src.close()

    @classmethod
    def generate_ultra_large_tiles(cls, tiff_path, tile, WIDTH, HEIGHT, pixel_coords, img_format, mp, date):
        """
            Generates intermediate images for the ultra large image and then tiles the intermediate images.
            Since the intermediate images are created such that they are as close to Pillow's Image pixel size limit
            as possible, and not necessarily aligned with the tiles, one tile may lie between two intermediate images,
            or four intermediate images. 
        """
        # Create the intermediate tiles
        inter_dir, img_width, img_height = TileUtils.img_to_intermediate_images(tiff_path, tile, WIDTH, HEIGHT, date, img_format)
        intermediate_files = [f for f in os.listdir(inter_dir) if f.endswith(img_format)]

        # Get the tiling information for all intermediate tiles
        intermediate_info = TileUtils.getIntermediateTilingInfo(tile, pixel_coords, WIDTH, HEIGHT, img_width, img_height, intermediate_files)

        # Perform the tiling
        TileUtils.tile_intermediates(tile, WIDTH, HEIGHT, inter_dir, intermediate_info, mp, img_format)

    @classmethod
    def getIntermediateTilingInfo(cls, tile, pixel_coords, WIDTH, HEIGHT, img_width, img_height, intermediate_files):
        # sourcery no-metrics
        intermediate_files.sort()

        single_inter_pixel_coords = [] # for the tiles that fit in a single image
        double_inter_pixel_coords = [] # for the tiles in between two images
        quad_inter_pixel_coords = [] # for the tiles in between four images

        # Get required tiling information
        for index,filename in enumerate(intermediate_files):
            inter_metadata = IntermediateMetadata(filename)

            # Get tiling information for tiles in single images (i.e. find if a tile's (x,y) coordinates are included in the intermediate file)
            inter_coords = [(inter_metadata.name, x,y, done_x, done_y, path) for (x,y, done_x, done_y, path) in pixel_coords if x >= inter_metadata.start_x and y >= inter_metadata.start_y and x + tile.width <= inter_metadata.end_x and y + tile.height <= inter_metadata.end_y]
            if inter_coords:
                single_inter_pixel_coords.append(inter_coords)

            # Get tiling information for tiles between two images (tile spans two intermediate images)
            double_coords_raw = [(x,y, done_x, done_y, path) for (x, y, done_x, done_y, path) in pixel_coords if (x < inter_metadata.end_x and x + tile.width > inter_metadata.end_x and y >= inter_metadata.start_y and y + tile.height <= inter_metadata.end_y) or (y < inter_metadata.end_y and y + tile.height > inter_metadata.end_y and x >= inter_metadata.start_x and x + tile.width <= inter_metadata.end_x)]
            if double_coords_raw:
                double_coords_LR = [(filename, intermediate_files[index + math.ceil(HEIGHT / img_height)], x, y, done_x, done_y, path) for (x, y, done_x, done_y, path) in double_coords_raw if x < inter_metadata.end_x and x + tile.width > inter_metadata.end_x]
                double_coords_AB = [(filename, intermediate_files[index + 1], x, y, done_x, done_y, path) for (x, y, done_x, done_y, path) in double_coords_raw if y < inter_metadata.end_y and y + tile.height > inter_metadata.end_y]
                if double_coords_LR:
                    double_inter_pixel_coords.append(double_coords_LR)
                if double_coords_AB:
                    double_inter_pixel_coords.append(double_coords_AB)
            
            # Get tiling information for tiles between four images (tile spans four intermediate images)
            quad_coords = [(filename, intermediate_files[index+1], intermediate_files[index + math.ceil(HEIGHT / img_height)], intermediate_files[index + math.ceil(HEIGHT / img_height) + 1], x, y, done_x, done_y, path) for (x,y,done_x,done_y, path) in pixel_coords if ((not done_x) and (not done_y) and x < inter_metadata.end_x and x + tile.width > inter_metadata.end_x and y < inter_metadata.end_y and y + tile.height > inter_metadata.end_y)]
            if quad_coords:
                quad_inter_pixel_coords.append(quad_coords)
        return single_inter_pixel_coords, double_inter_pixel_coords, quad_inter_pixel_coords
    
    @classmethod
    def tile_intermediates(cls, tile, WIDTH, HEIGHT, inter_dir, intermediate_info, mp, img_format):
        # sourcery no-metrics
        """
            This function orchestrates the appropriate function calls to generate the tiles
            using the intermediate images.

            This function deals with the following cases:
                1. tile lies entirely in an intermediate image
                2. tile lies along the border of two intermediate images
                3. tile lies in the corner of four intermediate images
        """
        print("\tTiling complete images")
        for single_inter_imgs in tqdm(intermediate_info[0]):
            filename = single_inter_imgs[0][0]
            inter_metadata = IntermediateMetadata(filename)

            img_path = os.path.join(inter_dir, filename)
            src = Image.open(img_path)
            img_arr = np.array(src)

            if mp:
                # Create a shared array
                X_shape = img_arr.shape
                X = RawArray('B', X_shape[0] * X_shape[1] * X_shape[2])

                # Wrap shared array as numpy array
                X_np = np.frombuffer(X, dtype='uint8').reshape(X_shape)

                # Copy image to the shared array
                np.copyto(X_np, img_arr)

                # Use multiprocessing to tile the numpy array
                with Pool(processes=NUM_CORES, initializer=init_worker, initargs=(X, X_shape, None, None)) as pool:
                    multi = [pool.apply_async(TileUtils.generate_tile_from_arr, args=(tile, WIDTH, HEIGHT, x, y, done_x, done_y, path, img_format,), kwds={"inter_x":(x - inter_metadata.start_x), "inter_y":(y - inter_metadata.start_y)}) for (filename, x, y, done_x, done_y, path) in single_inter_imgs]
                    f = [p.get() for p in multi]
                    pool.close()
                    pool.join()
            else: 
                for filename, x, y, done_x, done_y, path in single_inter_imgs:
                    TileUtils.generate_tile_from_arr(tile, WIDTH, HEIGHT, x, y, done_x, done_y, path, img_format, inter_x=(x - inter_metadata.start_x), inter_y=(y - inter_metadata.start_y), img_arr=img_arr)

            # Close the image
            src.close()

        print("\tTiling between two images")
        if mp:
            with Pool(processes=NUM_CORES) as pool:
                args = zip(repeat((tile.width, tile.height, inter_dir, img_format)), intermediate_info[1])
                result = list(tqdm(pool.imap(process_doubles_MP, args), total=len(intermediate_info[1])))
        else:
            for double_inter_imgs in tqdm(intermediate_info[1]):
                process_doubles_tuple(tile.width, tile.height, inter_dir, img_format, double_inter_imgs)

        print("\tTiling between four images")
        if mp:
            # Use half as many processes as cores to ensure not running out of available mem and getting stuck
            with Pool(processes=(NUM_CORES // 2)) as pool:
                args = zip(repeat((tile.width, tile.height, inter_dir, img_format)), intermediate_info[2])
                result = list(tqdm(pool.imap(process_quads_MP, args), total=len(intermediate_info[2])))
        else:
            for quad_inter_imgs in tqdm(intermediate_info[2]):
                process_quads_tuple(tile.width, tile.height, inter_dir, img_format, quad_inter_imgs)
        shutil.rmtree(inter_dir)

    @classmethod
    def generate_tile_from_arr(cls, tile, WIDTH, HEIGHT, x, y, done_x, done_y, path, img_format, inter_x = None, inter_y = None, img_arr=None):
        """ 
            Function which actually manipulates the numpy array to create a tile from the original image array 
            If utilizing multiprocessing, this function accesses the shared image array.
        """
        if img_arr is None:
            img_arr = np.frombuffer(arr_dict['X'], dtype="uint8").reshape(arr_dict['X_shape'])

        real_x = x
        real_y = y

        if inter_x != None:
            real_x = inter_x
        if inter_y != None:
            real_y = inter_y

        # Tiling past boundaries 
        if tile.handling == Handling.include_incomplete_tiles and (done_x or done_y):
            incomplete_tile = img_arr[real_y:min(real_y + tile.height, HEIGHT), real_x:min(real_x + tile.width, WIDTH)]
            empty_array = np.zeros((tile.height, tile.height, 3), dtype=np.uint8)
            empty_array[0:incomplete_tile.shape[0], 0:incomplete_tile.shape[1]] = incomplete_tile
            incomplete_img = Image.fromarray(empty_array)
            incomplete_img.save(path + "." + img_format)
        else: # Tiling within boundaries
            tile_array = img_arr[real_y:real_y + tile.height, real_x:real_x + tile.width]
            tile_img = Image.fromarray(tile_array)
            tile_img.save(path + "." + img_format)
        return 1

    @classmethod 
    def generate_tile_between_two_images(cls, t_width, t_height, WIDTH, HEIGHT, x, y, done_x, done_y, inter_x, inter_y, path, img_format, img_arr_left=None, img_arr_right=None):
        if img_arr_left is None:
            img_arr_left = np.frombuffer(arr_dict['X'], dtype="uint8").reshape(arr_dict['X_shape'])
        if img_arr_right is None:
            img_arr_right = np.frombuffer(arr_dict['Y'], dtype="uint8").reshape(arr_dict['Y_shape'])

        leftover_x = t_width - (WIDTH - inter_x)
        leftover_y = t_height - (HEIGHT - inter_y)

        left_chunk = img_arr_left[inter_y:min(inter_y + t_height, HEIGHT), inter_x:min(inter_x + t_width, WIDTH)]

        if leftover_x > 0:
            right_chunk = img_arr_right[inter_y:inter_y + t_height, 0:leftover_x]
        elif leftover_y > 0:
            right_chunk = img_arr_right[0:leftover_y, inter_x:inter_x + t_width]

        empty_array = np.zeros((t_height, t_height, 3), dtype=np.uint8)
        empty_array[0:left_chunk.shape[0], 0:left_chunk.shape[1]] = left_chunk

        if leftover_x > 0:
            empty_array[0:right_chunk.shape[0], left_chunk.shape[1]:left_chunk.shape[1]+right_chunk.shape[1]] = right_chunk
        elif leftover_y > 0:
            empty_array[left_chunk.shape[0]:left_chunk.shape[0]+right_chunk.shape[0], 0:right_chunk.shape[1]] = right_chunk
        if leftover_x > 0 or leftover_y > 0:
            complete_img = Image.fromarray(empty_array)
            complete_img.save(path + "." + img_format)

    @classmethod 
    def generate_tile_between_four_images(cls, t_width, t_height, img_arr_TL, img_arr_TR, img_arr_BL,img_arr_BR, WIDTH, HEIGHT, x, y, done_x, done_y, inter_x, inter_y, path, img_format):
        leftover_x = t_width - (WIDTH - inter_x)
        leftover_y = t_height - (HEIGHT - inter_y)

        top_left_chunk = img_arr_TL[inter_y:min(inter_y + t_height, HEIGHT), inter_x:min(inter_x + t_width, WIDTH)]
        top_right_chunk = img_arr_TR[inter_y:inter_y + t_height, 0:leftover_x]
        bot_left_chunk = img_arr_BL[0:leftover_y, inter_x:inter_x + t_height]
        bot_right_chunk = img_arr_BR[0:leftover_y, 0:leftover_x]
    
        empty_array = np.zeros((t_height, t_height, 3), dtype=np.uint8)
        empty_array[0:top_left_chunk.shape[0], 0:top_left_chunk.shape[1]] = top_left_chunk
        empty_array[0:top_right_chunk.shape[0], top_left_chunk.shape[1]:top_left_chunk.shape[1]+top_right_chunk.shape[1]] = top_right_chunk
        empty_array[top_left_chunk.shape[0]:top_left_chunk.shape[0]+bot_left_chunk.shape[0], 0:bot_left_chunk.shape[1]] = bot_left_chunk
        empty_array[top_left_chunk.shape[0]:top_left_chunk.shape[0]+bot_right_chunk.shape[0], top_left_chunk.shape[1]:top_left_chunk.shape[1]+bot_right_chunk.shape[1]] = bot_right_chunk
        complete_img = Image.fromarray(empty_array)
        complete_img.save(path + "." + img_format)

    @classmethod
    def generate_tile_directories(cls, metadata, tile, x, y, geotran_d, tile_date_path):
        output_filename, region = TileUtils.generate_tile_name_with_coordinates(metadata.date, tile, x, y, geotran_d)
        output_path = tile_date_path + region.lat_lon_to_modis() + '/'
        if not os.path.exists(output_path):
            try:
                os.mkdir(output_path)
            except FileExistsError:
                """ Ignore exception when parallel processes attempty to create the same directory """
        return os.path.join(output_path, output_filename)
        
    @classmethod
    def generate_tile_name_with_coordinates(cls, date, tile, x, y, geotran_d):
        tr_x = x * geotran_d['x_size'] + geotran_d['x_min'] 
        tr_y = (y + tile.height) * geotran_d['y_size'] + geotran_d['y_min']
        bl_x = (x + tile.width) * geotran_d['x_size'] + geotran_d['x_min']
        bl_y = y * geotran_d['y_size'] + geotran_d['y_min']
        filename = "{d}_{by},{bx},{ty},{tx}".format(d=date, ty=str(f'{round(bl_y, 4):08}'), tx=str(f'{round(bl_x, 4):09}'), by=str(f'{round(tr_y, 4):08}'), bx=str(f'{round(tr_x, 4):09}'))
        return filename, Rectangle(Coordinate((bl_y, bl_x)), Coordinate((tr_y, tr_x)))

    @classmethod
    def img_to_intermediate_images(cls, tiff_path, tile, width, height, date, img_format):
        output_dir = os.path.join(os.path.dirname(tiff_path), 'inter_{}x{}_{}'.format(width, height, date))
        if not os.path.isdir(output_dir):
            os.mkdir(output_dir)

        max_img_width = min(width, MAX_INTERMEDIATE_LENGTH)
        max_img_height = min(height, MAX_INTERMEDIATE_LENGTH)
        
        # Find largest possible intermediate image sizes
        while ((max_img_width != width) and (((width / max_img_width) % 1) * max_img_width  < tile.width)):
            max_img_width -= 256

        while ((max_img_height != height) and (((height / max_img_height)  % 1) * max_img_height < tile.height)):
            max_img_height -= 256

        original_max_img_width = max_img_width   # Store these values in another variable so they can be returned
        original_max_img_height = max_img_height  
        
        # LOOP THOUGH AND GET THE DATA TO GENERATE THE INTERMEDIATE TILES
        width_current = 0
        done_width = False
        index = 0
        intermediate_data = []
        while width_current < width and not done_width:
            if width - width_current < max_img_width:
                max_img_width = width - width_current
                done_width = True
            height_current = 0
            done_height = False
            max_img_height = original_max_img_height
            while height_current < height and not done_height:
                if height - height_current < max_img_height: 
                    max_img_height = height - height_current
                    done_height = True
                intermediate_data.append((width_current, height_current, max_img_width, max_img_height, index))
                height_current += max_img_height
                index += 1
            width_current += max_img_width
        print("\tCreating intermediate images")
        for (width_current, height_current, width_length, height_length, index) in tqdm(intermediate_data):
            TileUtils.generate_intermediate_image(output_dir, width_current, height_current, width_length, height_length, tiff_path, index, img_format)
        return output_dir, original_max_img_width, original_max_img_height

    @classmethod 
    def generate_intermediate_image(cls, output_dir, width_current, height_current, width_length, height_length, tiff_path, index, img_format):
        output_path = os.path.join(output_dir, "{}_{}_{}_{}_{}".format(str(index).zfill(5), width_current, height_current, width_current + width_length, height_current + height_length))
        output_log_path = os.path.join(output_dir, "logs.txt")
        filename = "{}.{}".format(output_path, img_format)
        if not os.path.isfile(filename):
            command = "gdal_translate -of {of} -srcwin --config GDAL_CACHEMAX 12000 --config GDAL_PAM_ENABLED NO {x}, {y}, {t_width}, {t_height} {tif_path} {fname}".format(of=img_format.upper(), x=str(width_current), y=str(height_current), t_width=width_length, t_height=height_length, tif_path=tiff_path, fname=filename)
            os.system("{} > {}".format(command, output_log_path))
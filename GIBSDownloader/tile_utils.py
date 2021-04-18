import argparse
import os
import math
import warnings
import shutil
import multiprocessing
from multiprocessing.pool import ThreadPool as Pool

import numpy as np
from matplotlib import pyplot as plt
from osgeo import gdal
from PIL import Image
from tqdm import tqdm 
from bs4 import BeautifulSoup as bs

from GIBSDownloader.tile import Tile
from GIBSDownloader.handling import Handling
from GIBSDownloader.file_metadata import TiffMetadata, IntermediateMetadata
from GIBSDownloader.coordinate_utils import Coordinate, Rectangle

warnings.simplefilter('ignore', Image.DecompressionBombWarning)

MAX_INTERMEDIATE_LENGTH = int(math.sqrt(2 * Image.MAX_IMAGE_PIXELS)) # Maximum width and height for an intermediate tile to guarantee num pixels less than PIL's max

class TileUtils():
    @classmethod
    def getGeoTransform(cls, path):
        content = []
        # Read the XML file
        with open(path, "r") as f:
            # Read each line in the file, readlines() returns a list of lines
            content = f.readlines()
            # Combine the lines in the list into a string
            content = "".join(content)
            bs_content = bs(content, "lxml")
            values = str(bs_content.find("geotransform")).replace("<geotransform> ", "").replace("</geotransform>","").split(",")
        return float(values[0]),float(values[1]),float(values[3]),float(values[5])
        
    @classmethod
    def getTilingSplitCoords(cls, tile, WIDTH, HEIGHT):
        x_step, y_step = int(tile.width * (1 - tile.overlap)), int(tile.height * (1 - tile.overlap))
        x = 0 
        done_x = False

        # Check for valid tiling
        if (tile.width > WIDTH or tile.height > HEIGHT):
            raise argparse.ArgumentTypeError("Tiling dimensions greater than image dimensions")

        # Calculate the number of tiles to be generated
        if tile.handling == Handling.discard_incomplete_tiles:
            num_iterations = (WIDTH - tile.width * tile.overlap) // (tile.width * (1 - tile.overlap)) * (HEIGHT - tile.height * tile.overlap) // (tile.height * (1 -  tile.overlap))
        else:
            num_iterations = math.ceil((WIDTH - tile.width * tile.overlap) / (tile.width * (1 - tile.overlap))) * math.ceil((HEIGHT - tile.height * tile.overlap) / (tile.height * (1 -  tile.overlap)))
        
        pixel_coords = []

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
                    
                pixel_coords.append((x, y, done_x, done_y))

                y += y_step
            x += x_step
        return pixel_coords

    @classmethod
    def img_to_tiles(cls, tiff_path, region, res, tile, tile_date_path):
        # Get metadata from original image
        metadata = TiffMetadata(tiff_path)

        WIDTH, HEIGHT = region.calculate_width_height(res)
        ultra_large = False
        if WIDTH * HEIGHT > 2 * Image.MAX_IMAGE_PIXELS:
            ultra_large = True

        # Use the following to get the coordinates of each tile
        x_min, x_size, y_min, y_size = TileUtils.getGeoTransform(tiff_path + ".aux.xml")
       
        # Find the pixel coordinate extents of each tile to be generated
        pixel_coords = TileUtils.getTilingSplitCoords(tile, WIDTH, HEIGHT)

        if ultra_large: 
            # Create the intermediate tiles
            inter_dir, img_width, img_height = TileUtils.img_to_intermediate_images(tiff_path, tile, WIDTH, HEIGHT, metadata.date)

            # Add each coordinate to its proper list
            intermediate_files = [f for f in os.listdir(inter_dir) if f.endswith('jpeg')]
            intermediate_files.sort()

            single_inter_pixel_coords = [] # for the tiles that fit in a single image
            double_inter_pixel_coords = [] # for the tiles which require two images
            quad_inter_pixel_coords = [] # for the tiles which require four images

            # Get tiling information for single images
            for filename in intermediate_files:
                inter_metadata = IntermediateMetadata(filename)
                inter_coords = [(inter_metadata.name, x,y, done_x, done_y) for (x,y, done_x, done_y) in pixel_coords if x >= inter_metadata.start_x and y >= inter_metadata.start_y and x + tile.width <= inter_metadata.end_x and y + tile.height <= inter_metadata.end_y]
                if inter_coords:
                    single_inter_pixel_coords.append(inter_coords)
            
            # Get tiling information for between two images
            for index, filename in enumerate(intermediate_files):
                inter_metadata = IntermediateMetadata(filename)
                double_coords_raw = [(x,y, done_x, done_y) for (x,y,done_x,done_y) in pixel_coords if (x < inter_metadata.end_x and x + tile.width > inter_metadata.end_x and y >= inter_metadata.start_y and y + tile.height <= inter_metadata.end_y) or (y < inter_metadata.end_y and y + tile.height > inter_metadata.end_y and x >= inter_metadata.start_x and x + tile.width <= inter_metadata.end_x)]

                if double_coords_raw:
                    double_coords_LR = [(filename, intermediate_files[index + math.ceil(HEIGHT / img_height)], x, y, done_x, done_y) for (x, y, done_x, done_y) in double_coords_raw if x < inter_metadata.end_x and x + tile.width > inter_metadata.end_x]
                    double_coords_AB = [(filename, intermediate_files[index + 1], x, y, done_x, done_y) for (x, y, done_x, done_y) in double_coords_raw if y < inter_metadata.end_y and y + tile.height > inter_metadata.end_y]
                    if double_coords_LR:
                        double_inter_pixel_coords.append(double_coords_LR)
                    if double_coords_AB:
                        double_inter_pixel_coords.append(double_coords_AB)

            # Get tiling information for between four images
            for index, filename in enumerate(intermediate_files):
                inter_metadata = IntermediateMetadata(filename)
                quad_coords = [(filename, intermediate_files[index+1], intermediate_files[index + math.ceil(HEIGHT / img_height)], intermediate_files[index + math.ceil(HEIGHT / img_height) + 1], x, y, done_x, done_y) for (x,y,done_x,done_y) in pixel_coords if ((not done_x) and (not done_y) and x < inter_metadata.end_x and x + tile.width > inter_metadata.end_x and y < inter_metadata.end_y and y + tile.height > inter_metadata.end_y)]
                if quad_coords:
                    quad_inter_pixel_coords.append(quad_coords)
        
            print("Tiling intermediate images...")

            # Tile the complete images
            for single_inter_imgs in tqdm(single_inter_pixel_coords):
                filename = single_inter_imgs[0][0]
                inter_metadata = IntermediateMetadata(filename)

                img_path = os.path.join(inter_dir, filename)
                src = Image.open(img_path)
                img_arr = np.array(src)

                for i, (filename, x, y, done_x, done_y) in enumerate(single_inter_imgs):
                    TileUtils.generate_tile(tile, img_arr, tile_date_path, metadata, inter_metadata.end_x - inter_metadata.start_x, inter_metadata.end_y - inter_metadata.start_y, x_min, x_size, y_min, y_size, x, y, done_x, done_y, inter_x=(x - inter_metadata.start_x), inter_y=(y - inter_metadata.start_y))

                """
                #Use multithreading to tile the numpy array
                num_cores = multiprocessing.cpu_count()
                print("Generating {} tiles using {} threads...".format(len(single_inter_imgs), num_cores), end="")
                pool = Pool(num_cores)

                for i, (filename, x, y, done_x, done_y) in enumerate(single_inter_imgs):
                    pool.apply_async(TileUtils.generate_tile, args=(tile, img_arr, tile_date_path, metadata, inter_metadata.end_x - inter_metadata.start_x, inter_metadata.end_y - inter_metadata.start_y, x_min, x_size, y_min, y_size, x, y, done_x, done_y,), kwds={"inter_x":(x - inter_metadata.start_x), "inter_y":(y - inter_metadata.start_y)})
                pool.close()
                pool.join()
                """
            
            # Tile in between two images
            for double_inter_imgs in tqdm(double_inter_pixel_coords):
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

                for i, (f1, f2, x, y, done_x, done_y) in enumerate(double_inter_imgs):
                    TileUtils.generate_tile_between_two_images(tile, img_arr_left, img_arr_right, tile_date_path, metadata, inter_metadata_left.end_x - inter_metadata_left.start_x, inter_metadata_left.end_y - inter_metadata_left.start_y, x_min, x_size, y_min, y_size, x, y, done_x, done_y, x - inter_metadata_left.start_x, y - inter_metadata_left.start_y)

                
                #Use multithreading to tile the numpy array
                """
                num_cores = multiprocessing.cpu_count()
                print("Generating {} tiles using {} threads...".format(len(double_inter_imgs), num_cores), end="")
                pool = Pool(num_cores)
                for i, (f1, f2, x, y, done_x, done_y) in enumerate(double_inter_imgs):
                    pool.apply_async(TileUtils.generate_tile_between_two_images, args=(tile, img_arr_left, img_arr_right, tile_date_path, metadata, inter_metadata_left.end_x - inter_metadata_left.start_x, inter_metadata_left.end_y - inter_metadata_left.start_y, x_min, x_size, y_min, y_size, x, y, done_x, done_y, x - inter_metadata_left.start_x, y - inter_metadata_left.start_y))
                pool.close()
                pool.join()
                """
            
            # Tile in between four images  
            for quad_inter_imgs in tqdm(quad_inter_pixel_coords):
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

                for i, (f1, f2, f3, f4, x, y, done_x, done_y) in enumerate(quad_inter_imgs):
                    TileUtils.generate_tile_between_four_images(tile, img_arr_TL, img_arr_TR, img_arr_BL, img_arr_BR, tile_date_path, metadata, inter_metadata_TL.end_x - inter_metadata_TL.start_x, inter_metadata_TL.end_y - inter_metadata_TL.start_y, x_min, x_size, y_min, y_size, x, y, done_x, done_y, x - inter_metadata_TL.start_x, y - inter_metadata_TL.start_y)
               
                #Use multithreading to tile the numpy array
                """
                num_cores = multiprocessing.cpu_count()
                print("Generating {} tiles using {} threads...".format(len(quad_inter_imgs), num_cores), end="")
                pool = Pool(num_cores)

                for i, (f1, f2, f3, f4, x, y, done_x, done_y) in enumerate(quad_inter_imgs):
                    pool.apply_async(TileUtils.generate_tile_between_four_images, args=(tile, img_arr_TL, img_arr_TR, img_arr_BL, img_arr_BR, tile_date_path, metadata, inter_metadata.end_x - inter_metadata.start_x, inter_metadata.end_y - inter_metadata.start_y, x_min, x_size, y_min, y_size, x, y, done_x, done_y, x - inter_metadata.start_x, y - inter_metadata.start_y))
                pool.close()
                pool.join()
                """
            print("Finished tiling all the intermediates")
            shutil.rmtree(inter_dir)
        else: 
            # Open GeoTiff as numpy array in order to tile from the array
            src = Image.open(tiff_path)
            img_arr = np.array(src)

            for i, (x, y, done_x, done_y) in enumerate(pixel_coords):
                TileUtils.generate_tile(tile, img_arr, tile_date_path, metadata, WIDTH, HEIGHT, x_min, x_size, y_min, y_size, x, y, done_x, done_y)

            #Use multithreading to tile the numpy array
            """
            num_cores = multiprocessing.cpu_count()
            print("Generating {} tiles using {} threads...".format(len(pixel_coords), num_cores), end="")
            pool = Pool(1)
            for i, (x, y, done_x, done_y) in enumerate(pixel_coords):
                pool.apply_async(TileUtils.generate_tile, args=(tile, img_arr, tile_date_path, metadata, WIDTH, HEIGHT, x_min, x_size, y_min, y_size, x, y, done_x, done_y))
            
            pool.close()
            pool.join()
            """
            print("done!")

    @classmethod
    def generate_tile(cls, tile, img_arr, tile_date_path, metadata, WIDTH, HEIGHT, x_min, x_size, y_min, y_size, x, y, done_x, done_y, inter_x = None, inter_y = None):
        # Find which MODIS grid location the current tile fits into
        output_filename, region = TileUtils.generate_tile_name_with_coordinates(metadata.date, x, x_min, x_size, y, y_min, y_size, tile)
        output_path = tile_date_path + region.lat_lon_to_modis() + '/'
        if not os.path.exists(output_path):
            os.mkdir(output_path)

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
            incomplete_img.save(output_path + output_filename + ".jpeg")
        else: # Tiling within boundaries
            tile_array = img_arr[real_y:real_y+tile.height, real_x:real_x+tile.width]
            tile_img = Image.fromarray(tile_array)
            tile_img.save(output_path + output_filename + ".jpeg")      

    @classmethod 
    def generate_tile_between_two_images(cls, tile, img_arr_left, img_arr_right, tile_date_path, metadata, WIDTH, HEIGHT, x_min, x_size, y_min, y_size, x, y, done_x, done_y, inter_x, inter_y):
        # Find which MODIS grid location the current tile fits into
        output_filename, region = TileUtils.generate_tile_name_with_coordinates(metadata.date, x, x_min, x_size, y, y_min, y_size, tile)
        output_path = tile_date_path + region.lat_lon_to_modis() + '/'
        if not os.path.exists(output_path):
            os.mkdir(output_path)

        leftover_x = tile.width - (WIDTH - inter_x)
        leftover_y = tile.height - (HEIGHT - inter_y)

        left_chunk = img_arr_left[inter_y:min(inter_y + tile.height, HEIGHT), inter_x:min(inter_x + tile.width, WIDTH)]

        if leftover_x > 0:
            right_chunk = img_arr_right[inter_y:inter_y + tile.height, 0:leftover_x]
        elif leftover_y > 0:
            right_chunk = img_arr_right[0:leftover_y, inter_x:inter_x + tile.width]

        empty_array = np.zeros((tile.height, tile.height, 3), dtype=np.uint8)
        empty_array[0:left_chunk.shape[0], 0:left_chunk.shape[1]] = left_chunk

        if leftover_x > 0:
            empty_array[0:right_chunk.shape[0], left_chunk.shape[1]:left_chunk.shape[1]+right_chunk.shape[1]] = right_chunk
        elif leftover_y > 0:
            empty_array[left_chunk.shape[0]:left_chunk.shape[0]+right_chunk.shape[0], 0:right_chunk.shape[1]] = right_chunk
        if leftover_x > 0 or leftover_y > 0:
            complete_img = Image.fromarray(empty_array)
            complete_img.save(output_path + output_filename + ".jpeg")

    @classmethod 
    def generate_tile_between_four_images(cls, tile, img_arr_TL, img_arr_TR, img_arr_BL,img_arr_BR, tile_date_path, metadata, WIDTH, HEIGHT, x_min, x_size, y_min, y_size, x, y, done_x, done_y, inter_x, inter_y):
        # Find which MODIS grid location the current tile fits into
        output_filename, region = TileUtils.generate_tile_name_with_coordinates(metadata.date, x, x_min, x_size, y, y_min, y_size, tile)
        output_path = tile_date_path + region.lat_lon_to_modis() + '/'
        if not os.path.exists(output_path):
            os.mkdir(output_path)

        leftover_x = tile.width - (WIDTH - inter_x)
        leftover_y = tile.height - (HEIGHT - inter_y)

        top_left_chunk = img_arr_TL[inter_y:min(inter_y + tile.height, HEIGHT), inter_x:min(inter_x + tile.width, WIDTH)]
        top_right_chunk = img_arr_TR[inter_y:inter_y + tile.height, 0:leftover_x]
        bot_left_chunk = img_arr_BL[0:leftover_y, inter_x:inter_x + tile.height]
        bot_right_chunk = img_arr_BR[0:leftover_y, 0:leftover_x]
    
        empty_array = np.zeros((tile.height, tile.height, 3), dtype=np.uint8)
        empty_array[0:top_left_chunk.shape[0], 0:top_left_chunk.shape[1]] = top_left_chunk
        empty_array[0:top_right_chunk.shape[0], top_left_chunk.shape[1]:top_left_chunk.shape[1]+top_right_chunk.shape[1]] = top_right_chunk
        empty_array[top_left_chunk.shape[0]:top_left_chunk.shape[0]+bot_left_chunk.shape[0], 0:bot_left_chunk.shape[1]] = bot_left_chunk
        empty_array[top_left_chunk.shape[0]:top_left_chunk.shape[0]+bot_right_chunk.shape[0], top_left_chunk.shape[1]:top_left_chunk.shape[1]+bot_right_chunk.shape[1]] = bot_right_chunk
        complete_img = Image.fromarray(empty_array)
        complete_img.save(output_path + output_filename + ".jpeg")

    @classmethod
    def generate_tile_name_with_coordinates(cls, date, x, x_min, x_size, y, y_min, y_size, tile):
        tr_x = x * x_size + x_min 
        tr_y = (y + tile.height) * y_size + y_min 
        bl_x = (x + tile.width) * x_size + x_min
        bl_y = y * y_size + y_min
        filename = "{d}_{by},{bx},{ty},{tx}".format(d=date, ty=str(f'{round(bl_y, 4):08}'), tx=str(f'{round(bl_x, 4):09}'), by=str(f'{round(tr_y, 4):08}'), bx=str(f'{round(tr_x, 4):09}'))
        return filename, Rectangle(Coordinate((bl_y, bl_x)), Coordinate((tr_y, tr_x)))

    @classmethod
    def img_to_intermediate_images(cls, tiff_path, tile, width, height, date):
        output_dir = os.path.join(os.path.dirname(tiff_path), 'inter_{}'.format(date))
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
        
        print(width, height, max_img_width, max_img_height, width / max_img_width, height /max_img_height )
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
        
        # Utilize multithreading to generate the intermediate tiles
        num_cores = multiprocessing.cpu_count()
        pool = Pool(num_cores)
        
        print("Generating {} intermediate images using {} threads".format(len(intermediate_data), num_cores))
        for (width_current, height_current, width_length, height_length, index) in intermediate_data:
            pool.apply_async(TileUtils.generate_intermediate_image, args=(output_dir, width_current, height_current, width_length, height_length, tiff_path, index))
        
        pool.close()
        pool.join()

        return output_dir, original_max_img_width, original_max_img_height

    @classmethod 
    def generate_intermediate_image(cls, output_dir, width_current, height_current, width_length, height_length, tiff_path, index):
        output_path = os.path.join(output_dir, "{}_{}_{}_{}_{}".format(str(index).zfill(5), width_current, height_current, width_current + width_length, height_current + height_length))
        command = "gdal_translate -of JPEG -srcwin --config GDAL_PAM_ENABLED NO {x}, {y}, {t_width}, {t_height} {tif_path} {out_path}.jpeg".format(x=str(width_current), y=str(height_current), t_width=width_length, t_height=height_length, tif_path=tiff_path, out_path=output_path)
        os.system(command)
        
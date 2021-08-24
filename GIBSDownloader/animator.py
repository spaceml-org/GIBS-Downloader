import os
import warnings

import cv2
from cv2 import cv2
from PIL import Image

from GIBSDownloader.tiff_downloader import TiffDownloader

warnings.simplefilter('ignore', Image.DecompressionBombWarning)

class Animator():
    @classmethod
    def format_images(cls, originals_path, region, dates, video_path, xml_path, name, res, img_format):
        """
        Formats downloaded images to prepare for video generation.

        Some downloaded regions are very large, resulting in very large images.
        Therefore, we must resize the images while maintaining the same aspect
        ratio. In these cases, we download the images again with height set to
        1080 and a width which maintains the ratio.

        After this function executes, the `video_path` subdirectory will be
        populated with the images prepared to be joined into the video.

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
        width, height = region.calculate_width_height(res)
        if width * height > 2 * Image.MAX_IMAGE_PIXELS:
            print("The downloaded images are too large to generate a video. Redownloading the region with smaller image dimensions")
            ratio = width / height
            resized_height = 1080
            resized_width = resized_height * ratio
            for date in dates:
                frame_name = TiffDownloader.generate_download_filename(video_path, name, date)
                TiffDownloader.download_area_tiff(region, date, xml_path, frame_name, name, res, img_format, width=resized_width, height=resized_height)
            
        else:
            images = [img for img in os.listdir(originals_path) if img.endswith(img_format)]
            for image in images:
                frame_output = os.path.splitext(os.path.join(video_path, image))[0] + "." + img_format
                if not os.path.exists(frame_output):
                    im = Image.open(os.path.join(originals_path, image))
                    im.thumbnail(im.size)
                    im.save(frame_output, img_format.upper(), quality=100)
                    im2 = Image.open(frame_output)
                    size = im2.size
                    if min(size[0], size[1]) > 1080:
                        ratio = 1080 / min(im2.size[0], im2.size[1])
                        reduced_size = int(size[0] * ratio), int(size[1] * ratio)
                        im_resized = im2.resize(reduced_size, Image.ANTIALIAS)
                        im_resized.save(frame_output, img_format.upper(), quality=100)

    @classmethod
    def create_video(cls, video_path, img_format):
        """ Joins images in video_path in chronological order into a movie"""
        images = [img for img in os.listdir(video_path) if img.endswith("." + img_format)]
        images.sort()
        frame = cv2.imread(os.path.join(video_path, images[0]))
        height, width, layers = frame.shape
        video = cv2.VideoWriter(os.path.join(video_path, 'animation.avi'),
        cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'), 15, (width, height))
        for image in images:
            img_path = os.path.join(video_path, image)
            video.write(cv2.imread(img_path))
            os.remove(img_path)
        video.release()
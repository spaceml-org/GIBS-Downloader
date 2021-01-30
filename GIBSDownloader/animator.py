import os
import warnings

import cv2
from PIL import Image

from GIBSDownloader.tiff_downloader import TiffDownloader

warnings.simplefilter('ignore', Image.DecompressionBombWarning)

class Animator():
    @classmethod
    def format_images(cls, tif_path, region, dates, video_path, xml_path, output_dir, product):
        width, height = region.calculate_width_height(.25)
        if width * height > 2 * Image.MAX_IMAGE_PIXELS:
            print("The downloaded images are too large to generate a video. Redownloading the region with smaller image dimensions")
            ratio = width / height
            resized_height = 1080
            resized_width = resized_height * ratio
            for date in dates:
                TiffDownloader.download_area_tiff(region, date, video_path, xml_path, output_dir, product, width=resized_width, height=resized_height, out_frmt="JPEG")
        else:
            images = [img for img in os.listdir(tif_path) if img.endswith(".tif")]
            for image in images:
                frame_output = os.path.splitext(os.path.join(video_path, image))[0] + ".jpeg"
                if not os.path.exists(frame_output):
                    im = Image.open(os.path.join(video_path, image))
                    im.thumbnail(im.size)
                    im.save(frame_output, "JPEG", quality=100)
                    im2 = Image.open(frame_output)
                    size = im2.size
                    if min(size[0], size[1]) > 1080:
                        ratio = 1080 / min(im2.size[0], im2.size[1])
                        reduced_size = int(size[0] * ratio), int(size[1] * ratio)
                        im_resized = im2.resize(reduced_size, Image.ANTIALIAS)
                        im_resized.save(frame_output, "JPEG", quality=100)

    @classmethod
    def create_video(cls, video_path):
        images = [img for img in os.listdir(video_path) if img.endswith(".jpeg")]
        images.sort()
        frame = cv2.imread(os.path.join(video_path, images[0]))
        height, width, layers = frame.shape
        video = cv2.VideoWriter('./output_video.avi',
        cv2.VideoWriter_fourcc('M', 'J', 'P', 'G'), 24, (width, height))
        for image in images:
            img_path = os.path.join(video_path, image)
            video.write(cv2.imread(img_path))
            os.remove(img_path)
        video.release()
        

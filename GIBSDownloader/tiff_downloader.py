import os
from datetime import date, timedelta

from GIBSDownloader.product import Product
from GIBSDownloader.coordinate_utils import Rectangle, Coordinate

import rasterio
from rasterio.transform import from_bounds


class TiffDownloader():

    @classmethod
    def generate_download_filename(cls, output, name, date):
        return "{}{}_{}".format(output, name, date)

    @classmethod
    def download_area_tiff(cls, region, date, xml_path, filename, name, res, img_format, width=None, height=None):

        if width == None and height == None:
            width, height = region.calculate_width_height(res)

        xml_filename = TiffDownloader.generate_xml(xml_path, name, date)

        with rasterio.open(xml_filename) as src:
            wind = src.window(
                region.bl_coords.x,
                region.bl_coords.y,
                region.tr_coords.x,
                region.tr_coords.y,
                precision=21
            )
            profile = src.profile
            profile["driver"] = img_format
            profile["width"] = width
            profile["height"] = height
            if src.crs is not None:
                profile["transform"] = from_bounds(
                    region.bl_coords.x,
                    region.bl_coords.y,
                    region.tr_coords.x,
                    region.tr_coords.y,
                    width,
                    height,
                )

            with rasterio.open(filename, "w", **profile) as dst_src:
                dst_src.write(
                    src.read(window=wind, out_shape=(src.count, height, width))
                )

    @classmethod
    def get_dates_range(cls, start_date, end_date):
        start_components = start_date.split('-')
        end_components = end_date.split('-')

        d1 = date(int(start_components[0]), int(start_components[1]), int(start_components[2]))
        d2 = date(int(end_components[0]), int(end_components[1]), int(end_components[2]))

        dates = [d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)]
        return dates

    @classmethod
    def generate_xml(cls, xml_path, name, date):
        xml_base = '<GDAL_WMS><Service name="TiledWMS"><ServerUrl>https://gibs.earthdata.nasa.gov/twms/epsg4326/best/twms.cgi?'
        xml_end = '</ServerUrl><TiledGroupName>{name} tileset</TiledGroupName><Change key="${{time}}">{date}</Change></Service></GDAL_WMS>'.format(name=name,date=date)
        xml_content = xml_base + xml_end

        xml_filename = '{}{}.xml'.format(xml_path, date)

        with open(xml_filename, 'w') as xml_file:
            xml_file.write(xml_content)
        return xml_filename



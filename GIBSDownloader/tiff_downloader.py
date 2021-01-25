import os
from datetime import date, timedelta

from GIBSDownloader.product import Product
from GIBSDownloader.coordinate_utils import Rectangle, Coordinate

class TiffDownloader():
    @classmethod
    def download_area_tiff(cls, region, date, download_path, xml_path, output, product):
        """
        region: rectangular region to be downloaded
        date: YYYY-MM-DD
        output: path/to/filename (do not specify extension)
        returns tuple with dowloaded width and height
        """

        width, height = region.calculate_width_height(0.25)
        lon_lat = "{l_x} {upper_y} {r_x} {lower_y}".format(l_x=region.bl_coords.x, upper_y=region.tr_coords.y, r_x=region.tr_coords.x, lower_y=region.bl_coords.y)

        xml_filename = TiffDownloader.generate_xml(xml_path, product, date)
        filename = "{}{}_{}.tif".format(output, str(product), date)
        command = "gdal_translate -of GTiff -outsize {w} {h} -projwin {ll} {xml} {f}".format(w=width, h=height, ll=lon_lat, xml=xml_filename, f=filename)
        
        os.system(command)
        return filename

    @classmethod
    def get_dates_range(cls, start_date, end_date):
        start_components = start_date.split('-')
        end_components = end_date.split('-')

        d1 = date(int(start_components[0]), int(start_components[1]), int(start_components[2]))
        d2 = date(int(end_components[0]), int(end_components[1]), int(end_components[2]))

        dates = [d1 + timedelta(days=x) for x in range((d2 - d1).days + 1)]
        return dates
    
    @classmethod
    def generate_xml(cls, xml_path, product, date):
        xml_base = "<GDAL_WMS><Service name=\"TMS\"><ServerUrl>https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/{prod}/default/{d}/250m/".format(prod=product.get_long_name(), d=date)
        xml_end = "${z}/${y}/${x}.jpg</ServerUrl></Service><DataWindow><UpperLeftX>-180.0</UpperLeftX><UpperLeftY>90</UpperLeftY><LowerRightX>396.0</LowerRightX><LowerRightY>-198</LowerRightY><TileLevel>8</TileLevel><TileCountX>2</TileCountX><TileCountY>1</TileCountY><YOrigin>top</YOrigin></DataWindow><Projection>EPSG:4326</Projection><BlockSizeX>512</BlockSizeX><BlockSizeY>512</BlockSizeY><BandsCount>3</BandsCount></GDAL_WMS>"
        xml_content = xml_base + xml_end

        xml_filename = '{}{}.xml'.format(xml_path, date)

        with open(xml_filename, 'w') as xml_file:
            xml_file.write(xml_content)
        return xml_filename

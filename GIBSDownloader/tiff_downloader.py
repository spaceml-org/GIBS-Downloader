import os
from GIBSDownloader.product import Product
from GIBSDownloader.coordinate_utils import Rectangle, Coordinate

class TiffDownloader():
    @classmethod
    def download_area_tiff(cls, region, date, output, product):
        """
        region: rectangular region to be downloaded
        date: YYYY-MM-DD
        output: path/to/filename (do not specify extension)
        returns tuple with dowloaded width and height
        """

        width, height = region.calculate_width_height(0.25)
        lon_lat = "{l_x} {upper_y} {r_x} {lower_y}".format(l_x=region.bl_coords.x, upper_y=region.tr_coords.y, r_x=region.tr_coords.x, lower_y=region.bl_coords.y)

        base = "gdal_translate -of GTiff -outsize {w} {h} -projwin {ll} '<GDAL_WMS><Service name=\"TMS\"><ServerUrl>https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/{prod}/default/{d}/250m/".format(w=width, h=height, ll=lon_lat, prod=product.get_long_name(), d=date)
        end = "${z}/${y}/${x}.jpg</ServerUrl></Service><DataWindow><UpperLeftX>-180.0</UpperLeftX><UpperLeftY>90</UpperLeftY><LowerRightX>396.0</LowerRightX><LowerRightY>-198</LowerRightY><TileLevel>8</TileLevel><TileCountX>2</TileCountX><TileCountY>1</TileCountY><YOrigin>top</YOrigin></DataWindow><Projection>EPSG:4326</Projection><BlockSizeX>512</BlockSizeX><BlockSizeY>512</BlockSizeY><BandsCount>3</BandsCount></GDAL_WMS>' "
        filename = "{}{}_{}.tif".format(output, str(product), date)
        command = base + end + filename
        os.system(command)
        return filename
import pathlib
import sys

import xml.etree.ElementTree as ET
import urllib.request

import pandas as pd

class DatasetSearcher():
    @classmethod
    def getProductInfo(cls, name):
        # XML to parse
        url = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/1.0.0/WMTSCapabilities.xml"

        # Read the xml as a file
        response = urllib.request.urlopen(url).read()
        root = ET.fromstring(response)

        # Parse xml to create a list of products
        imagery_prods = []
        count = sum(1 for _ in root[3])
        for i in range(count):
            for child in root[3][i]:
                if 'Identifier' in str(child):
                    product_name = child.text
                if 'Format' in str(child):
                    img_format = child.text.replace('image/',"")
                if 'TileMatrixSetLink' in str(child):
                    if 'TileMatrixSet' in str(child[0]):
                        img_res = child[0].text
            imagery_prods.append([product_name,img_res,img_format])

        # Convert the list of products to pandas dataframe
        imagery_prods_df = pd.DataFrame(imagery_prods)
        imagery_prods_df.columns = ['Imagery_Product_Name', 'Image_Resolution', 'Image_Format']

        # Search for product name specified by user in available products
        name = name.lower().split()
        filter_df = imagery_prods_df
        for x in name:
            filter_df = filter_df[filter_df.Imagery_Product_Name.str.lower().str.contains(x, na=False)]

        if len(filter_df) == 1 and name[0] == filter_df.Imagery_Product_Name.item():
            name = filter_df.Imagery_Product_Name.item().replace("_"," ")
            res = filter_df.Image_Resolution.item()
            img_format = filter_df.Image_Format.item()
            print(name, res, img_format)
            
        elif len(set(filter_df.Imagery_Product_Name)) == 1 and name[0] == set(filter_df.Imagery_Product_Name):
            filter_df = filter_df.sort_values(by=["Image_Resolution"])
            name = filter_df.Imagery_Product_Name.iloc[0].replace("_"," ")
            res = filter_df.Image_Resolution.iloc[0]
            img_format = filter_df.Image_Format.iloc[0]
            
        else:
            print("\n\n\nPlease enter the full imagery product name from the following list:\n")
            print(filter_df[["Imagery_Product_Name", "Image_Resolution"]].to_string(index=False))
            sys.exit("\n\n\n")

        # Converting image resolution to kilometers
        if res[-2:] == 'km':
            res = float(res[:len(res)-2])
        elif res[-1] == 'm':
            res = float(res[:len(res)-1])/1000

        return name, res, img_format

import pathlib
import sys

import pandas as pd

class DatasetSearcher():
    @classmethod
    def getProductInfo(cls, name):
        # convert imagery products .csv file into a pandas dataframe
        path = str(pathlib.Path(__file__).parent.absolute())
        imagery_products_df = pd.read_csv(path+"/gibs_imagery_products.csv")
        
        # search for product name specified by user in available products
        name = name.lower().split()
        filter_df = imagery_products_df

        for x in name:
            filter_df = filter_df[filter_df.Imagery_Product_Name.str.lower().str.contains(x, na=False)]
        if len(filter_df) == 1:
            name = filter_df.Imagery_Product_Name.item().replace("_"," ")
            res = filter_df.Image_Resolution.item()
            img_format = filter_df.Format.item()

        elif len(set(filter_df.Imagery_Product_Name)) == 1:
            filter_df = filter_df.sort_values(by=["Image_Resolution"])
            name = filter_df.Imagery_Product_Name.iloc[0].replace("_"," ")
            res = filter_df.Image_Resolution.iloc[0]
            img_format = filter_df.Format.iloc[0]

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
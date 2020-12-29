# NASA-GIBS-Downloader
NASA-GIBS-Downloader is a command-line tool which facilitates the downloading of NASA satellite imagery and offers different functionalities in order to prepare the images for training in a machine learning pipeline. The tool currently provides support for downloading the following product: `MODIS_Terra_CorrectedReflectance_TrueColor`. You can read more about this specific product [here](https://wiki.earthdata.nasa.gov/display/GIBS/GIBS+Available+Imagery+Products#expand-CorrectedReflectance17Products).

## Dependencies 
This package depends on the GDAL translator library. Before installing the GIBSDownloader package and thus the GDAL Python binding, you have to install GDAL on your machine. I have found that the easiest way to do this is create a virtual environment in which you will use the GIBSDownloader, and then install GDAL with conda as follows: ``conda install -c conda-forge gdal``.

## Installation
Once GDAL is installed on your machine, the GIBSDownloader package can be installed using: `pip install git+https://github.com/spaceml-org/NASA-GIBS-Downloader.git#egg=GIBSDownloader`  
Once installed, the packaged can be referenced as `gdl` on the command-line.  
\
**NOTE:** this package must be installed in the same virtual environment in which you installed GDAL.

## Usage
### Positional Arguments
There are six required positional arguments which are as follows:
`start-date`, `end-date`, `left-lon`, `upper-lat`, `right-lon`, `lower-lat`. The first two arguments establish a range of dates to download the images, and the remaining four arguments form the top left and bottom right coordinates of the desired rectangular region to be downloaded.

### Optional Parameters
As well as the required positional arguments, the GIBSDownloader also offers some optional parameters for increased customizability.  
`--tile`: when set to true, each downloaded image will be tiled, and the tiles will be outputted as jpegs.  
`--tile-width`: specifies the width of each tile (defaults to 512 px).  
`--tile-height`: specifies the height of each tile (defaults to 512 px).  
`--tile-overlap`: determines the overlap between consecutive tiles while tiling (defaults 0.5).  
`--generate-tfrecords`: when set to true, the tiles are used to generate 100 MB TFRecord files which contains the tiles as well as the coordinates of the top left and bottom right corner of each tile.  
`--remove-originals`: when set to true, the original downloaded images will be deleted and only the tiled images and TFRecords will be saved  

### Example 
Say we want to download images of the Bay Area in California from 15 September 2020 to 30 September 2020, while also tiling the downloaded images and writing to TFRecords.  
\
This can be done with the following command:  
`gdl 2020-09-15 2020-09-30 40.353784 -124.328539 37.003277 -120.253964 --tile=true --generate-tfrecords=true`.  
This will create the following directory structure: 
```
modis_upper-lat_left-lon_start-date_end-date/
      |> original_images/
           |> modis_date.tif
      |> tiled_images/
           |> width_height_overlap/
                |> date_coordinates.jpeg
      |> tfrecords
           |> width_height_overlap/
                |> modis_tf.tfrecord
```
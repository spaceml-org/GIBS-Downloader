# NASA-GIBS-Downloader
NASA-GIBS-Downloader is a command-line tool which facilitates the downloading of NASA satellite imagery and offers different functionalities in order to prepare the images for training in a machine learning pipeline. The tool currently provides support for downloading the following product: `MODIS_Terra_CorrectedReflectance_TrueColor`

## Dependencies 
This package depends on the GDAL translator library. I have found that the easiest way to install this dependency is using conda as follows: ``conda install -c conda-forge gdal``. All other dependencies are specified in `requirements.txt`

## Installation

## Usage
Sample coordinates for Bay Area: `40.353784 -124.328539 37.003277 -120.253964`
### Positional Arguments
`start-date`, `end-date`, `left-lon`, `upper-lat`, `right-lon`, `lower-lat`

### Optional Arguments
`--tile`, `--tile-width`, `--tile-height`, `--tile-overlap`, `--generate-tfrecords`

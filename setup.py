from setuptools import setup, find_packages 

with open('requirements.txt') as f:
    requirements = f.readlines() 

long_description = '''Python wrapper package for NASA GIBS API \ 
    with additional utility functions to prepare downloaded images for \
    machine learning pipeline''' 

setup(
    name ='GIBSDownloader', 
    version ='1.0.0', 
    author ='Fernando Lisboa, Shivam Verma', 
    author_email ='0fernando.lisboa@gmail.com', 
    url ='https://github.com/spaceml-org/NASA-GIBS-Downloader', 
    description ='Downloading tool for NASA GIBS', 
    long_description = long_description, 
    long_description_content_type ="text/markdown",  
    packages = find_packages(), 
    entry_points ={ 
        'console_scripts': [ 
            'gdl = GIBSDownloader.gibs_downloader:main'
        ] 
    }, 
    classifiers =( 
        "Programming Language :: Python :: 3", 
        "Operating System :: OS Independent", 
    ), 
    keywords ='GIBS gdl satellite python package GIBSDownloader', 
    install_requires = requirements, 
    zip_safe = False
)
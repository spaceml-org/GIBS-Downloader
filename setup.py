from setuptools import setup, find_packages 

with open('requirements.txt') as f:
    requirements = f.readlines() 

long_description = '''Python package for downloading NASA GIBS imagery \ 
    with additional functionality to prepare downloaded images for \
    machine learning pipeline''' 

setup(
    name='GIBSDownloader', 
    version='1.0.0', 
    license='Apache License 2.0',
    author='Fernando Lisboa, Navya Sandadi, Shivam Verma', 
    url='https://github.com/spaceml-org/GIBS-Downloader', 
    description='Downloading tool for NASA GIBS satellite imagery', 
    long_description=long_description, 
    long_description_content_type="text/markdown",  
    packages=find_packages(), 
    entry_points={ 
        'console_scripts': [ 
            'gdl = GIBSDownloader.gibs_downloader:main'
        ] 
    }, 
    classifiers=( 
        'Development Status :: 5 - Production/Stable',
        'License :: OSI Approved :: Apache Software License',
        'Intended Audience :: Science/Research',
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Programming Language :: Python :: 3.9",
        "Operating System :: OS Independent", 
    ), 
    keywords='GIBS gdl satellite python package GIBSDownloader', 
    install_requires=requirements, 
    python_requires='>=3.6',
    zip_safe=False,
    include_package_data=True
)
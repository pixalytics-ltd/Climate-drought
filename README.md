# Climate-drought
Development of drought indicators linked to the OGC Climate Resilience Pilot

## Standalone installation for Windows

Install conda environment using the Anaconda Prompt:
- Setup the climate_env conda environment from within the code directory: `conda env create -n climate_env -f environment.yml`
- Activate the environment: `conda activate climate_env`
- Use pip to install the main branch of the climate indices repository: `pip install -e git+https://github.com/monocongo/climate_indices.git@master#egg=climate_indices`
- Use pip to install the feature/20 branch of the pixutils repository: `pip install -e git+https://github.com/pixalytics-ltd/pixutils.git@feature/20#egg=pixutils`
- Use pip to install the main branch of the covjson_pydantic repository (needed as the pip package, version 0.1.0 doesn't have indenting): `pip install git+https://github.com/KNMI/covjson-pydantic.git`

Note: if the climate indices or pixutils respositories needs to be edited locally, then clone them and when inside the repository, with the conda environment activated, run: `python setup.py develop`

## Using pre-calculated index data from GDO

Fraction of Active Photosynthetically Active Radiation is obtained from a file downloaded manually from the Global Drought Observatory (GDO) where it has been precomputed. Soil moisture anomaly is either computed from ECMWF data, which takes a long time to request and download, or obtained directly from a precomputed file from GDO. These files must be downloaded for these indicies to be calculated.

Data source: https://edo.jrc.ec.europa.eu/gdo/php/index.php?id=2112
From the above link, download files and store in folders as follows:
- All within an 'input' directory as defined in config.py
- input/smant/ -> download in here all years under 'Ensemble Soil Moisture Anomaly' and 'Ensemble Soil Moisture Anomaly (2M...'
- input/fpanv/ -> download in here all years under 'FAPAR Anomaly' and 'FAPAR Anomaly (VIIRS)'
- input/spg03/ -> download in here all years under 'Standardised Precipitation Index, 03-month accumulation period'

## Testing climate indices

- Register on the Copernicus Climate Services portal: https://cds.climate.copernicus.eu/#!/home
- Get API key details and place in a file in your home directory i.e. create a file in our home directory called `.cdsapirc` with the two lines below where the key should be the one created:

```
url: https://cds.climate.copernicus.eu/api/v2
key: xxxx
```

- Run the test procedure in the activated conda environment where you define a local output directory: `python test_drought.py -y 52.5 -x 1.25 -s 20200101 -e 20221231 -p SPI -o <output-folder>`

## Index_viewer web app

Script to generate a web app to view and interact with Index input and output data.
To run:
- ensure streamlit=1.8.1 is installed in your environmnt
- ensure CONFIG constant is set up correctly (i.e. correct output path to ECMWF netcdfs, and input path to GDO)
- set RESTRICT_DATA_SELECTION to True to view pre-computed GDO and ECMWF data, or False to select anywhere/time using only GDO data.
- the 'DOWNLOADED' constant is a dictionary containing the details of data which has already been downloaded. I recommend downloading the required data for a number of test case CDI's using the test_drought script, because the web app will hang if you try to download data while that's running. Bear in mind that the dates of individual index data will not be the same as the arguments specified for the CDI, as the CDI requires historical data.
- in the command line, activate climate-env
- enter 'streamlit run index_viewer.py'
The web app will start up in a window in your browser (check the terminal to see which localhost it's using.)




[![DOI](https://zenodo.org/badge/597664161.svg)](https://doi.org/10.5281/zenodo.14643509)

# Climate-drought

Development of drought indicators linked to the OGC Climate Resilience & Disaster Pilots.

The code includes both pre-computer and computed climate indices, which those marked as experimental where they were included for specific testing purposes
* **SPI_ECMWF:** Standardized Precipitation Index (SPI) calculated from the ECMWF ERA-5 data, Copernicus Climate Change Service (C3S) API access - see below
* **SPI_GDO:** SPI pre-computed from the Global Drought Observatory (GDO), files manually downloaded
* **SPI_NCG:** SPI calculated from NOAA data, Experimental API access
* **SMA_ECMWF:** Soil Moisture Anomaly (SMA) calculated from the ECMWF ERA-5 data, C3S API access - see below
* **SMA_GDO:** SMA pre-computed from GDO, files manually downloaded
* **fAPAR:** Fraction of Active Photosynthetically Active Radiation is obtained from the GDO, files manually downloaded
* **CDI:** Combined Drought Indicator calculated from a combination of SPI, SMA and fAPAR
* **FEATURE_SAFE:** Climate projection data from SAFE, Experimental using provided file
* **UTCI:** Universal Thermal Climate Index (UTCI) download & calculated from the ECMWF ERA-5 data and then combined with SPI to create a Health Index, C3S API access - see below

## Installation of the climate_env conda environment

Install conda environment using the Anaconda Prompt:
* Setup the climate_env conda environment from within the code directory: `conda env create -n climate_env -f environment.yml`
* Activate the environment: `conda activate climate_env`
* Use pip to install the main branch of the climate indices repository: `pip install -e git+https://github.com/monocongo/climate_indices.git@master#egg=climate_indices`
* Use pip to install the feature/20 branch of the pixutils repository: `pip install -e git+https://github.com/pixalytics-ltd/pixutils.git@feature/20#egg=pixutils`
* Use pip to install the main branch of the covjson_pydantic repository (needed as the pip package, version 0.1.0 doesn't have indenting): `pip install git+https://github.com/KNMI/covjson-pydantic.git`

Note: if the climate indices or pixutils respositories needs to be edited locally, then clone them and when inside the repository, with the conda environment activated, run: `python setup.py develop`

## Testing/running the climate indices code

### To download the input data from the Copernicus Climate Change Service 
* Register on the Copernicus Climate Change Service's portal: https://cds.climate.copernicus.eu/how-to-api
* Get API key details and place in a file in your home directory i.e. create a file in our home directory called `.cdsapirc` with the two lines below where the key should be the one created:

```
url: https://cds.climate.copernicus.eu/api
key: xxxx
```

### Running tests using direct interaction with the code
* Setup and active the climate_env conda environment
* Run the python code interface: `python test_drought.py -y 52.5 -x 1.25 -s 20200101 -e 20221231 -p SPI -o <output-folder>`
* Run the test_drought notebook, which also needs in the conda environment:
    * Install jupytext: `python -m pip install jupytext --upgrade --user`
    * Create the ipynb format file from the Github synched Markdown version: `jupytext --set-formats ipynb,md --sync test_drought.md`
    * Make the environment available to the jupyter notebook: `python -m ipykernel install --user --name climate_env --display-name "Python (climate_env)"`
    * Startup: `jupyter notebook`

### Index_viewer web app
Script to generate a web app to view and interact with Index input and output data.
To run:
* Ensure streamlit=1.8.1 is installed in your environmnt
* Change `OUTPUT_DIR` to location of downloaded netcdf files from ECMWF and output JSON files
* The `DOWNLOADED` constant is a dictionary containing the details of data which has already been downloaded. I recommend downloading the required data for a number of test case CDI's using the test_drought script, because the web app will hang if you try to download data while that's running. Bear in mind that the dates of the individual index data will not be the same as the arguments specified here, as the CDI requires longer time-periods of indices.
* Activate the conda environment: `conda activate climate_env`
* Run streamlit: `streamlit run index_viewer.py`
The web app will start up in a window in your browser.




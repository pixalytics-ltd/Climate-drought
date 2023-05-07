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

## Testing climate indices

- Register on the Copernicus Climate Services portal: https://cds.climate.copernicus.eu/#!/home
- Get API key details and place in a file in your home directory i.e. create a file in our home directory called `.cdsapirc` with the two lines below where the key should be the one created:

```
url: https://cds.climate.copernicus.eu/api/v2
key: xxxx
```

- Run the test procedure in the activated conda environment where you define a local output directory: `python test_drought.py -y 52.5 -x 1.25 -s 20200101 -e 20221231 -p SPI -o <output-folder>`


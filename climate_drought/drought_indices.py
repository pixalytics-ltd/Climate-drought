import logging
import os
import numpy as np
import xarray as xr
import json
import geojson
import glob 

from climate_drought import indices, config, utils, era5_request as erq

# pygeometa for OGC API record creation
import yaml
import ast
import re
from pygeometa.core import read_mcf
from pygeometa.schemas.ogcapi_records import OGCAPIRecordOutputSchema

from abc import ABC, abstractclassmethod
from typing import List

# Logging
logging.basicConfig(level=logging.DEBUG)

class DroughtIndex(ABC):
    """
    Base class providing functionality for all drought indices
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs, index_shortname: str):
        """
        Initializer.
        :param config: config object
        :param args: analysis args object
        """
        # set up logger
        self.logger = logging.getLogger("ERA5_Processing")
        self.logger.setLevel(logging.DEBUG) if config.verbose else self.logger.setLevel(logging.INFO)
        
        # transfer inputs
        self.config = config
        self.args = args
        self.index_shortname = index_shortname

    @property
    def output_file_path(self):
        """
        Returns the path to the output file from processing
        :return: path to the output file
        """
        file_str = "{sd}-{ed}_{la}_{lo}".format(sd=self.args.start_date, ed=self.args.end_date, la=self.args.latitude, lo=self.args.longitude)
        return os.path.join(self.config.outdir, self.index_shortname + "_{d}.json".format(d=file_str))

    @abstractclassmethod
    def download(self) -> List[str]:
        """
        Abstract method to ensure bespoke download procedure is used for each index
        :return: list of netcdfs linking to downloaded files
        """
        pass

    @abstractclassmethod
    def process(self):
        """
        Abstract method to ensure bespoke processing procedure is used for each index
        """
        pass

    def generate_geojson(self, df_filtered) -> None:
        """
         Generates GeoJSON file for data
         :return: path to the geojson file
         """
        # Build GeoJSON object
        self.feature_collection = {"type": "FeatureCollection", "features": []}

        for i in df_filtered.index:
            feature = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [float(self.args.longitude), float(self.args.latitude)]}, "properties": {}}

            # Extract columns as properties
            property = df_filtered.loc[i].to_json(date_format='iso', force_ascii = True)
            parsed = json.loads(property)
            print("Sam: ",parsed)
            feature['properties'] = parsed

            # Add feature
            self.feature_collection['features'].append(feature)
        dump = geojson.dumps(self.feature_collection, indent=4)
        #self.logger.info("JSON: ",dump)

        # Reload to check formatting
        json_x = geojson.loads(dump)

        with open(self.output_file_path, "w", encoding='utf-8') as outfile:
            geojson.dump(json_x, outfile, indent=4)

    def generate_record(self) -> None:
        """
         Generates OGC API Record JSON file
         :return: path to the json file
         """

        # Read generic YML
        yaml_file = 'drought-ogc-record.yml'
        with open(os.path.join(os.path.dirname(__file__), yaml_file)) as f:
            # use safe_load instead load
            dataMap = yaml.safe_load(f)
            f.close()

        # Define output record yaml
        out_yaml = os.path.join(os.path.dirname(__file__), os.path.splitext(os.path.basename(yaml_file))[0] + "-updated.yml")

        # Update bounding box
        self.logger.info("dataMap: {} ".format(dataMap['identification']['extents']['spatial']))
        yaml_dict = {}
        ## [bounds.left, bounds.bottom, bounds.right, bounds.top]
        float_bbox = '[{:.3f},{:.3f},{:.3f},{:.3f}]'.format(float(self.req.longitude)-0.1, float(self.req.latitude)-0.1, float(self.req.longitude)+0.1, float(self.req.latitude)+0.1)
        yaml_dict.update({'bbox': ast.literal_eval(float_bbox)})
        #yaml_dict.update({'crs': ast.literal_eval(dst_crs.split(":")[1])})

        # remove single quotes
        res = {key.replace("'", ""): val for key, val in yaml_dict.items()}
        dataMap['identification']['extents']['spatial'] = [res]
        self.logger.info("Modified dataMap: {} ".format(dataMap['identification']['extents']['spatial']))

        # Update dates
        self.logger.debug("dataMap: {} ".format(dataMap['identification']['extents']['temporal']))
        fdate = self.json_file.split("_")[0]
        date_string = self.dates[0].strftime("%Y-%m-%d")
        end_date_string = self.dates[-1].strftime("%Y-%m-%d")

        yaml_dict = {}
        yaml_dict.update({'begin': date_string})
        yaml_dict.update({'end': end_date_string})
        dataMap['identification']['extents']['temporal'] = [yaml_dict]
        self.logger.debug("Modified dataMap: {} ".format(dataMap['identification']['extents']['temporal']))

        # Update index filename
        outdir = os.path.dirname(self.output_file_path)
        self.logger.debug("dataMap: {} ".format(dataMap['metadata']['dataseturi']))
        dataMap['metadata']['dataseturi'] = outdir + self.json_file
        self.logger.debug("Modified dataMap: {} ".format(dataMap['metadata']['dataseturi']))

        # Updated url and file type
        dataMap['distribution']['s3']['url'] = outdir + self.json_file
        if os.path.splitext(self.json_file) == "json":
            dataMap['distribution']['s3']['type'] = 'JSON'
        else:
            dataMap['distribution']['s3']['type'] = 'COG'
        self.logger.debug("Modified dataMap type: {} ".format(dataMap['distribution']['s3']['type']))
        self.logger.debug("Modified dataMap url: {} ".format(dataMap['distribution']['s3']['url']))

        # Remove single quotes
        dataDict = {re.sub("'", "", key): val for key, val in dataMap.items()}

        # Output modified version of YAML
        with open(out_yaml, 'w') as f:
            yaml.dump(dataDict, f)
            f.close()

        # Read modified YAML into dictionary
        mcf_dict = read_mcf(out_yaml)

        # Choose API Records output schema
        records_os = OGCAPIRecordOutputSchema()

        # Default schema
        json_string = records_os.write(mcf_dict)

        # Write to record file to disk
        json_file = os.path.join(outdir, "record.json")
        with open(json_file, 'w') as ff:
            ff.write(json_string)
            ff.close()

        self.logger.info("Processing completed successfully for {}".format(json_file))


class SPI(DroughtIndex):

    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        """
        Initializer
        :param args: program arguments
        :param working_dir: directory that will hold all files generated by the class
        """
        # precipitation download must return a baseline time series because this is a requirement of the outsourced spi calculation algorithm
        super().__init__(config, args, 'spi')
        
        # create era5 request object
        req = erq.ERA5Request(erq.PRECIP_VARIABLES, 'precip', self.args, self.config, baseline=True)

        # initialise the download object using the request, but don't download yet
        self.spi_download = erq.ERA5Download(req,self.logger)

        self.logger.debug("Initiated ERA5 daily processing of temperature strategy.")

    def download(self):
        """
        Download requried data from ERA5 portal using the imported ERA5 request module.
        The processing part of the SPI calculation requires that the long term dataset is passed in at the same time as the short term analysis period therefore we must request the whole baseline period for this analysis.
        :output: list containing name of single generated netcdf file. Must be a list as other indices will return the paths to multiple netcdfs for baseline and short-term timespans.
        """

        if os.path.exists(self.spi_download.download_file_path):
            self.logger.info("Downloaded file '{}' already exists.".format(self.spi_download.download_file_path))
        else:
            downloaded_file = self.spi_download.download()
            self.logger.info("Downloading  for '{}' completed.".format(downloaded_file))

        return [self.spi_download.download_file_path]

    def convert_precip_to_spi(self) -> None:
        """
        Calculates SPI precipitation drought index
        :param input_file_path: path to file containing precipitation
        :param output_file_path: path to file to be written containing SPI
        :return: nothing
        """

        # Extract data from NetCDF file
        datxr = xr.open_dataset(self.spi_download.download_file_path)
        self.logger.debug("Xarray:")
        self.logger.debug(datxr)

        # Convert to monthly sums and extract max of the available cells
        # group('time.month') is 1 to 12 while resamp is monthly data
        #if not self.args.accum:
        # TODO JC reinstate this for SPI but at the moment we're just using monthly data so accum will never be true
        resamp = datxr.tp.max(['latitude', 'longitude']).load()
        #else:
        #resamp = datxr.tp.resample(time='1MS').sum().max(['latitude', 'longitude']).load()
        precip = resamp[:, 0]

        self.logger.info("Input precipitation, {} values: {:.3f} {:.3f} ".format(len(precip.values), np.nanmin(precip.values), np.nanmax(precip.values)))

        # Calculate SPI
        spi = indices.INDICES()
        spi_vals = spi.calc_spi(np.array(precip.values).flatten())
        self.logger.info("SPI, {} values: {:.3f} {:.3f}".format(len(spi_vals), np.nanmin(spi_vals),np.nanmax(spi_vals)))
        resamp = resamp.sel(expver=1, drop=True)

        # Convert xarray to dataframe Series and add SPI
        df = resamp.to_dataframe()
        df['spi'] = spi_vals
        #df = df.reset_index(level=[1,2])
        self.logger.debug("DF: ")
        self.logger.debug(df.head())

        # Select requested time slice
        self.logger.debug("Filtering between {} and {}".format(self.args.start_date, self.args.end_date))
        self.logger.debug("Index: {}".format(df.index[0]))
        df_filtered = df.loc[(df.index >= self.args.start_date) & (df.index <= self.args.end_date)]

        # Convert date/time to string and then set this as the index
        df_filtered['StartDateTime'] = df_filtered.index.strftime('%Y-%m-%dT00:00:00')

        # Remove any NaN values
        df_filtered = df_filtered[~df_filtered.isnull().any(axis=1)]
        self.logger.debug("Updated DF: ")
        self.logger.debug(df_filtered.head())

        return df_filtered
    

    def process(self) -> str:
        """
        Carries out processing of the downloaded data.  This is the main functionality that is likely to differ between
        each implementation.
        :return: path to the output file generated by the algorithm
        """
        self.logger.info("Initiating processing of ERA5 daily data.")

        if not os.path.isfile(self.spi_download.download_file_path):
            raise FileNotFoundError("Unable to locate downloaded data '{}'.".format(self.spi_download.download_file_path))
        
        # Calculates SPI precipitation drought index
        df_filtered = self.convert_precip_to_spi()
        self.generate_geojson(df_filtered)

        return df_filtered
    
class SMA_ECMWF(DroughtIndex):
    """
    Specialisation of the json base class for downloading and processing soil water data
    """

    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        """
        Initializer.  Forwards parameters to super class, then instantiates download object.
        :param args: argument object
        :param working_dir: directory that will hold all files generated by the class
        """
        super().__init__(config,args,index_shortname='smecmwf')
        self.logger.debug("Initiated ERA5 daily processing of soil water.")
        
        # initialise download objects
        req_baseline = erq.ERA5Request(erq.SOILWATER_VARIABLES, 'soilwater', self.args, self.config, baseline=True)
        self.swv_monthly_download = erq.ERA5Download(req_baseline, self.logger)

        # create era5 request object for short term period
        req_shorterm = erq.ERA5Request(erq.SOILWATER_VARIABLES, 'soilwater', self.args, self.config, baseline=False, monthly=False)
        self.swv_hourly_download = erq.ERA5Download(req_shorterm, self.logger)
    
    def download(self):
        """
        Download requried data from ERA5 portal using the imported ERA5 request module.
        Download long term monthly data for the long term mean, and separately hourly data for short term period.
        """
        def exists_or_download(erad: erq.ERA5Download):
            if os.path.exists(erad.download_file_path):
                self.logger.info("Downloaded file '{}' already exists.".format(erad.download_file_path))
            else:
                downloaded_file = erad.download()
                self.logger.info("Downloading  for '{}' completed.".format(downloaded_file))
        
        # download baseline and monthly data
        exists_or_download(self.swv_monthly_download)
        exists_or_download(self.swv_monthly_download)

        return [self.swv_monthly_download.download_file_path, self.swv_hourly_download.download_file_path]

    def process(self) -> str:
        """
        Carries out processing of the downloaded data.  This is the main functionality that is likely to differ between
        each implementation.
        :return: path to the output file generated by the algorithm
        """
        self.logger.info("Initiating processing of ERA5 soil water data.")

        if not os.path.isfile(self.swv_monthly_download.download_file_path):
            raise FileNotFoundError("Unable to locate downloaded data '{}'.".format(self.swv_monthly_download.download_file_path))
        if not os.path.isfile(self.swv_hourly_download.download_file_path):
            raise FileNotFoundError("Unable to locate downloaded data '{}'.".format(self.swv_hourly_download.download_file_path))

        # Open netcdfs
        monthly_swv = xr.open_dataset(self.swv_monthly_download.download_file_path)
        hourly_swv = xr.open_dataset(self.swv_hourly_download.download_file_path).squeeze()

        # Reduce monthly data to what's relevant
        monthly_swv = monthly_swv.isel(expver=0).drop_vars('expver').mean(('latitude','longitude'))
        swv_mean = monthly_swv.mean('time')
        swv_std = monthly_swv.std('time')

        # Resmple hourly data to dekafs
        hourly_swv = hourly_swv.drop_vars(['latitude','longitude']).to_dataframe()
        swv_dekads = utils.to_dekads(hourly_swv)
        
        # Calculate zscores
        for layer in [1,2,3,4]:
            col = 'swvl' + str(layer)
            swv_dekads['zscore_' + col] = ((swv_dekads[col] - swv_mean[col].item()) / swv_std[col].item())

        # Output to JSON
        self.generate_geojson(swv_dekads)

        self.logger.info("Completed processing of ERA5 soil water data.")

        return swv_dekads

class SMA_EDO(DroughtIndex):
    """
    Specialisation of the Drought class for processing pre-downlaoded soil moisture anomaly data from EDO.
    Requires that you have downladed all years of 'Ensemble Soil Moisture Anomaly' and 'Ensemble Soil Moisture Anomaly (2M, Lisflood...' 
    from https://edo.jrc.ec.europa.eu/gdo/php/index.php?id=2112 and stored them in the 'input' folder as specified in the Config object
    i.e. Ensemble moisture data must all be in /inputs/smant
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        super().__init__(config,args,index_shortname='smedo')
        self.files_loc = config.indir + '/smant'
        self.filelist = glob.glob(self.files_loc + '/sma*.nc')

    def download(self):
        # Do nothing -data already downloaded
        if len(self.filelist) > 0:
            self.logger.info("Downloaded files available.")
        else:
            self.logger.info("Cannot find downloaded files in folder {}".format(self.files_loc))
        return self.files_loc
        

    def process(self):
        # open all dses - doesn't take long
        get_ds = lambda fname: xr.open_dataset(fname).sel(lat=self.args.latitude,lon=self.args.longitude,method='nearest').drop_vars(['lat','lon','4326']) 
        df = xr.merge(get_ds(fname) for fname in self.filelist).to_dataframe()

        # trim to required dates
        df = df.loc[(df.index >= self.args.start_date) & (df.index <= self.args.end_date)]

        # smand is the modelled data and is availale more recently than the long term time series of smant
        # replace missing smant values with smand and discard
        df.smant.fillna(df.smand, inplace=True)
        del df['smand']
        
        # Output to JSON
        self.generate_geojson(df)

        self.logger.info("Completed processing of ERA5 soil water data.")

        return df

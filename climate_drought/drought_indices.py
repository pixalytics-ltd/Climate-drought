import logging
import os
import numpy as np
import pandas as pd
import xarray as xr
import glob
import datetime
from dateutil.relativedelta import relativedelta

# JSON export
import json
import geojson
import orjson
from covjson_pydantic.reference_system import ReferenceSystem
from covjson_pydantic.domain import Domain
from covjson_pydantic.ndarray import NdArray
from covjson_pydantic.coverage import Coverage
from covjson_pydantic.parameter import Parameter, ParameterGroup

# Drought indices calculator
from climate_drought import indices, config, utils, era5_request as erq, gdo_download as gdo

# pygeometa for OGC API record creation
import yaml
import ast
import re
from pygeometa.core import read_mcf
from pygeometa.schemas.ogcapi_records import OGCAPIRecordOutputSchema

# code architecture
from abc import ABC, abstractclassmethod
from typing import List, Union, Dict
from enum import Enum


# Warning messages generated by climate_indices, TODO to fix
from numba.core.errors import NumbaDeprecationWarning, NumbaPendingDeprecationWarning
import warnings

warnings.simplefilter('ignore', category=NumbaDeprecationWarning)
warnings.simplefilter('ignore', category=NumbaPendingDeprecationWarning)

class SSType(Enum):
    """
    Spatial selection type
    """
    POINT = 'point'
    BBOX = 'bbox'
    POLYGON = 'polygon'

# where working in netcdf, and if using a polygon, we need a value to show where in the grid is not included in the polygon (since xarray covers a rectangular/square lat/lon area)
# this can't be nan as we can't differentiate between no data, so needs a unique value
OUTSIDE_AREA_SELECTION = -99999

class VarInfo():
    """
    Describes a variable which is output as part of the larger Drought Index object
    E.g. SPI_ECMWF outputs tp (total precipitation) and spi
    """
    def __init__(self,longname,units,label,link="https://xxx",gridsize=None):
        self.longname = longname
        self.units = units
        self.label = label
        self.link = link
        self.gridsize = gridsize

ALL_VARS = {
    'spg03': VarInfo('Standard Precipitation Index','unitless','Standard Precipitation Index',"https://climatedataguide.ucar.edu/climate-data/standardized-precipitation-index-spi",gridsize=1),
    'smand': VarInfo('Soil Moisture Anomaly','unitless','Soil Moisture Anomaly',"https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables",gridsize=0.1),
    'smant': VarInfo('Soil Moisture Anomaly','unitless','Soil Moisture Anomaly',"https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables",gridsize=0.1),
    'fpanv': VarInfo('fraction Absorbed Photosynthetically Active Radiation (fAPAR) Anomaly','unitless','fAPAR_anomaly',gridsize=0.083),
    'tp': VarInfo('Total Precipitation','m','Precipitation_amount',"https://vocab.nerc.ac.uk/standard_name/precipitation_amount/"),
    'spi': VarInfo('Standard Precipitation Index','unitless','Standard Precipitation Index',"https://climatedataguide.ucar.edu/climate-data/standardized-precipitation-index-spi"),
    'swvl1': VarInfo('Soil Water Volume Layer 1','m3/m3','Soil_moisture_amount',"https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables"),
    'swvl2': VarInfo('Soil Water Volume Layer 2','m3/m3','Soil_moisture_amount',"https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables"),
    'swvl3': VarInfo('Soil Water Volume Layer 3','m3/m3','Soil_moisture_amount',"https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables"),
    'swvl4': VarInfo('Soil Water Volume Layer 4','m3/m3','Soil_moisture_amount',"https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables"),
    'zscore_swvl1': VarInfo('Soil Moisture Anomaly Layer 1','unitless','Soil Moisture Anomaly',"https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables"),
    'zscore_swvl2': VarInfo('Soil Moisture Anomaly Layer 2','unitless','Soil Moisture Anomaly',"https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables"),
    'zscore_swvl3': VarInfo('Soil Moisture Anomaly Layer 3','unitless','Soil Moisture Anomaly',"https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables"),
    'zscore_swvl4': VarInfo('Soil Moisture Anomaly Layer 4','unitless','Soil Moisture Anomaly',"https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables"),
    'CDI': VarInfo('Combined Drought Index','unitless','Combined Drought Index')
    }

class DroughtIndex(ABC):
    """
    Base class providing functionality for all drought indices
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs, vars: Dict[str,VarInfo]):
        """
        Initializer.
        :param config: config object
        :param args: analysis args object
        """
        
        # transfer inputs
        self.config = config
        self.args = args
        self.vars = vars

        # turn lat, lon input into a list if necessary
        if not isinstance(args.latitude,list):
            self.args.latitude = [args.latitude]
        if not isinstance(args.longitude,list):
            self.args.longitude = [args.longitude]
        if not len(self.args.latitude)==len(self.args.latitude):
            self.logger.error('Latitude and longitude input must be single numbers or lists of the same length.')
            quit()

        # determine if we'e dealing with a point, polygon or bounding box
        if len(self.args.latitude)==1:
            self.sstype = SSType.POINT
        elif len(self.args.latitude)==2:
            self.sstype = SSType.BBOX
        else:
            self.sstype = SSType.POLYGON

        # set up logger
        self.logger = logging.basicConfig(filename='{0}/log_{1}.txt'.format(config.outdir,datetime.datetime.now()),level=logging.DEBUG)
        self.logger = logging.getLogger("ERA5_Processing")
        self.logger.setLevel(logging.DEBUG) if config.verbose else self.logger.setLevel(logging.INFO)

        # Assign an empty dataframe and dataset to hold data
        # Need both to support different output formats
        self.data_df = pd.DataFrame()
        self.data_ds = xr.Dataset()

    @property
    def index_shortname(self):
        return type(self).__name__.replace('_','')

    @property
    def output_file_path(self):
        """
        Returns the path to the output file from processing
        :return: path to the output file
        """
        latstr = str(self.args.latitude).replace('[','').replace(']','').replace(', ','-')
        lonstr = str(self.args.longitude).replace('[','').replace(']','').replace(', ','-')

        file_str = "{sd}-{ed}_{la}_{lo}".format(sd=self.args.start_date, ed=self.args.end_date, la=latstr, lo=lonstr)
        oformat = self.args.oformat.lower()
        if "cov" in oformat: # Generate CoverageJSON file
            file_ext = 'covjson'
        elif "csv" in oformat:  # Generate CSV
            file_ext = 'csv'
        elif "net" in oformat:  # Generate NetCDF
            file_ext = 'nc'
        else: # Generate GeoJSON
            file_ext = 'json'

        return os.path.join(self.config.outdir, self.index_shortname.lower() + "_{d}.{e}".format(d=file_str, e=file_ext))

    @abstractclassmethod
    def download(self) -> List[str]:
        """
        Abstract method to ensure bespoke download procedure is used for each index
        :return: list of netcdfs linking to downloaded files
        """
        pass

    @abstractclassmethod
    def process(self) -> pd.DataFrame:
        """
        Abstract method to ensure bespoke processing procedure is used for each index.
        MUST produce a dataframe with index time, columns latitude and longitude for output file processing
        """
        pass

    def generate_geojson(self) -> None:
        """
         Generates GeoJSON file for data
         :return: path to the geojson file
         """
        # Build GeoJSON object
        self.feature_collection = {"type": "FeatureCollection", "features": []}

        df = self.data_df.set_index(['time','latitude','longitude'])
        for i in df.index:
            feature = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [i[2], i[1]]}, "properties": {}}

            # Extract columns as properties
            property = df.loc[i].to_json(date_format='iso', force_ascii = True)
            parsed = json.loads(property)
            #print("Sam: ",parsed)
            feature['properties'] = parsed

            # Add feature
            self.feature_collection['features'].append(feature)
        dump = geojson.dumps(self.feature_collection, indent=4)
        #self.logger.info("JSON: ",dump)

        # Reload to check formatting
        json_x = geojson.loads(dump)

        with open(self.output_file_path, "w", encoding='utf-8') as outfile:
            geojson.dump(json_x, outfile, indent=4)

    def generate_covjson(self) -> None:
        """
         Generates CoverageJSON file for data
         :return: path to the json file
         """

        # Extract dates and values
        dates = self.data_ds.time.values
        latitudes = self.data_ds.latitude.values
        longitudes = self.data_ds.longitude.values

        parameters = dict()
        ranges = dict()

        for key, val in self.vars.items():
            # Add each variable to parameter dictionary
            parameters[key] = Parameter(
                type="Parameter",
                description={
                    "en": val.longname
                },
                unit={
                    "symbol":val.units
                },
                observedProperty={
                    "id": val.link,
                    "label": {
                        "en": val.label
                    }
                }
            )
            # Add each variable data to ranges
            ranges[key] = NdArray(
                axisNames=["x","y","t"],
                shape=[len(longitudes),len(latitudes),len(dates)],
                values=self.data_ds[key].to_numpy().flatten().tolist()
                )

        # Create Structure
        self.feature_collection = Coverage(
            domain=Domain(
                domainType="Grid",
                axes={
                    "x": {"dataType": "float", "values": longitudes.tolist()},
                    "y": {"dataType": "float", "values": latitudes.tolist()},
                    "t": {"dataType": "datetime", "values": [str(t) for t in dates]}
                },
            ),
            referencing=ReferenceSystem(coordinates=["x", "y"], type="GeographicCRS"),
            parameters=parameters,
            ranges=ranges
        )

        # TODO Indent option now fails
        self.logger.warning("The CovJSON indenting option is no longer working - need to look at")
        json_x = self.feature_collection.json(exclude_none=True)#, indent=True)
        f = open(self.output_file_path, "w", encoding='utf-8')
        f.write(json_x)

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
        if self.sstype==SSType.POINT:
            minlo = self.args.longitude[0]-0.1
            minla = self.args.latitude[0]-0.1
            maxlo = self.args.longitude[0]+0.1
            maxla = self.args.latitude[0]+0.1
        else:
            minlo = np.min(self.args.longitude)
            minla = np.min(self.args.latitude)
            maxlo = np.max(self.args.longitude)
            maxla = np.max(self.args.latitude)
        float_bbox = '[{:.3f},{:.3f},{:.3f},{:.3f}]'.format(minlo, minla, maxlo, maxla)
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

    def generate_output(self) -> None:
        # Save JSON file
        ## TODO SL to finish implementation of CoverageJSON so can be chosen option
        print('Generating output...')
        if not os.path.isfile(self.output_file_path):
            oformat = self.args.oformat.lower()
            if "cov" in oformat:  # Generate CoverageJSON file
                self.generate_covjson()
            elif "csv" in oformat:  # Generate CSV
                self.data_df.to_csv(self.output_file_path,index=False)
            elif "net" in oformat:  # Generate NetCDF
                xr.Dataset(self.data_ds).to_netcdf(self.output_file_path)
            else:  # Generate GeoJSON
                self.generate_geojson()
        else:
            self.logger.warning('Outfile not written: already exists')

class GDODroughtIndex(DroughtIndex):
    """
    Specialisation of the Drought class for processing pre-computed indices from the Global Drought Observatory.
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs, prod_code: Union[List[str], str]):

        # Turn product code into list if not already
        self.prod_code = [prod_code] if isinstance(prod_code,str) else prod_code

        # Get variable details for reuested products
        vars = dict(filter(lambda k: k[0] in self.prod_code, ALL_VARS.items()))

        super().__init__(config,args,vars)
        self.grid_size = next(iter(self.vars.values())).gridsize
        self.fileloc = config.indir + "/" + self.prod_code[0]

        # Create GDO download objects so we can see what the filenames are
        
        # create list of years to download data for
        years = np.arange(int(self.args.start_date[:4]),int(self.args.end_date[:4])+1)

        dl_objs = []
        for y in years:
            for pc in self.prod_code:
                obj = gdo.GDODownload(y,pc,logger=self.logger)
                if obj.success:
                    dl_objs.append(obj)

        self.files = dl_objs
        self.filelist = []

    def download(self):

        filelist = []
        if not os.path.isdir(self.fileloc):
            os.mkdir(self.fileloc)

        for f in self.files:
            filelist = filelist + f.download(self.fileloc)

        self.filepaths = [self.fileloc + "/" + f for f in filelist]
        return self.filepaths
            
    def load_and_trim(self):

        if len(self.filepaths)==0:
            self.logger.error('No files downloaded')

        def open_point(fname):
            return xr.open_dataset(fname).sel(lat=self.args.latitude,lon=self.args.longitude,method='nearest').drop_vars(['4326']) 

        def open_bbox(fname):
            ds = xr.open_dataset(fname).drop_vars(['4326'])
            return utils.mask_ds_bbox(ds,
                                        np.min(self.args.longitude),
                                        np.max(self.args.longitude),
                                        np.min(self.args.latitude),
                                        np.max(self.args.latitude)
            )

        def open_poly(fname):
            ds = xr.open_dataset(fname).drop_vars(['4326']) 
            return utils.mask_ds_poly(ds,
                                        self.args.latitude,
                                        self.args.longitude,
                                        self.grid_size,
                                        self.grid_size,
                                        other = OUTSIDE_AREA_SELECTION
                                        )
        # Methods to open data
        open_func = {
            SSType.POINT.value: open_point,
            SSType.BBOX.value: open_bbox,
            SSType.POLYGON.value: open_poly
        }

        # Open all dses and merge
        ds = xr.merge(open_func[self.sstype.value](fname) for fname in self.filepaths)

        # Trim to required dates
        ds = ds.sel(time=slice(pd.Timestamp(self.args.start_date),pd.Timestamp(self.args.end_date)))

        return ds
  
class SPI_ECMWF(DroughtIndex):

    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        """
        Initializer
        :param args: program arguments
        :param working_dir: directory that will hold all files generated by the class
        """
        # Get variable details for reuested products
        vars = dict(filter(lambda k: k[0] in ['tp','spi'], ALL_VARS.items()))

        # precipitation download must return a baseline time series because this is a requirement of the outsourced spi calculation algorithm
        super().__init__(config, args, vars)
        
        # create era5 request object
        request = erq.ERA5Request(
            erq.PRECIP_VARIABLES,
            'precip',
            self.args,
            self.config, 
            start_date=config.baseline_start,
            end_date=config.baseline_end,
            frequency=erq.Freq.MONTHLY,
            aws=self.config.aws)

        # initialise the download object using the request, but don't download yet
        self.download_obj = erq.ERA5Download(request,self.logger)

    def download(self):
        """
        Download required data from ERA5 portal using the imported ERA5 request module.
        The processing part of the SPI calculation requires that the long term dataset is passed in at the same time as the short term analysis period therefore we must request the whole baseline period for this analysis.
        :output: list containing name of single generated netcdf file. Must be a list as other indices will return the paths to multiple netcdfs for baseline and short-term timespans.
        """

        if os.path.exists(self.download_obj.download_file_path):
            self.logger.info("Downloaded file '{}' already exists.".format(self.download_obj.download_file_path))
        else:
            downloaded_file = self.download_obj.download()
            self.logger.info("Downloading  for '{}' completed.".format(downloaded_file))

        return [self.download_obj.download_file_path]

    def convert_precip_to_spi(self) -> None:
        """
        Calculates SPI precipitation drought index
        :param input_file_path: path to file containing precipitation
        :param output_file_path: path to file to be written containing SPI
        :return: nothing
        """

        # Extract data from NetCDF file
        ds = xr.open_dataset(self.download_obj.download_file_path)

        if 'expver' in ds.keys():
            ds = ds.sel(expver=1,drop=True)

        self.logger.debug("Xarray:")
        self.logger.debug(ds)

        # Mask polygon if needed
        if self.sstype.value==SSType.POLYGON.value:
            ds = utils.mask_ds_poly(
                ds=ds,
                lats=self.args.latitude,
                lons=self.args.longitude,
                grid_x=0.1,
                grid_y=0.1,
                ds_lat_name='latitude',
                ds_lon_name='longitude',
                other=OUTSIDE_AREA_SELECTION,
                mask_bbox=False
            )

        # Get total precipitation as data array
        da = ds.tp

        # Set up SPI calculation  algorithm
        spi = indices.INDICES()

        # Convert to monthly sums and extract max of the available cells
        if self.config.aws or self.config.era_daily: # or any other setting which would result in more than monthy data
            da = da.resample(time='1MS').sum()
            
        if self.sstype.value==SSType.POINT.value:
            da = da.max(['latitude', 'longitude']).load()
            spi_vals = spi.calc_spi(da)
        else:
            spi_vals = xr.apply_ufunc(spi.calc_spi,da,input_core_dims=[['time']],output_core_dims=[['time']],vectorize=True)

        self.logger.info("Input precipitation, {} values: {:.3f} {:.3f} ".format(len(da.values), np.nanmin(da.values), np.nanmax(da.values)))
        self.logger.info("SPI, {} values: {:.3f} {:.3f}".format(len(spi_vals), np.nanmin(spi_vals),np.nanmax(spi_vals)))

        # Store spi
        ds = xr.Dataset(data_vars={'tp':da,'spi':spi_vals})

        return ds
    
    def process(self):
        """
        Carries out processing of the downloaded data.  This is the main functionality that is likely to differ between
        each implementation.
        :return: path to the output file generated by the algorithm
        """
        self.logger.info("Initiating processing of ERA5 daily data.")

        if not os.path.isfile(self.download_obj.download_file_path):
            raise FileNotFoundError("Unable to locate downloaded data '{}'.".format(self.spi_download.download_file_path))
        
        # Calculates SPI precipitation drought index
        ds = self.convert_precip_to_spi()

        # Select requested time slice
        ds_filtered = utils.crop_ds(ds,self.args.start_date,self.args.end_date)

        # Fill any missing gaps
        time_months = pd.date_range(self.args.start_date,self.args.end_date,freq='1MS')
        ds_reindexed = ds_filtered.reindex({'time': time_months})

        df_reindexed = ds_reindexed.to_dataframe().reset_index()

        # store processed data on object
        self.data_ds = ds_reindexed
        self.data_df = df_reindexed

        self.generate_output()

        return df_reindexed

class SPI_GDO(GDODroughtIndex):
    """
    Specialisation of the GDODrought class for processing pre-computed photosynthetically active radiation anomaly data from GDO.
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        super().__init__(config,args,'spg03')

    def process(self):
        ds = super().load_and_trim()

        # Fill any data gaps
        time_months = pd.date_range(self.args.start_date,self.args.end_date,freq='1MS')
        ds = ds.reindex({'time': time_months})

        # Rename lat and lon coords for consitency with other drought indices
        ds = ds.rename({'lat':'latitude','lon':'longitude'})

        self.data_ds = ds

        # Convert to df for output
        df = ds.to_dataframe().reset_index()

        # Drop locations outside of selected area
        df = df[df.spg03!=OUTSIDE_AREA_SELECTION]
        self.data_df = df

        #self.generate_output()

        return df

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

        # Get variable details for reuested products
        vars = dict(filter(lambda k: k[0] in ['swvl1','swvl2','swvl3','swvl4','zscore_swvl1','zscore_swvl2','zscore_swvl3','zscore_swvl4'], ALL_VARS.items()))

        super().__init__(config,args,vars)
        self.logger.debug("Initiated ERA5 daily processing of soil water.")
        
        #initialise download objects
        #long-term 'baseline' object to compute the mean
        request_baseline = erq.ERA5Request(
            erq.SOILWATER_VARIABLES,
            'soilwater',
            self.args,
            self.config,
            start_date=config.baseline_start,
            end_date=config.baseline_end,
            frequency=erq.Freq.MONTHLY)
        
        self.download_obj_baseline = erq.ERA5Download(request_baseline, self.logger)

        #create era5 request object for short term period
        request_sample = erq.ERA5Request(
            erq.SOILWATER_VARIABLES,
            'soilwater',
            self.args,
            self.config,
            args.start_date,
            args.end_date,
            frequency=erq.Freq.DAILY if self.config.era_daily else erq.Freq.HOURLY)
        
        self.download_obj_sample = erq.ERA5Download(request_sample, self.logger)
    
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
        exists_or_download(self.download_obj_baseline)
        exists_or_download(self.download_obj_sample)

        return [self.download_obj_baseline.download_file_path, self.download_obj_sample.download_file_path]

    def process(self) -> str:
        """
        Carries out processing of the downloaded data.  This is the main functionality that is likely to differ between
        each implementation.
        :return: path to the output file generated by the algorithm
        """
        self.logger.info("Initiating processing of ERA5 soil water data.")

        path_monthly = self.download_obj_baseline.download_file_path
        path_sample = self.download_obj_sample.download_file_path

        if not os.path.isfile(path_monthly):
            raise FileNotFoundError("Unable to locate downloaded data '{}'.".format(path_monthly))
        
        if not os.path.isfile(path_sample):
            raise FileNotFoundError("Unable to locate downloaded data '{}'.".format(path_sample))

        # Open netcdfs
        monthly_swv = xr.open_dataset(path_monthly)
        sample_swv = xr.open_dataset(path_sample).squeeze()

        # Mask polygon if needed
        if self.sstype.value==SSType.POLYGON.value:
            mask_ds = lambda ds: utils.mask_ds_poly(
                ds=ds,
                lats=self.args.latitude,
                lons=self.args.longitude,
                grid_x=0.1,
                grid_y=0.1,
                ds_lat_name='lat' if self.config.era_daily else 'latitude',
                ds_lon_name='lon' if self.config.era_daily else 'longitude',
                other=OUTSIDE_AREA_SELECTION,
                mask_bbox=False
            )
            monthly_swv=mask_ds(monthly_swv)
            sample_swv=mask_ds(sample_swv)

        # Reduce monthly data to what's relevant
        if 'expver' in monthly_swv.keys():
            monthly_swv = monthly_swv.isel(expver=0).drop_vars('expver')

        monthly_swv = monthly_swv.mean(('latitude','longitude'))
        swv_mean = monthly_swv.mean('time')
        swv_std = monthly_swv.std('time')

        if self.sstype.value==SSType.POINT:
            sample_swv = sample_swv.drop_vars(['lat','lon'] if self.config.era_daily else ['latitude','longitude'])

        # Resmple sample data to dekads
        swv_dekads = utils.ds_to_dekads(sample_swv)
        
        # Calculate zscores
        for layer in [1,2,3,4]:
            col = 'swvl' + str(layer)
            swv_dekads['zscore_' + col] = ((swv_dekads[col] - swv_mean[col].item()) / swv_std[col].item())

        # fill any data gaps
        time_dekads = utils.dti_dekads(self.args.start_date,self.args.end_date)
        swv_dekads = swv_dekads.reindex({'time':time_dekads})

        self.logger.info("Completed processing of ERA5 soil water data.")

        self.data_ds = swv_dekads
        self.data_df = swv_dekads.to_dataframe().reset_index()

        # Output to JSON
        self.generate_output()

        return swv_dekads

class SMA_GDO(GDODroughtIndex):
    """
    Specialisation of the GDODrought class for processing pre-computed soil moisture anomaly from GDO.
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        super().__init__(config,args,['smant']) #['smant','smand']

    def process(self):
        print('Loading and trimmning data...')
        ds = super().load_and_trim()

        # TODO reimplement if it is important to have data beyond 2022
        # # smand is used instead of smant for November 2022 (2nd dekad) onwards
        # # split data, rename smand -> smant, and recombine
        # if 'smand' in list(ds.variables):
        #     da_smant = utils.crop_ds(ds.smant,self.args.start_date,'20221110')
        #     da_smand = utils.crop_ds(ds.drop_vars('smant').rename({'smand':'smant'}).smant,'20221111',self.args.end_date)
        #     da = xr.concat([da_smant,da_smand],dim='time')
        #     self.vars.pop('smand')
        # else:
        #     da = ds.smant

        # Fill any data gaps
        print('Filling gaps  in data...')  
        time_dekads = utils.dti_dekads(self.args.start_date,self.args.end_date)
        ds = ds.reindex({'time': time_dekads})

        # Rename lat and lon coords for consitency with other drought indices
        ds = ds.rename({'lat':'latitude','lon':'longitude'})

        self.data_ds = ds
        
        # Convert to df for output
        print('Converting to dataframe...')
        df = ds.to_dataframe().reset_index()

        # Drop locations outside of selected area
        print('Reducing to requested area...')
        df = df[df.smant!=OUTSIDE_AREA_SELECTION]
        self.data_df = df

        #self.generate_output()

        return df

class FPAR_GDO(GDODroughtIndex):
    """
    Specialisation of the GDODrought class for processing pre-computed photosynthetically active radiation anomaly data from GDO.
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        super().__init__(config,args,'fpanv')
    
    def process(self):
        ds = super().load_and_trim()

        # Fill any data gaps
        time_dekads = utils.dti_dekads(self.args.start_date,self.args.end_date)
        ds = ds.reindex({'time': time_dekads})
        
        # Rename lat and lon coords for consitency with other drought indices
        ds = ds.rename({'lat':'latitude','lon':'longitude'})

        self.data_ds = ds

        # Convert to df for output
        df = ds.to_dataframe().reset_index()

        # Drop locations outside of selected area
        df = df[df.fpanv!=OUTSIDE_AREA_SELECTION]
        self.data_df = df

        #self.generate_output()

        return df

class CDI(DroughtIndex):

    """
    Extension of base class for combined drought indicator
    """
    def __init__(
            self,
            cfg: config.Config,
            args: config.CDIArgs
            ):
        
        # Get variable details for reuested products
        vars = dict(filter(lambda k: k[0] in [args.spi_var,args.sma_var,args.fpr_var,'CDI'], ALL_VARS.items()))
        
        super().__init__(cfg,args,vars)

        # Initialise all separate indicators to be combined
        sdate_ts = pd.Timestamp(args.start_date)
        sdate_dk = sdate_ts.replace(day=utils.nearest_dekad(sdate_ts.day))

        def aa_new(required_sdate: pd.Timestamp) -> config.AnalysisArgs:
            """
            Helper function to quickly return modified arguments
            """
            # Makes sure start date is in dekads and the required format
            sdate = required_sdate.replace(day=utils.nearest_dekad(required_sdate.day))
            return config.AnalysisArgs(args.latitude,args.longitude,sdate.strftime('%Y%m%d'),args.end_date)
        
        # SPI: one month before
        # SPI dates are always at the start of each month because it's the monthly average
        sdate_spi = sdate_ts.replace(day=1) - relativedelta(months=1)
        spi_class = SPI_ECMWF if args.sma_source=='ECMWF' else SPI_GDO
        self.aa_spi = aa_new(sdate_spi)
        self.spi = spi_class(cfg,self.aa_spi)
            
        # SMA: 2 dekads before
        sdate_sma = sdate_dk - relativedelta(days=20)
        sma_class = SMA_ECMWF if args.sma_source=='ECMWF' else SMA_GDO
        self.aa_sma = aa_new(sdate_sma)
        self.sma = sma_class(cfg,self.aa_sma)
         
        # fAPAR - 1 dekad before
        sdate_fpr = sdate_dk - relativedelta(days=10)
        self.aa_fpr = aa_new(sdate_fpr)
        self.fpr = FPAR_GDO(cfg,self.aa_fpr)
        
        # Initialise times
        # We want our final timeseries to include all data from the beginning of the SPI to the end of the CDI, so all data can be retained
        self.time_dekads = utils.dti_dekads(sdate_spi,args.end_date)

    def download(self):
        spi_file = self.spi.download()
        sma_file = self.sma.download()
        fpr_file = self.fpr.download()

        return[spi_file,sma_file,fpr_file]
        
    def process(self):

        self.logger.info("Computing Combined Drought Indicator...")

        # For a CDI at time x, we use:
        # SPI: x - 1 month (3 dekads)
        # SMA: x - 2 dekad
        # fAPAR: x - previous full dekad

        # Process individual indices
        self.spi.process()
        self.sma.process()
        self.fpr.process()

        da_spi = self.spi.data_ds[self.args.spi_var]
        da_sma = self.sma.data_ds[self.args.sma_var]
        da_fpr = self.fpr.data_ds[self.args.fpr_var]

        # drop values outside requested area if polygon
        if self.sstype.value is SSType.POLYGON.value:
            da_spi = da_spi.where(da_spi != OUTSIDE_AREA_SELECTION)
            da_sma = da_sma.where(da_sma != OUTSIDE_AREA_SELECTION)
            da_fpr = da_fpr.where(da_fpr != OUTSIDE_AREA_SELECTION)

        # Interpolate SMA and FPR to same grid as CDI
        if not (self.sstype.value is SSType.POINT.value):
            da_sma = utils.regrid_like(da_sma,da_spi)
            da_fpr = utils.regrid_like(da_fpr,da_spi)

        da_sma = da_sma.reindex({'latitude':da_spi.latitude,'longitude':da_spi.longitude},method='nearest')
        da_fpr = da_fpr.reindex({'latitude':da_spi.latitude,'longitude':da_spi.longitude},method='nearest')

        # Reindex to shared timeframe
        spi_reindexed = da_spi.reindex({'time':self.time_dekads},method='ffill')
        sma_reindexed = da_sma.reindex({'time':self.time_dekads})
        fpr_reindexed = da_fpr.reindex({'time':self.time_dekads})

        self.ds_reindexed = xr.Dataset(data_vars = {self.args.spi_var: spi_reindexed,
                                                    self.args.sma_var: sma_reindexed,
                                                    self.args.fpr_var: fpr_reindexed})
        
        # Shift data to calculated CDI from delayed data
        spi_shifted = spi_reindexed.shift({'time':3})
        sma_shifted = sma_reindexed.shift({'time':2})
        fpr_shifted = fpr_reindexed.shift({'time':1})


        # Now create CDI with following levels:
        # 0: no warning
        # 1: watch = spi < -1
        # 2: warning = sma < -1 and spi < -1
        # 3: alert 1 = fpr < -1 and spi < -1
        # 4: alert 2 = all < -1

        def calc_cdi(spi,sma,fpr):
            spi_ = spi < -1
            sma_ = sma < -1
            fpr_ = fpr < -1
            cdi = np.ones_like(spi) * np.nan
            cdi[~spi_] = 0
            cdi[spi_] = 1
            cdi[spi_ & sma_] = 2
            cdi[spi_ & fpr_] = 3
            cdi[spi_ & sma_ & fpr_] = 4
            cdi[np.isnan(spi) | np.isnan(sma) | np.isnan(fpr)] = np.nan
            return cdi

        cdi = xr.apply_ufunc(calc_cdi,spi_shifted,sma_shifted,fpr_shifted)

        self.ds_shifted = xr.Dataset(data_vars={self.args.spi_var: spi_shifted, self.args.sma_var: sma_shifted, self.args.fpr_var: fpr_shifted, 'CDI': cdi})
        self.data_ds = self.ds_reindexed.assign(CDI=cdi)
        self.data_df = self.data_ds.to_dataframe().reset_index()

        self.generate_output()

        self.logger.info("Completed processing of ERA5 CDI data.")
        return self.data_df
    

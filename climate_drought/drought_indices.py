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
from typing import List, Union
from enum import Enum

# shapely for masking polyons
from shapely import Polygon, vectorized

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

# define grid size so we can crop to polygon area if needed
GDO_SPI_GRID = 1
GDO_SMA_GRID = 0.1
GDO_FPR_GRID = 0.083

class DroughtIndex(ABC):
    """
    Base class providing functionality for all drought indices
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        """
        Initializer.
        :param config: config object
        :param args: analysis args object
        """
        
        # transfer inputs
        self.config = config
        self.args = args

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

        # set data to empty df as an indicator that this hasn't been processed yet
        self.data = pd.DataFrame()

    @property
    def index_shortname(self):
        return type(self).__name__.replace('_','')

    @property
    def output_file_path(self):
        """
        Returns the path to the output file from processing
        :return: path to the output file
        """
        file_str = "{sd}-{ed}_{la}_{lo}".format(sd=self.args.start_date, ed=self.args.end_date, la=self.args.latitude, lo=self.args.longitude)
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

    # TODO needs updating for all possible options
    def generate_covjson(self, df_filtered) -> None:
        """
         Generates CoverageJSON file for data
         :return: path to the json file
         """

        # Extract dates and values
        dates = df_filtered.index.values

        # Print dataframe
        self.logger.debug("Data frame: ")
        self.logger.debug(df_filtered)

        if "SPI" in self.args.indicator or "CDI" in self.args.indicator:
            if "CDI" in self.args.indicator:
                spi_name = "SPI"
                spi_vals = df_filtered.spg03.values
                pvals = []
                for val in spi_vals:
                    pvals.append(float(val))
            else: #SPI
                spi_name = self.args.indicator
                spi_vals = df_filtered.spi.values
                svals = []
                for val in spi_vals:
                    svals.append(float(val))
                num_vals = len(spi_vals)

                precip_name = "Precipitation"

                precip_vals = df_filtered.tp.values
                pvals = []
                for val in precip_vals:
                    pvals.append(float(val))

                parameters = {
                    precip_name: Parameter(
                        type="Parameter",
                        description={
                            "en": "Total Precipitation"
                        },
                        unit={
                            "symbol": "m"
                        },
                        observedProperty={
                            "id": "https://vocab.nerc.ac.uk/standard_name/precipitation_amount/",
                            "label": {
                                "en": "Precipition_amount"
                            }
                        }
                    ),
                    spi_name: Parameter(
                        type="Parameter",
                        description={
                            "en": "Standard Precipitation Index"
                        },
                        unit={
                            "symbol": "unitless"
                        },
                        observedProperty={
                            "id": "https://climatedataguide.ucar.edu/climate-data/standardized-precipitation-index-spi",
                            "label": {
                                "en": "Standard Precipitation Index"
                            }
                        }
                    ),
                }

                ranges = {
                    precip_name: NdArray(axisNames=["x", "y", "t"], shape=[1, 1, num_vals], values=pvals),
                    spi_name: NdArray(axisNames=["x", "y", "t"], shape=[1, 1, num_vals], values=svals)
                }

        if "SMA" in self.args.indicator or "CDI" in self.args.indicator:
            if "CDI" in self.args.indicator:
                sma_name = "SMA"
                sma_vals = df_filtered.smant.values
                svals = []
                for val in sma_vals:
                    svals.append(float(val))
            else:
                sm_name = "Soil Moisture"
                self.logger.warning("Just outputting the surface, level 1, soil moisture and associated anomaly")

                sm_vals = df_filtered.swvl1.values
                pvals = []
                for val in sm_vals:
                    pvals.append(float(val))
                sma_name = self.args.indicator
                sma_vals = df_filtered.zscore_swvl1.values
                svals = []
                for val in sma_vals:
                    svals.append(float(val))
                num_vals = len(sma_vals)

                parameters = {
                    sm_name: Parameter(
                        type="Parameter",
                        description={
                            "en": "Surface Soil Moisture"
                        },
                        unit={
                            "symbol": "m3/m3"
                        },
                        observedProperty={
                            "id": "https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables",
                            "label": {
                                "en": "Soil_moisture_amount"
                            }
                        }
                    ),
                    sma_name: Parameter(
                        type="Parameter",
                        description={
                            "en": "Surface Soil Moisture Anomaly"
                        },
                        unit={
                            "symbol": "unitless"
                        },
                        observedProperty={
                            "id": "https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables",
                            "label": {
                                "en": "Surface Soil Moisture Anomaly"
                            }
                        }
                    ),
                }

                ranges = {
                    sm_name: NdArray(axisNames=["x", "y", "t"], shape=[1, 1, num_vals], values=pvals),
                    sma_name: NdArray(axisNames=["x", "y", "t"], shape=[1, 1, num_vals], values=svals)
                }

        if self.args.indicator == "CDI":
            cdi_name = self.args.indicator
            cdi_vals = df_filtered.CDI.values
            cvals = []
            for val in cdi_vals:
                cvals.append(float(val))
            num_vals = len(cdi_vals)

            fpv_name = "fAPAR anomaly"
            fpv_vals = df_filtered.fpanv.values
            fvals = []
            for val in fpv_vals:
                fvals.append(float(val))

            parameters = {
                spi_name: Parameter(
                    type="Parameter",
                    description={
                        "en": "Standard Precipitation Index"
                    },
                    unit={
                        "symbol": "unitless"
                    },
                    observedProperty={
                        "id": "https://climatedataguide.ucar.edu/climate-data/standardized-precipitation-index-spi",
                        "label": {
                            "en": "Standard Precipitation Index"
                        }
                    }
                ),
                sma_name: Parameter(
                    type="Parameter",
                    description={
                        "en": "Surface Soil Moisture Anomaly"
                    },
                    unit={
                        "symbol": "unitless"
                    },
                    observedProperty={
                        "id": "https://climatedataguide.ucar.edu/climate-data/soil-moisture-data-sets-overview-comparison-tables",
                        "label": {
                            "en": "Surface Soil Moisture Anomaly"
                        }
                    }
                ),
                fpv_name: Parameter(
                    type="Parameter",
                    description={
                        "en": "fraction Absorbed Photosynthetically Active Radiation (fAPAR) Anomaly"
                    },
                    unit={
                        "symbol": "unitless"
                    },
                    observedProperty={
                        "id": "https://xxx",
                        "label": {
                            "en": "fAPAR_anomaly"
                        }
                    }
                ),
                cdi_name: Parameter(
                    type="Parameter",
                    description={
                        "en": "Combined Drought Indicator"
                    },
                    unit={
                        "symbol": "unitless"
                    },
                    observedProperty={
                        "id": "https://xxx",
                        "label": {
                            "en": "combined_drought_indicator"
                        }
                    }
                )
            }

            self.logger.debug("Parameters: ")
            self.logger.debug(parameters)
            self.logger.debug("Output datasets: SPI {} SMA {} FPV {} CDI {}".format(len(pvals),len(svals),len(fvals),len(cvals)))

            ranges = {
                spi_name: NdArray(axisNames=["x", "y", "t"], shape=[1, 1, num_vals], values=pvals),
                sma_name: NdArray(axisNames=["x", "y", "t"], shape=[1, 1, num_vals], values=svals),
                fpv_name: NdArray(axisNames=["x", "y", "t"], shape=[1, 1, num_vals], values=fvals),
                cdi_name: NdArray(axisNames=["x", "y", "t"], shape=[1, 1, num_vals], values=cvals)
            }

        # Create Structure
        self.feature_collection = Coverage(
            domain=Domain(
                domainType="PointSeries",
                axes={
                    "x": {"dataType": "float", "values": [self.args.longitude]},
                    "y": {"dataType": "float", "values": [self.args.latitude]},
                    "t": {"dataType": "datetime", "values": list(dates)}
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

    def generate_output(self) -> None:
        # Save JSON file
        ## TODO SL to finish implementation of CoverageJSON so can be chosen option
        if not os.path.isfile(self.output_file_path):
            oformat = self.args.oformat.lower()
            if "cov" in oformat:  # Generate CoverageJSON file
                self.generate_covjson(self.data)
            elif "csv" in oformat:  # Generate CSV
                self.data.to_csv(self.output_file_path)
            elif "net" in oformat:  # Generate NetCDF
                xr.Dataset(self.data.to_xarray()).to_netcdf(self.output_file_path)
            else:  # Generate GeoJSON
                self.generate_geojson(self.data)
        else:
            self.logger.warning('Outfile not written: already exists')

class GDODroughtIndex(DroughtIndex):
    """
    Specialisation of the Drought class for processing pre-computed indices from the Global Drought Observatory.
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs, grid_size, prod_code: Union[List[str], str]):
        super().__init__(config,args)
        self.grid_size = grid_size
        self.prod_code = [prod_code] if isinstance(prod_code,str) else prod_code
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
            
    def load_and_trim(self):

        if len(self.filepaths)==0:
            self.logger.error('No files downloaded')

        # Methods to open data
        if self.sstype==SSType.POINT:
            def open(fname):
                return xr.open_dataset(fname).sel(lat=self.args.latitude,lon=self.args.longitude,method='nearest').drop_vars(['4326']) 
        elif self.sstype==SSType.BBOX:
            def open(fname):
                ds = xr.open_dataset(fname).drop_vars(['4326'])
                return utils.mask_ds_bbox(ds,
                                          np.min(self.args.longitude),
                                          np.max(self.args.longitude),
                                          np.min(self.args.latitude),
                                          np.max(self.args.latitude)
                )
        elif self.sstype==SSType.POLYGON:
            def open(fname):
                ds = xr.open_dataset(fname).drop_vars(['4326']) 
                return utils.mask_ds_poly(ds,
                                          self.args.latitude,
                                          self.args.longitude,
                                          self.grid_size,
                                          self.grid_size,
                                          other = OUTSIDE_AREA_SELECTION
                                          )

        # Open all dses and merge
        ds = xr.merge(open(fname) for fname in self.filepaths)

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
        # precipitation download must return a baseline time series because this is a requirement of the outsourced spi calculation algorithm
        super().__init__(config, args)
        
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
        datxr = xr.open_dataset(self.download_obj.download_file_path)

        if 'expver' in datxr.keys():
            datxr = datxr.sel(expver=1,drop=True)

        self.logger.debug("Xarray:")
        self.logger.debug(datxr)

        # Convert to monthly sums and extract max of the available cells
        if self.config.aws: # or any other setting which would result in more than monthy data
            precip = datxr.tp.resample(time='1MS').sum().max(['latitude', 'longitude']).load()
        else:
            precip = datxr.tp.max(['latitude', 'longitude']).load()

        self.logger.info("Input precipitation, {} values: {:.3f} {:.3f} ".format(len(precip.values), np.nanmin(precip.values), np.nanmax(precip.values)))

        # Calculate SPI
        spi = indices.INDICES()
        spi_vals = spi.calc_spi(np.array(precip.values).flatten())
        self.logger.info("SPI, {} values: {:.3f} {:.3f}".format(len(spi_vals), np.nanmin(spi_vals),np.nanmax(spi_vals)))

        # Convert xarray to dataframe Series and add SPI
        df = precip.to_dataframe()
        df['spi'] = spi_vals
        #df = df.reset_index(level=[1,2])
        self.logger.debug("DF: ")
        self.logger.debug(df.head())

        # Select requested time slice
        self.logger.debug("Filtering between {} and {}".format(self.args.start_date, self.args.end_date))
        self.logger.debug("Index: {}".format(df.index[0]))
        df_filtered = utils.crop_df(df,self.args.start_date,self.args.end_date)

        return df_filtered
    
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
        df_filtered = self.convert_precip_to_spi()

        # Fill any missing gaps
        time_months = pd.date_range(self.args.start_date,self.args.end_date,freq='1MS')
        df_filtered = utils.fill_gaps(time_months,df_filtered)

        # store processed data on object
        self.data = df_filtered

        self.generate_output()

        return df_filtered

class SPI_GDO(GDODroughtIndex):
    """
    Specialisation of the GDODrought class for processing pre-computed photosynthetically active radiation anomaly data from GDO.
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        super().__init__(config,args,GDO_SPI_GRID,'spg03')

    def process(self):
        df = super().load_and_trim()

        # Fill any data gaps
        time_months = pd.date_range(self.args.start_date,self.args.end_date,freq='1MS')
        df = utils.fill_gaps(time_months,df)

        self.data = df
        self.generate_output()

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
        super().__init__(config,args)
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

        # Reduce monthly data to what's relevant
        if 'expver' in monthly_swv.keys():
            monthly_swv = monthly_swv.isel(expver=0).drop_vars('expver')

        monthly_swv = monthly_swv.mean(('latitude','longitude'))
        swv_mean = monthly_swv.mean('time')
        swv_std = monthly_swv.std('time')

        # Resmple sample data to dekafs
        sample_swv = sample_swv.drop_vars(['lat','lon'] if self.config.era_daily else ['latitude','longitude']).to_dataframe()
        swv_dekads = utils.df_to_dekads(sample_swv)
        
        # Calculate zscores
        for layer in [1,2,3,4]:
            col = 'swvl' + str(layer)
            swv_dekads['zscore_' + col] = ((swv_dekads[col] - swv_mean[col].item()) / swv_std[col].item())

        # fill any data gaps
        time_dekads = utils.dti_dekads(self.args.start_date,self.args.end_date)
        swv_dekads = utils.fill_gaps(time_dekads,swv_dekads)

        self.logger.info("Completed processing of ERA5 soil water data.")

        self.data = swv_dekads

        # Output to JSON
        self.generate_output()

        return swv_dekads

class SMA_GDO(GDODroughtIndex):
    """
    Specialisation of the GDODrought class for processing pre-computed soil moisture anomaly from GDO.
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        super().__init__(config,args,GDO_SMA_GRID,['smant','smand'])

    def process(self):
        df = super().load_and_trim()

        # smand is the modelled data and is available more recently than the long term time series of smant
        # replace missing smant values with smand and discard
        if 'smand' in list(df.columns):
            df.smant.fillna(df.smand, inplace=True)
            del df['smand']

        # Fill any data gaps
        time_dekads = utils.dti_dekads(self.args.start_date,self.args.end_date)
        df = utils.fill_gaps(time_dekads,df)

        self.data = df
        self.generate_output()

        return df

class FPAR_GDO(GDODroughtIndex):
    """
    Specialisation of the GDODrought class for processing pre-computed photosynthetically active radiation anomaly data from GDO.
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        super().__init__(config,args,GDO_FPR_GRID,'fpanv')
    
    def process(self):
        df = super().load_and_trim()

        # Fill any data gaps
        time_dekads = utils.dti_dekads(self.args.start_date,self.args.end_date)
        df = utils.fill_gaps(time_dekads,df)

        self.data = df
        self.generate_output()

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
        super().__init__(cfg,args)

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

        # Process individual indices if not already done
        df_spi = self.spi.process() if len(self.spi.data) == 0 else self.spi.data
        df_sma = self.sma.process() if len(self.sma.data) == 0 else self.sma.data
        df_fpr = self.fpr.process() if len(self.fpr.data) == 0 else self.fpr.data

        # Put these into a new df with the required time bounds
        spi_filled = utils.crop_df(utils.fill_gaps(self.time_dekads,df_spi).fillna(method='ffill'),self.time_dekads[0],self.time_dekads[-1])
        sma_filled = utils.crop_df(utils.fill_gaps(self.time_dekads,df_sma),self.time_dekads[0],self.time_dekads[-1])
        fpr_filled = utils.crop_df(utils.fill_gaps(self.time_dekads,df_fpr),self.time_dekads[0],self.time_dekads[-1])

        self.df_merged =  pd.concat([spi_filled,sma_filled,fpr_filled],axis=1)

        # Now shift each column by number of dekads we need to go back to compute CDI
        spi_shifted = spi_filled.shift(3)
        sma_shifted = sma_filled.shift(2)
        fpr_shifted = fpr_filled.shift(1)
        self.sma_shifted = sma_shifted
        self.fpr_shifted = fpr_shifted

        self.df_shifted = pd.concat([spi_shifted,sma_shifted,fpr_shifted],axis=1)

        # Now create CDI with following levels:
        # 0: no warning
        # 1: watch = spi < -1
        # 2: warning = sma < -1 and spi < -1
        # 3: alert 1 = fpr < -1 and spi < -1
        # 4: alert 2 = all < -1

        def calc_cdi(r):
            spi_ = r[self.args.spi_var] < -1
            sma_ = r[self.args.sma_var] < -1
            fpr_ = r[self.args.fpr_var] < -1
            if r.isna().any():
                return np.nan
            elif spi_ and sma_ and fpr_:
                return 4
            elif spi_ and fpr_:
                return 3
            elif spi_ and sma_:
                return 2
            elif spi_:
                return 1
            else:
                return 0
            
        cdi = self.df_shifted.apply(calc_cdi,axis=1)

        df = self.df_shifted
        df['CDI'] = cdi
        
        self.data = df

        # Output to JSON
        if not os.path.isfile(self.output_file_path):
            self.generate_output()

        self.logger.info("Completed processing of ERA5 CDI data.")
        return df
    

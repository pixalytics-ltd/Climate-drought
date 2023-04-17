import logging
import os
import numpy as np
import pandas as pd
import xarray as xr
import json
import geojson
import glob
import datetime
from dateutil.relativedelta import relativedelta

from climate_drought import indices, config, utils, era5_request as erq

# pygeometa for OGC API record creation
import yaml
import ast
import re
from pygeometa.core import read_mcf
from pygeometa.schemas.ogcapi_records import OGCAPIRecordOutputSchema

from abc import ABC, abstractclassmethod
from typing import List, Union

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

        # set up logger
        self.logger = logging.basicConfig(filename='{0}/log_{1}.txt'.format(config.outdir,datetime.datetime.now()),level=logging.DEBUG)
        self.logger = logging.getLogger("ERA5_Processing")
        self.logger.setLevel(logging.DEBUG) if config.verbose else self.logger.setLevel(logging.INFO)

        # set data to empty df as an indicator that this hasn't been processed yet
        self.data = pd.DataFrame()

    @property
    def index_shortname(self):
        return  type(self).__name__.replace('_','-')

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
        super().__init__(config, args)
        
        # create era5 request object
        request = erq.ERA5Request(erq.PRECIP_VARIABLES, 'precip', self.args, self.config, start_date=config.baseline_start, end_date=config.baseline_end)

        # initialise the download object using the request, but don't download yet
        self.download_obj = erq.ERA5Download(request,self.logger)

    def download(self):
        """
        Download requried data from ERA5 portal using the imported ERA5 request module.
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
        #if not self.args.accum:
        # TODO JC reinstate this for SPI but at the moment we're just using monthly data so accum will never be true
        precip = datxr.tp.max(['latitude', 'longitude']).load()
        #else:
        #resamp = datxr.tp.resample(time='1MS').sum().max(['latitude', 'longitude']).load()

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
        df_filtered = utils.crop_df(df,self.args.start_date,self.args.end_date)#df.loc[(df.index >= self.args.start_date) & (df.index <= self.args.end_date)]

        return df_filtered
    

    def process(self) -> str:
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
        # Monthly for SPI - ASSUMES SPI data is always at the start of each month. TODO JC5 make sure this is the case and fix if not
        time_months = pd.date_range(self.args.start_date,self.args.end_date,freq='1MS')
        df_filtered = utils.fill_gaps(time_months,df_filtered)

        if not os.path.isfile(self.output_file_path):
            self.generate_geojson(df_filtered)

        # store processed data on object
        self.data = df_filtered

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
            end_date=config.baseline_end)
        
        self.download_obj_baseline = erq.ERA5Download(request_baseline, self.logger)

        #create era5 request object for short term period
        request_shorterm = erq.ERA5Request(
            erq.SOILWATER_VARIABLES,
            'soilwater',
            self.args,
            self.config,
            args.start_date,
            args.end_date,
            monthly=False)
        
        self.download_obj_hourly = erq.ERA5Download(request_shorterm, self.logger)
    
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
        exists_or_download(self.download_obj_hourly)

        return [self.download_obj_baseline.download_file_path, self.download_obj_hourly.download_file_path]

    def process(self) -> str:
        """
        Carries out processing of the downloaded data.  This is the main functionality that is likely to differ between
        each implementation.
        :return: path to the output file generated by the algorithm
        """
        self.logger.info("Initiating processing of ERA5 soil water data.")

        path_monthly = self.download_obj_baseline.download_file_path
        path_hourly = self.download_obj_hourly.download_file_path

        if not os.path.isfile(path_monthly):
            raise FileNotFoundError("Unable to locate downloaded data '{}'.".format(path_monthly))
        
        if not os.path.isfile(path_hourly):
            raise FileNotFoundError("Unable to locate downloaded data '{}'.".format(path_hourly))

        # Open netcdfs
        monthly_swv = xr.open_dataset(path_monthly)
        hourly_swv = xr.open_dataset(path_hourly).squeeze()

        # Reduce monthly data to what's relevant
        if 'expver' in monthly_swv.keys():
            monthly_swv = monthly_swv.isel(expver=0).drop_vars('expver')
        monthly_swv = monthly_swv.mean(('latitude','longitude'))
        swv_mean = monthly_swv.mean('time')
        swv_std = monthly_swv.std('time')

        # Resmple hourly data to dekafs
        hourly_swv = hourly_swv.drop_vars(['latitude','longitude']).to_dataframe()
        swv_dekads = utils.df_to_dekads(hourly_swv)
        
        # Calculate zscores
        for layer in [1,2,3,4]:
            col = 'swvl' + str(layer)
            swv_dekads['zscore_' + col] = ((swv_dekads[col] - swv_mean[col].item()) / swv_std[col].item())

        # fill any data gaps
        time_dekads = utils.dti_dekads(self.args.start_date,self.args.end_date)
        swv_dekads = utils.fill_gaps(time_dekads,swv_dekads)

        # Output to JSON
        self.generate_geojson(swv_dekads)

        self.logger.info("Completed processing of ERA5 soil water data.")

        self.data = swv_dekads

        return swv_dekads

class SMA_GDO(DroughtIndex):
    """
    Specialisation of the Drought class for processing pre-downlaoded soil moisture anomaly data from EDO.
    Requires that you have downladed all years of 'Ensemble Soil Moisture Anomaly' and 'Ensemble Soil Moisture Anomaly (2M, Lisflood...' 
    from https://edo.jrc.ec.europa.eu/gdo/php/index.php?id=2112 and stored them in the 'input' folder as specified in the Config object
    i.e. Ensemble moisture data must all be in /inputs/smant
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        super().__init__(config,args)
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

        # fill any data gaps
        time_dekads = utils.dti_dekads(self.args.start_date,self.args.end_date)
        df = utils.fill_gaps(time_dekads,df)
        
        # Output to JSON
        if not os.path.isfile(self.output_file_path):
            self.generate_geojson(df)

        self.logger.info("Completed processing of ERA5 soil water data.")

        self.data = df

        return df

class FPAR_GDO(DroughtIndex):
    """
    Specialisation of the Drought class for processing pre-downlaoded photosynthetically active radiation anomaly data from EDO.
    Requires that you have downladed all years of 'Fraction of Absorbed Photo....' and 'Fraction of Absorbed.... (VIIRS)' 
    from https://edo.jrc.ec.europa.eu/gdo/php/index.php?id=2112 and stored them in the 'input' folder as specified in the Config object
    i.e. data must all be in /inputs/fpanv
    """
    def __init__(self, config: config.Config, args: config.AnalysisArgs):
        super().__init__(config,args)
        self.files_loc = config.indir + '/fpanv'
        self.filelist = glob.glob(self.files_loc + '/fpanv*.nc')

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
        # replace missing fpanv values (which are better quality data?) with fapan
        # df.fpanv.fillna(df.fapan, inplace=True)
        # del df['fapan']

        # fill any data gaps
        time_dekads = utils.dti_dekads(self.args.start_date,self.args.end_date)
        df = utils.fill_gaps(time_dekads,df)
        
        # Output to JSON
        if not os.path.isfile(self.output_file_path):
            self.generate_geojson(df)

        self.logger.info("Completed processing of ERA5 fAPAR data.")

        self.data = df

        return df

class CDI(DroughtIndex):

    """
    Extension of base class for combined drought indicator
    Can initialise from scratch or using existing index objects
    """
    def __init__(
            self,
            cfg: config.Config,
            args: config.AnalysisArgs,
            sma_source: str = 'EDO',
            spi: SPI = None,
            sma: Union[SMA_ECMWF,SMA_GDO] = None,
            fpr: FPAR_GDO = None
            ):
        super().__init__(cfg,args)

        # Initialise all separate indicators to be combined
        sdate_ts = pd.Timestamp(args.start_date)
        sdate_dk = sdate_ts.replace(day=utils.nearest_dekad(sdate_ts.day))
        def create_new(idx: DroughtIndex, required_sdate: pd.Timestamp, name: str) -> bool:
            """
            Determine if we need to create a new index or use the one provided
            """
            if (idx is not None):
                if (idx.data.index[0] <= required_sdate <= idx.data.index[-1]):
                    return False
                else:
                    self.logger.info('{0} provided does not meet timing requirements: requried start {1} not within data time bounds {2} to {3}'.format(name,required_sdate,args.start_date,args.end_date))
                    self.logger.info('Creating new {} object...'.format(name))
                    return True
            else:
                self.logger.info('No {0} provided.'.format(name))
                self.logger.info('Creating new {} object...'.format(name))
                return True
            
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
        self.spi = SPI(cfg,aa_new(sdate_spi)) if create_new(spi,sdate_spi,'SPI') else spi
            
        # SMA: 2 dekads before
        sdate_sma = sdate_dk - relativedelta(days=20)
        sma_class = SMA_ECMWF if sma_source=='ECMWF' else SMA_GDO
        self.sma = sma_class(cfg,aa_new(sdate_sma)) if create_new(sma,sdate_sma,'SMA') else sma
         
        # fAPAR - 1 dekad before
        sdate_fpr = sdate_dk - relativedelta(days=10)
        self.fpr = FPAR_GDO(cfg,aa_new(sdate_fpr)) if create_new(fpr,sdate_fpr,'fAPAR') else fpr
        
        # Initialise times
        # We want our final timeseries to include all data from the beginning of the SPI to the end of the CDI, so all data can be retained
        self.time_dekads = utils.dti_dekads(sdate_dk,args.end_date)

    def download(self):
        self.spi.download()
        self.sma.download()
        self.fpr.download()
        
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
        self.fpr_shifted = fpr_shifted

        self.df_shifted = pd.concat([spi_shifted,sma_shifted,fpr_shifted],axis=1)

        # Now create CDI with following levels:
        # 0: no warning
        # 1: watch = spi < -1
        # 2: warning = sma < -1 and spi < -1
        # 3: alert 1 = fpr < -1 and spi < -1
        # 4: alert 2 = all < -1

        anyna = self.df_shifted.isna().any(axis=1).to_numpy()
        spi_warn = (spi_shifted < -1).to_numpy().flatten()
        sma_warn = (sma_shifted < -1).to_numpy().flatten()
        fpr_warn = (fpr_shifted < -1).to_numpy().flatten()

        cdi = []
        for spi_, sma_, fpr_, anyna_ in zip(spi_warn,sma_warn,fpr_warn, anyna):
            if anyna_:
                cdi.append(np.nan)
            elif spi_ and sma_ and fpr_:
                cdi.append(4) # alert 2
            elif spi_ and fpr_:
                cdi.append(3) # alert 1
            elif spi_ and sma_:
                cdi.append(2) # warning
            elif spi_:
                cdi.append(1) # watch
            else:
                cdi.append(0) # normal

        df = self.df_shifted
        df['CDI'] = cdi
        
        # Output to JSON
        if not os.path.isfile(self.output_file_path):
            self.generate_geojson(df)

        self.logger.info("Completed processing of ERA5 CDI data.")
        self.data = df
        return df
    
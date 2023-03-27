import logging
import os
import numpy as np
from typing import List
from datetime import date, time
# handling NetCDF files
import xarray
import json
import geojson
from climate_drought import indices, utils
import matplotlib.pyplot as plt
# ERA download
from pixutils import era_download
# pygeometa for OGC API record creation
import yaml
import ast
import re
from pygeometa.core import read_mcf
from pygeometa.schemas.ogcapi_records import OGCAPIRecordOutputSchema
from abc import ABC, abstractmethod

# Logging
logging.basicConfig(level=logging.DEBUG)

# ERA5 download range
Sdate = '19850101'
Edate = '20221231'


class Era5ProcessingBase(ABC):
    """
    Provides some basic functionality that can be used by different implementation specific strategies for different
    data sources
    """

    #   target download time for each data source
    SAMPLE_TIME = time(hour=12, minute=0)

    def __init__(self, args, variables: List[str], working_dir: str):
        """
        Initializer; should be called by derived classes
        :param args: program arguments
        :param working_dir: directory that will hold all files generated by the class
        """
        self.logger = logging.getLogger("ERA5_Processing")
        self.logger.setLevel(logging.DEBUG) if args.verbose else self.logger.setLevel(logging.INFO)
        self.args = args
        self.variables = variables

        # Create list of dates between max start and end dates
        dates = utils.daterange(Sdate, Edate, 0)
        date_list = []
        for i,indate in enumerate(dates):
            self.args.year = int(indate[0:4])
            self.args.month = int(indate[4:6])
            self.args.day = int(indate[6:8])
            date_list.append(date(self.args.year, self.args.month, self.args.day))
        self.args.dates = date_list
        self.working_dir = working_dir

    @property
    def download_file_path(self):
        """
        Returns the path to the file that will be downloaded
        :return: path to the file that will be downloaded
        """
        freq = 'hourly' if self.args.accum else 'monthly'
        file_str = "{sd}-{ed}_{fq}_{la}_{lo}".format(sd=Sdate, ed=Edate, fq=freq, la=self.args.latitude, lo=self.args.longitude)
        return os.path.join(self.working_dir, self.fname_nc + "_{d}.nc".format(d=file_str))
    

    def download(self) -> str:
        """
        This function handles downloading from the Copernicus Climate Service.
        Functionality should be suitable for most uses, but can be overridden by derived classes for more specialised
        downloads
        :return: path to the file containing the downloaded data
        """
        self.logger.info("Initiating download of ERA5 data.")
        self.logger.info("Variables to be downloaded: {}.".format(", ".join(self.VARIABLES)))

        # Setup area of interest extraction
        boxsz = 0.1
        area_box = []
        area_box.append(self.args.latitude + boxsz)
        area_box.append(self.args.longitude - boxsz)
        area_box.append(self.args.latitude - boxsz)
        area_box.append(self.args.longitude + boxsz)

        if self.args.accum:
            times = []
            for i in range(24):
                times.append(time(hour=i, minute=0))
        else:
            times = [self.SAMPLE_TIME]

        self._download_era5_data(variables=self.VARIABLES,
                                 dates=self.args.dates,
                                 times=times,
                                 area=area_box,
                                 monthly=not self.args.accum,
                                 out_file=self.download_file_path)

        if os.path.isfile(self.download_file_path):
            self.logger.info("ERA5 data was downloaded to '{}'.".format(self.download_file_path))
        else:
            raise FileNotFoundError("ERA5 download file '{}' was missing.".format(self.download_file_path))

        return self.download_file_path

    def _download_era5_data(self, variables: List[str], dates: List[date], times: List[time], area: str, monthly: str, out_file: str) -> None:

        """
        Executes the ERA5 download script in a separate process.
        :param variables: a list of variables to be downloaded from the Copernicus Climate Data Store.
        :param dates: a list of dates to download data for
        :param times: a list of times to download data for
        :param area: area of interest box to download data for
        :param monthly: download monthly reanalysis data
        :param out_file: output_file_path: path to the output file containing the requested fields.  Supported output format is NetCDF, determined by file extension.
        :return: nothing
        """

        if not os.path.exists(out_file):
            if monthly:
                era_monthly = True
            else:
                era_monthly = False

            self.logger.info("Downloading ERA data for {} {} for {}".format(dates[0],dates[-1],area))
            result = era_download.download_era5_reanalysis_data(dates=dates, times=times, variables=variables, area=str(area),
                                          monthly=era_monthly, file_path=os.path.expanduser(out_file))

            if result == 0:
                raise RuntimeError("Download process returned unexpected non-zero exit code '{}'.".format(result))

        if not os.path.isfile(out_file):
            raise FileNotFoundError("Output file '{}' could not be located.".format(out_file))

    @abstractmethod
    def process(self):
        pass

class Era5ProcessingWithJsonOutput(Era5ProcessingBase):
    """
    Specialisation of the base class for downloading and processing data
    """

    @property
    def output_file_path(self):
        """
        Returns the path to the output file from processing
        :return: path to the output file
        """
        file_str = "{sd}-{ed}_{la}_{lo}".format(sd=self.args.start_date, ed=self.args.end_date, la=self.args.latitude, lo=self.args.longitude)
        return os.path.join(self.working_dir, self.fname_json + "_{d}.json".format(d=file_str))

    def __init__(self, args, variables: List[str], working_dir: str, fname_nc: str, fname_json: str):
        """
        Initializer.  Forwards parameters to super class.
        :param args: program arguments
        :param working_dir: directory that will hold all files generated by the class
        """
        super().__init__(args=args, variables=variables, working_dir=working_dir)

        self.fname_nc = fname_nc
        self.fname_json = fname_json

        self.logger.debug("Initiated ERA5 daily processing of temperature strategy.")

    def download(self) -> str:
        """
        Performs file downloads.  Currently uses the basic functionality offered by the base class
        :return: path to the file containing the downloaded data
        """
        return super().download()

    def generate_geojson(self) -> None:
        """
         Generates GeoJSON file for data
         :return: path to the geojson file
         """
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
        float_bbox = '[{:.3f},{:.3f},{:.3f},{:.3f}]'.format(float(self.args.longitude)-0.1, float(self.args.latitude)-0.1, float(self.args.longitude)+0.1, float(self.args.latitude)+0.1)
        yaml_dict.update({'bbox': ast.literal_eval(float_bbox)})
        #yaml_dict.update({'crs': ast.literal_eval(dst_crs.split(":")[1])})

        # remove single quotes
        res = {key.replace("'", ""): val for key, val in yaml_dict.items()}
        dataMap['identification']['extents']['spatial'] = [res]
        self.logger.info("Modified dataMap: {} ".format(dataMap['identification']['extents']['spatial']))

        # Update dates
        self.logger.debug("dataMap: {} ".format(dataMap['identification']['extents']['temporal']))
        fdate = self.json_file.split("_")[0]
        date_string = self.args.dates[0].strftime("%Y-%m-%d")
        end_date_string = self.args.dates[-1].strftime("%Y-%m-%d")

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

class Era5PrecipProcessing(Era5ProcessingWithJsonOutput):
    """
    Specialisation of the json base class for downloading and processing precipitation data
    """
        #   variables to be downloaded using the API
    VARIABLES = ["total_precipitation"]

    def __init__(self, args, working_dir: str):
        """
        Initializer.  Forwards parameters to super class.
        :param args: program arguments
        :param working_dir: directory that will hold all files generated by the class
        """
        super().__init__(args=args, variables=self.VARIABLES, working_dir=working_dir,fname_nc='precip',fname_json='spi')
        self.logger.debug("Initiated ERA5 daily processing of temperature strategy.")

    def convert_precip_to_spi(self) -> None:
        """
        Calculates SPI precipitation drought index
        :param input_file_path: path to file containing precipitation
        :param output_file_path: path to file to be written containing SPI
        :return: nothing
        """

        # Extract data from NetCDF file
        datxr = xarray.open_dataset(self.download_file_path)
        self.logger.debug("Xarray:")
        self.logger.debug(datxr)

        # Convert to monthly sums and extract max of the available cells
        # group('time.month') is 1 to 12 while resamp is monthly data
        if self.args.accum:
            resamp = datxr.tp.max(['latitude', 'longitude']).load()
        else:
            resamp = datxr.tp.resample(time='1MS').sum().max(['latitude', 'longitude']).load()
        precip = resamp[:, 0]

        self.logger.info("Input precipitation, {} values: {:.3f} {:.3f} ".format(len(precip.values), np.nanmin(precip.values), np.nanmax(precip.values)))

        # Calculate SPI
        spi = indices.INDICES(self.args)
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
        sdate = r'{}-{}-{}'.format(self.args.start_date[0:4],self.args.start_date[4:6],self.args.start_date[6:8])
        edate = r'{}-{}-{}'.format(self.args.end_date[0:4],self.args.end_date[4:6],self.args.end_date[6:8])
        self.logger.debug("Filtering between {} and {}".format(sdate, edate))
        df_filtered = df.loc[(df.index >= sdate) & (df.index <= edate)]

        # Convert date/time to string and then set this as the index
        df_filtered['StartDateTime'] = df_filtered.index.strftime('%Y-%m-%dT00:00:00')
        #df_filtered = df_filtered.reset_index(drop=True)
        #df_filtered = df_filtered.set_index('day')
       #df_filtered = df_filtered.drop(['latitude'], axis=1)
        #df_filtered = df_filtered.drop(['longitude'], axis=1)
        # Remove any NaN values
        df_filtered = df_filtered[~df_filtered.isnull().any(axis=1)]
        self.logger.debug("Updated DF: ")
        self.logger.debug(df_filtered.head())

        # Scatter plot
        if self.args.plot:
            fig = plt.figure(dpi=900)
            ax1 = df_filtered['tp'].plot(label='Total precip')
            ax2 = df_filtered['spi'].plot(secondary_y = True, label='SPI')
            ax1.set_xlabel('Time')
            ax1.set_ylabel('Total Precipitation [m, blue]')
            ax2.set_ylabel('Standardized Precipitation Index (SPI, orange)')
            ax1.grid(True, linestyle = ':')
            ax2.grid(True, linestyle=':')
            pngfile = os.path.join(os.path.dirname(self.output_file_path),"{}-plot.png".format(self.args.product))
            self.logger.debug("PNG: {}".format(pngfile))
            plt.savefig(pngfile)

        # Build GeoJSON object
        self.feature_collection = {"type": "FeatureCollection", "features": []}

        for i in df_filtered.index:
            feature = {"type": "Feature", "geometry": {"type": "Point", "coordinates": [self.args.longitude, self.args.latitude]}, "properties": {}}

            # Extract columns as properties
            property = df_filtered.loc[i].to_json(date_format='iso', force_ascii = True)
            parsed = json.loads(property)
            print("Sam: ",parsed)
            feature['properties'] = parsed

            # Add feature
            self.feature_collection['features'].append(feature)

        # Generate output file
        self.generate_geojson()

    def process(self) -> str:
        """
        Carries out processing of the downloaded data.  This is the main functionality that is likely to differ between
        each implementation.
        :return: path to the output file generated by the algorithm
        """
        self.logger.info("Initiating processing of ERA5 daily data.")

        if not os.path.isfile(self.download_file_path):
            raise FileNotFoundError("Unable to locate downloaded data '{}'.".format(self.download_file_path))

        # Calculates SPI precipitation drought index
        self.convert_precip_to_spi()

        return self.output_file_path
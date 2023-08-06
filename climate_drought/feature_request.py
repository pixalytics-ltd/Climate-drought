import logging
import os
from typing import List
from datetime import date, time
import numpy as np
# Configuration
from climate_drought import utils, config
# Feature download
from requests import Request
import geopandas as gpd

# Logging
logging.basicConfig(level=logging.INFO)

# Shared constants
BOX_SIZE = 0.1

# SAFE server
URL = "https://disasterpilot-dean.fmecloud.com/fmedatastreaming/OGCAPI/collections.fmw/collection"

PRECIP_VARIABLES = ['total_precipitation']
SOILWATER_VARIABLES = ["volumetric_soil_water_layer_1", "volumetric_soil_water_layer_2",
                       "volumetric_soil_water_layer_3", "volumetric_soil_water_layer_4"]

class FeatureRequest():
    """
    Object to constrain SAFE Feature inputs.
    Built inputs using analysis and config arguments.
    """
    def __init__(self, variables, fname_out, args: config.AnalysisArgs, config: config.Config,
                 start_date, end_date):

        bbox = len(args.longitude)>1
        self.minlat = np.min(args.latitude) if bbox else float(args.latitude[0]) - BOX_SIZE
        self.minlon = np.min(args.longitude) if bbox else float(args.longitude[0]) - BOX_SIZE

        self.maxlat = np.max(args.latitude) if bbox else float(args.latitude[0]) + BOX_SIZE
        self.maxlon = np.max(args.longitude) if bbox else float(args.longitude[0]) + BOX_SIZE

        self.bbox = bbox

        self.start_date = start_date
        self.end_date = end_date
        self.variables = variables
        self.working_dir = config.outdir
        self.fname_out = fname_out
        self.verbose = config.verbose

class FeatureDownload():
    """
    Provides some basic functionality that can be used by different implementation specific strategies for different
    data sources
    """

    def __init__(self, req: FeatureRequest, logger: logging.Logger):
        self.logger = logger
        self.req = req

        # Create list of dates between max start and end dates
        dates = utils.daterange(self.req.start_date, self.req.end_date, 0)
        date_list = []
        for indate in dates:
            yyyy = int(indate[0:4])
            mm = int(indate[4:6])
            dd = int(indate[6:8])
            date_list.append(date(yyyy, mm, dd))
        self.dates = date_list

    @property
    def download_file_path(self):
        """
        Returns the path to the file that will be downloaded
        :return: path to the file that will be downloaded
        """

        latstr = str("{0:.2f}".format(self.req.minlat)) + '-' + str("{0:.2f}".format(self.req.maxlat))
        lonstr = str("{0:.2f}".format(self.req.minlon)) + '-' + str("{0:.2f}".format(self.req.maxlon))

        file_str = "{sd}-{ed}_{la}_{lo}_{fq}".format(sd=self.req.start_date,
                                                     ed=self.req.end_date,
                                                     la=latstr,
                                                     lo=lonstr,
                                                     fq=self.req.frequency.value)
    
        return os.path.join(self.req.working_dir, self.req.fname_out + "_{d}.nc".format(d=file_str))

    def download(self) -> str:
        """
        This function handles downloading from a Feature Server.
        Functionality should be suitable for most uses, but can be overridden by derived classes for more specialised
        downloads
        :return: path to the file containing the downloaded data
        """
        self.logger.info("Initiating download of Feature data.")
        self.logger.info("Variables to be downloaded: {}.".format(", ".join(self.req.variables)))

        area_box = [round(self.req.maxlat,2),
                    round(self.req.minlon,2),
                    round(self.req.minlat,2),
                    round(self.req.maxlon,2)
        ]

        self.download_feature_data(
            variables=self.req.variables,
            dates=self.dates,area=area_box,
            out_file=self.download_file_path)

        if os.path.isfile(self.download_file_path):
            self.logger.info("Feature data was downloaded to '{}'.".format(self.download_file_path))
        else:
            raise FileNotFoundError("Feature download file '{}' was missing.".format(self.download_file_path))

        return self.download_file_path

    def download_feature_data(self, variables: List[str], dates: List[date], area: List[float],out_file: str) -> bool:

        """
        Executes the Feature download script in a separate process.
        :param variables: a list of variables to be downloaded from the SAFE Feature server.
        :param dates: a list of dates to download data for
        :param area: area of interest box to download data for
        :param out_file: output_file_path: path to the output file containing the requested fields.
        :return: nothing
        """
        outfile_exists = False

        if not os.path.exists(out_file):

            self.logger.info("Downloading Feature data for {} {} for {}".format(dates[0], dates[-1], area))

            features = "?&service=WFS&request=GetFeature&typename={}".format(variables[0])
            full_url = os.path.join(URL,features)
            q = Request('GET', full_url).prepare().url
            df = gpd.read_file(q, format='GeoJSON')
            df.crs = 'EPSG:4326'

            result = xxxx

            if result == 0:
                raise RuntimeError("Download process returned unexpected non-zero exit code '{}'.".format(result))

        else:
            self.logger.info("Download file '{}' already exists.".format(out_file))
            outfile_exists = True

        if not os.path.isfile(out_file):
            raise FileNotFoundError("Output file '{}' could not be located.".format(out_file))

        return outfile_exists


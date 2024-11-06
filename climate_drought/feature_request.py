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
import geojson

TINTERVAL = [ "2020-01-16T14:51:12Z", "2031-01-01T19:15:35Z" ]
BBOX=[ -137.1584, 25.8242, -46.2405, 59.1733 ]

# Logging
logging.basicConfig(level=logging.INFO)

# Shared constants
BOX_SIZE = 0.1

# SAFE server
URL = "https://disasterpilot-dean.fmecloud.com/fmedatastreaming/OGCAPI/"

FEATURE_VARIABLES = ['climateECV_querier_MB_precip.fmw','climateECV_querier_MB_temp.fmw']

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

    def download(self) -> str:
        """
        This function handles downloading from a Feature Server.
        Functionality should be suitable for most uses, but can be overridden by derived classes for more specialised
        downloads
        :return: path to the file containing the downloaded data
        """
        self.logger.info("Initiating download of Feature data.")
        self.logger.info("Variables to be downloaded: {}.".format(", ".join(self.req.variables)))

        area_box = [round(self.req.minlon,2),
                    round(self.req.minlat,2),
                    round(self.req.maxlon,2),
                    round(self.req.maxlat,2)
        ]

        # Check requested area overlaps with server's bounding box
        overlap,union,iou = utils.calculate_iou(area_box, BBOX)
        # Check dates are within dataset time interval

        start_int = date.fromisoformat(TINTERVAL[0].split("T")[0])
        end_int = date.fromisoformat(TINTERVAL[1].split("T")[0])
        sdate = date(int(self.req.start_date[0:4]),int(self.req.start_date[4:6]),int(self.req.start_date[6:8]))
        edate = date(int(self.req.end_date[0:4]), int(self.req.end_date[4:6]), int(self.req.end_date[6:8]))
        print("{} within {} {}".format(self.req.start_date,TINTERVAL[0],TINTERVAL[1]))

        if iou > 0 and (sdate <= end_int) and (edate >= start_int):
            self.download_feature_data(
                variables=self.req.variables,
                dates=self.dates,area=area_box,
                out_file=self.req.fname_out)
        else:
            raise Exception("The requested bounding box {} is not covered by the dataset {} or the dates {} {} are not sufficiently covered bt the time interval {} {}".format(area_box, BBOX, self.req.start_date, self.req.end_date,TINTERVAL[0],TINTERVAL[1]))

        if os.path.isfile(self.req.fname_out):
            self.logger.info("Feature data was downloaded to '{}'.".format(self.req.fname_out))
        else:
            raise FileNotFoundError("Feature download file '{}' was missing.".format(self.req.fname_out))

        return self.req.fname_out

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

            #bbox = -99.0 49.0 -96.0 50.0
            features = "{}?StartYear={}&EndYear={}&bbox={},{},{},{}&limit=10000".format(FEATURE_VARIABLES[0],dates[0].year,dates[-1].year,area[0],area[1],area[2],area[3])

            full_url = URL+features
            self.logger.info("SME request: {}".format(full_url))
            try:
                q = Request('GET', full_url).prepare().url
                df = gpd.read_file(q, format='GeoJSON')
                #df.crs = 'EPSG:4326'
                self.logger.info("SAM Extracted data: {}".format(df))

                with open(out_file, "w", encoding='utf-8') as outfile:
                    geojson.dump(df, outfile, indent=4)

                result = 1
            except:
                result = 0

            if result == 0:
                raise RuntimeError("Download process returned unexpected non-zero exit code '{}'.".format(result))

        else:
            self.logger.info("Download file '{}' already exists.".format(out_file))
            outfile_exists = True

        if not os.path.isfile(out_file):
            raise FileNotFoundError("Output file '{}' could not be located.".format(out_file))

        return outfile_exists


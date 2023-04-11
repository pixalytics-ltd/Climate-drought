import logging
import os
from typing import List
from datetime import date, time
# handling NetCDF files
from climate_drought import utils, config
# ERA download
from pixutils import era_download

# Logging
logging.basicConfig(level=logging.DEBUG)

# Shared constants
PRECIP_VARIABLES = ['total_precipitation']
SOILWATER_VARIABLES = ["volumetric_soil_water_layer_1","volumetric_soil_water_layer_2","volumetric_soil_water_layer_3","volumetric_soil_water_layer_4"]

class ERA5Request():
    """
    Object to constrain ERA5 download inputs.
    Built inputs using analysis and config arguments.
    Download can be either:
    - baseline = True: a monthly mean over a long time perid to form the mean or baseline against which anomalies can be computed
    - baseline = False: a monthly or hourly value to retreive data over shorter timescales
    """
    def __init__(self, variables, fname_out, args: config.AnalysisArgs, config: config.Config, start_date, end_date, monthly=True):
        self.latitude = args.latitude
        self.longitude = args.longitude
        self.start_date = start_date
        self.end_date = end_date
        self.variables = variables
        self.working_dir = config.outdir
        self.fname_out = fname_out
        self.verbose = config.verbose
        self.monthly = monthly

class ERA5Download():
    """
    Provides some basic functionality that can be used by different implementation specific strategies for different
    data sources
    """

    #   target download time for each data source
    SAMPLE_TIME = time(hour=12, minute=0)

    def __init__(self, req : ERA5Request, logger: logging.Logger):
        """
        Initializer; should be called by derived classes
        :param args: program arguments
        :param variables: era5 variables to be downloaded
        :param working_dir: directory that will hold all files geerated by the class
        :param baseline: use pre-defined start and end dates and monthly frequency to return a long-term average
        """
        self.logger = logger
        self.req = req

        # Create list of dates between max start and end dates
        dates = utils.daterange(self.req.start_date,self.req.end_date,0)
        date_list = []
        for indate in dates:
            yyyy = int(indate[0:4])
            mm = int(indate[4:6])
            dd = int(indate[6:8])
            date_list.append(date(yyyy,mm,dd))
        self.dates = date_list

    @property
    def download_file_path(self):
        """
        Returns the path to the file that will be downloaded
        :return: path to the file that will be downloaded
        """
        freq = 'monthly' if self.req.monthly else 'hourly'
        file_str = "{sd}-{ed}_{fq}_{la}_{lo}".format(sd=self.req.start_date, ed=self.req.end_date, fq=freq, la=self.req.latitude, lo=self.req.longitude)
        return os.path.join(self.req.working_dir, self.req.fname_out + "_{d}.nc".format(d=file_str))
    
    def download(self) -> str:
        """
        This function handles downloading from the Copernicus Climate Service.
        Functionality should be suitable for most uses, but can be overridden by derived classes for more specialised
        downloads
        :return: path to the file containing the downloaded data
        """
        self.logger.info("Initiating download of ERA5 data.")
        self.logger.info("Variables to be downloaded: {}.".format(", ".join(self.req.variables)))

        # Setup area of interest extraction
        boxsz = 0.1
        area_box = []
        area_box.append(float(self.req.latitude) + boxsz)
        area_box.append(float(self.req.longitude) - boxsz)
        area_box.append(float(self.req.latitude) - boxsz)
        area_box.append(float(self.req.longitude) + boxsz)

        if not self.req.monthly:
            times = []
            for i in range(24):
                times.append(time(hour=i, minute=0))
        else:
            times = [self.SAMPLE_TIME]

        if not self._download_era5_data(variables=self.req.variables,
                                 dates=self.dates,
                                 times=times,
                                 area=area_box,
                                 monthly=self.req.monthly,
                                 out_file=self.download_file_path):

            if os.path.isfile(self.download_file_path):
                self.logger.info("ERA5 data was downloaded to '{}'.".format(self.download_file_path))
            else:
                raise FileNotFoundError("ERA5 download file '{}' was missing.".format(self.download_file_path))

        return self.download_file_path

    def _download_era5_data(self, variables: List[str], dates: List[date], times: List[time], area: str, monthly: str, out_file: str) -> bool:

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
        outfile_exists = False

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
            
        else:
            self.logger.info("Download file '{}' already exists.".format(out_file))
            outfile_exists = True

        if not os.path.isfile(out_file):
            raise FileNotFoundError("Output file '{}' could not be located.".format(out_file))
        
        return outfile_exists
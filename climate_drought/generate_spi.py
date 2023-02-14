import logging
import os
import sys
from os.path import expanduser
import numpy as np
import subprocess
from pathlib import Path
from typing import List
from enum import Enum, unique, auto
from datetime import date, time, datetime
# handling NetCDF files
import xarray
import pandas as pd
import json
from climate_drought import indices, utils
import matplotlib.pyplot as plt

# Logging
logging.basicConfig(level=logging.DEBUG)

# ERA5 download range
Sdate = '19850101'
Edate = '20221231'


class Era5ProcessingBase:
    """
    Provides some basic functionality that can be used by different implementation specific strategies for different
    data sources
    """
    # Code to downloading data from the Copernicus Climate Data Store.
    # If the 'pixutils' module is installed this script should be located in the 'bin' directory of the Conda environment else setup link to pixutils

    era_download = "era_download.py"
    home = expanduser("~")
    python_env = os.path.join(home, "anaconda3/envs/climate_env/bin")
    ERA_DOWNLOAD_PY = os.path.join(python_env, era_download)
    if not os.path.exists(ERA_DOWNLOAD_PY):
        ERA_DOWNLOAD_PY = os.path.join("pixutils", era_download)

    if not os.path.exists(ERA_DOWNLOAD_PY):
        print("could not find {}, exiting".format(era_download))
        sys.exit(1)

    # Need to call from python env is not in bin folder
    if "pixutils" in ERA_DOWNLOAD_PY:
        ERA_DOWNLOAD_PY = r'{} {}'.format(os.path.join(python_env,"python"),ERA_DOWNLOAD_PY)


    #   target download time for each data source
    SAMPLE_TIME = time(hour=12, minute=0)

    def __init__(self, args, working_dir: str):
        """
        Initializer; should be called by derived classes
        :param args: program arguments
        :param working_dir: directory that will hold all files generated by the class
        """
        self.logger = logging.getLogger("ERA5_Processing")
        self.logger.setLevel(logging.DEBUG) if args.verbose else self.logger.setLevel(logging.INFO)
        self.args = args

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
    def file_str(self) -> str:
        """
        Utility function to convert date and location to a defined string format
        :return: a date string formatted as "YYYY-MM" or "YYYY-MM-DD", depending on if a day is specified, and latitude/longitude coordinates
        """
        return "{sd}-{ed}_{la}_{lo}".format(sd=self.args.start_date, ed=self.args.end_date, la=self.args.latitude, lo=self.args.longitude)

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
                                 monthly=self.args.accum,
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
            pexe = self.ERA_DOWNLOAD_PY.split(" ")
            if len(pexe) > 1:
                cmd = [pexe[0]]
                cmd.append(pexe[1])
            else:
                cmd = [self.ERA_DOWNLOAD_PY]
            cmd.extend(variables)
            cmd.extend(["--dates"] + [_date.strftime("%Y-%m-%d") for _date in dates])
            cmd.extend(["--times"] + [_time.strftime("%H:%M") for _time in times])
            cmd.extend(["--area", str(area)])
            if monthly:
                cmd.extend(["--monthly"])
            cmd.extend(["--out_file", out_file])
            self.logger.info("Download: {}".format(cmd))

            proc = subprocess.run(cmd)
            if not proc.returncode == 0:
                raise RuntimeError("Download process returned unexpected non-zero exit code '{}'.".format(proc.returncode))

        if not os.path.isfile(out_file):
            raise FileNotFoundError("Output file '{}' could not be located.".format(out_file))

class Era5DailyPrecipProcessing(Era5ProcessingBase):
    """
    Specialisation of the base class for downloading and processing precipitation data
    """
    #   variables to be downloaded using the API
    VARIABLES = ["total_precipitation"]

    @property
    def download_file_path(self):
        """
        Returns the path to the file that will be downloaded
        :return: path to the file that will be downloaded
        """
        return os.path.join(self.working_dir, "precip_{d}.nc".format(d=self.file_str))

    @property
    def output_file_path(self):
        """
        Returns the path to the output file from processing
        :return: path to the output file
        """
        return os.path.join(self.working_dir, "spi_{d}.json".format(d=self.file_str))

    def __init__(self, args, working_dir: str):
        """
        Initializer.  Forwards parameters to super class.
        :param args: program arguments
        :param working_dir: directory that will hold all files generated by the class
        """
        super().__init__(args=args, working_dir=working_dir)
        self.logger.debug("Initiated ERA5 daily processing of temperature strategy.")

    def download(self) -> str:
        """
        Performs file downloads.  Currently uses the basic functionality offered by the base class
        :return: path to the file containing the downloaded data
        """
        return super().download()

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
        df_filtered['day'] = df_filtered.index.strftime('%Y-%m')#-%d')
        df_filtered = df_filtered.reset_index(drop=True)
        df_filtered = df_filtered.set_index('day')
        #df_filtered = df_filtered.drop(['latitude'], axis=1)
        #df_filtered = df_filtered.drop(['longitude'], axis=1)
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

        # Save as json file
        json_str = df_filtered.to_json()
        self.logger.debug("JSON: {}".format(json_str))
        with open(self.output_file_path, "w") as outfile:
            json.dump(json_str, outfile, indent=4)

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







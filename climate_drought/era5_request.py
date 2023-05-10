import logging
import os
from os.path import expanduser
from typing import List
from datetime import date, time
import numpy as np
# handling NetCDF files
import xarray as xr
from climate_drought import utils, config
# ERA download
from pixutils import era_download
# AWS ERA5 data access
from kerchunk.hdf import SingleHdf5ToZarr
from kerchunk.combine import MultiZarrToZarr
import dask
from dask.distributed import Client
import fsspec
import pathlib
import ujson
import zarr

# Logging
logging.basicConfig(level=logging.INFO)

# Shared constants
PRECIP_VARIABLES = ['total_precipitation']
SOILWATER_VARIABLES = ["volumetric_soil_water_layer_1", "volumetric_soil_water_layer_2",
                       "volumetric_soil_water_layer_3", "volumetric_soil_water_layer_4"]

AWSKEY = os.path.join(expanduser('~'), '.aws_api_key')
AWS_PRECIP_VARIABLE = ['precipitation_amount_1hour_Accumulation']


class ERA5Request():
    """
    Object to constrain ERA5 download inputs.
    Built inputs using analysis and config arguments.
    Download can be either:
    - baseline = True: a monthly mean over a long time period to form the mean or baseline against which anomalies can be computed
    - baseline = False: a monthly or hourly value to retrieve data over shorter timescales
    """
    def __init__(self, variables, fname_out, args: config.AnalysisArgs, config: config.Config,
                 start_date, end_date, aws=False, monthly=True):

        self.latitude = args.latitude
        self.longitude = args.longitude
        self.start_date = start_date
        self.end_date = end_date
        self.variables = variables
        self.working_dir = config.outdir
        self.fname_out = fname_out
        self.verbose = config.verbose
        self.monthly = monthly
        self.aws = aws

class ERA5Download():
    """
    Provides some basic functionality that can be used by different implementation specific strategies for different
    data sources
    """

    #   target download time for each data source
    SAMPLE_TIME = time(hour=12, minute=0)

    def __init__(self, req: ERA5Request, logger: logging.Logger):
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
        freq = 'monthly' if self.req.monthly else 'hourly'
        file_str = "{sd}-{ed}_{la}_{lo}_{fq}".format(sd=self.req.start_date,
                                                     ed=self.req.end_date,
                                                     la=self.req.latitude,
                                                     lo=self.req.longitude,
                                                     fq=freq)
    
        # Extra identifier for AWS downloaded ERA5 data
        if not self.req.aws:
            aws = ''
        else:
            aws = '-aws'
        return os.path.join(self.req.working_dir, self.req.fname_out + "_{d}{a}.nc".format(d=file_str, a=aws))

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
        area_box = [round(float(self.req.latitude) + boxsz, 2),
                    round(float(self.req.longitude) - boxsz, 2),
                    round(float(self.req.latitude) - boxsz, 2),
                    round(float(self.req.longitude) + boxsz, 2)]

        if not self.req.monthly:
            times = []
            for i in range(24):
                times.append(time(hour=i, minute=0))
        else:
            times = [self.SAMPLE_TIME]

        if self.req.aws and self.req.monthly and 'precip' in self.req.variables[0]:
            self._download_aws_data(area=area_box,
                                    out_file=self.download_file_path)
        else:
            self._download_era5_data(variables=self.req.variables,
                                     dates=self.dates,
                                     times=times,
                                     area=area_box,
                                     monthly=self.req.monthly,
                                     out_file=self.download_file_path)

        if os.path.isfile(self.download_file_path):
            self.logger.info("ERA5 data was downloaded to '{}'.".format(self.download_file_path))
        else:
            raise FileNotFoundError("ERA5 download file '{}' was missing.".format(self.download_file_path))

        return self.download_file_path

    def _download_era5_data(self, variables: List[str], dates: List[date], times: List[time], area: List[float],
                            monthly: str, out_file: str) -> bool:

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

            self.logger.info("Downloading ERA data for {} {} for {}".format(dates[0], dates[-1], area))
            result = era_download.download_era5_reanalysis_data(dates=dates,
                                                                times=times, variables=variables, area=str(area),
                                                                monthly=era_monthly,
                                                                file_path=os.path.expanduser(out_file))

            if result == 0:
                raise RuntimeError("Download process returned unexpected non-zero exit code '{}'.".format(result))

        else:
            self.logger.info("Download file '{}' already exists.".format(out_file))
            outfile_exists = True

        if not os.path.isfile(out_file):
            raise FileNotFoundError("Output file '{}' could not be located.".format(out_file))

        return outfile_exists

    # Created with reference to https://medium.com/pangeo/fake-it-until-you-make-it-reading-goes-netcdf4-data-on-aws-s3-as-zarr-for-rapid-data-access-61e33f8fe685
    def _download_aws_data(self, area: List[float], out_file: str) -> bool:

        """
        Executes the AWS download script in a separate process.
        :param area: area of interest box to download data for
        :param out_file: output_file_path: path to the output file containing the requested fields.  Supported output format is NetCDF, determined by file extension.
        :return: nothing
        """

        outfile_exists = False

        if not os.path.exists(out_file):
            self.logger.info(
                "Downloading ERA data for {} {} for {}".format(self.req.start_date, self.req.end_date, area))

            # Get list of AWS files
            fs = fsspec.filesystem('s3', anon=True)
            sdate = int(self.req.start_date[0:4])
            # TODO SL Can we fix for later dates?
            edate = 2020 + 1  # int(self.req.end_date[0:4])+1
            years = list(np.arange(sdate, edate, 1))
            self.logger.warning("AWS range restricted to {} to 2020 as the files after cause issues".format(sdate))
            months = list(np.arange(1, 12 + 1, 1))

            urls = []
            for year in years:
                for month in months:
                    if month < 10:
                        mnth = '0' + str(month)
                    else:
                        mnth = month

                    # ERA5-pds is located in us-west-2 and so depending on where this computation is taking place the time taken can vary dramatically.
                    s3file = "s3://era5-pds/{}/{}/data/{}.nc".format(year, mnth, AWS_PRECIP_VARIABLE[0])
                    url = fs.glob(s3file)
                    # Check the file exists online
                    if len(url) > 0:
                        urls.append(s3file)

            self.logger.debug("Example S3 URL: {}".format(urls[0]))

            # Create path for generated JSON files
            jdir = os.path.join(self.req.working_dir, 'jsons')
            pathlib.Path(jdir).mkdir(exist_ok=True)

            # Extract JSON files
            ## default_fill_cache=False avoids caching data in between file chunks to lower memory usage
            so = dict(
                mode="rb", anon=True, default_fill_cache=False,
                default_cache_type="none"
            )
            fs2 = fsspec.filesystem('')

            # inline_threshold adjusts the Size below which binary blocks are included directly in the output
            # a higher value can result in a larger json file but faster loading time
            def gen_json(u):
                dirlist = os.path.dirname(os.path.dirname(u))
                mnth = os.path.basename(dirlist)
                yr = os.path.basename(os.path.dirname(dirlist))
                jfile = os.path.join(jdir, "{}-{}-aws-precip.json".format(yr, mnth))
                if not os.path.exists(jfile):
                    with fsspec.open(u, **so) as inf:
                        h5chunks = SingleHdf5ToZarr(inf, u, inline_threshold=300)
                        with fs2.open(jfile, 'wb') as outf:
                            outf.write(ujson.dumps(h5chunks.translate()).encode())

            serial = False
            if serial:
                for u in urls:
                    gen_json(u)
            else:
                # Start a Dask client
                client = Client(n_workers=8)
                client
                dask.compute(*[dask.delayed(gen_json)(u) for u in urls])

            def modify_fill_value(out):
                out_ = zarr.open(out)
                out_.lon.fill_value = -999
                out_.lat.fill_value = -999
                return out

            def postprocess(out):
                out = modify_fill_value(out)
                return out

            # Make JSON yearly files
            year_jlist = []
            for year in years:
                jfile = os.path.join(jdir, '{}-combined.json'.format(year))
                if not os.path.exists(jfile):
                    # Generate json list
                    jlist = fs2.glob(os.path.join(jdir, "{}*precip.json".format(year)))
                    jlist.sort()  # Sort into numerical order
                    jlen = len(jlist)
                    self.logger.debug("Generated {} JSON files {} to {}".format(jlen, os.path.basename(jlist[0]),
                                                                               os.path.basename(jlist[-1])))
                    mzz = MultiZarrToZarr(
                        jlist,
                        remote_protocol="s3",
                        remote_options={'anon': True},
                        concat_dims=['time1'],
                        identical_dims=['lat', 'lon'],
                        # inline_threshold=0,
                        postprocess=postprocess
                        # 0 lon to Nan is as a result of no fill_value being assigned, so postprocess
                    )
                    d = mzz.translate()
                    with fs2.open(jfile, 'wb') as f:
                        f.write(ujson.dumps(d).encode())

                year_jlist.append(jfile)

            # Make combined JSON file
            ## Concatenate along a specified dimension (concat_dims)
            ## Specifying identical coordinates (identical_dims) is not strictly necessary but will speed up computation times.
            mzz = MultiZarrToZarr(
                year_jlist,
                remote_protocol="s3",
                remote_options={'anon': True},
                concat_dims=['time1'],
                identical_dims=['lat', 'lon'],
                inline_threshold=0
            )
            cfile = os.path.join(jdir, 'combined.json')
            mzz.translate(cfile)

            # Import JSON into xarray
            fs = fsspec.filesystem(
                "reference",
                fo=cfile,
                remote_protocol="s3",
                remote_options={"anon": True},
                skip_instance_cache=True
            )
            m = fs.get_mapper("")
            ds = xr.open_dataset(m, engine='zarr')

            # Prepare to extract lat/lon subset
            ds = ds.drop_vars('time1_bounds')
            self.logger.debug(ds)

            # Extract point time-series dataset
            minlat = float(area[2])
            maxlat = float(area[0])
            ## Change Latitude to 0 to 360 from -180 to 180
            minlon = float(area[1]) + 180.0
            maxlon = float(area[3]) + 180.0
            self.logger.info(
                "Extraction range, Lat: {:.3f} {:.3f} Lon: {:.3f} {:.3f}".format(minlat, maxlat, minlon, maxlon))
            mask_lon = (ds.lon >= minlon) & (ds.lon <= maxlon)
            mask_lat = (ds.lat >= minlat) & (ds.lat <= maxlat)
            ds_subset = ds.where(mask_lon & mask_lat, drop=True)

            # Rename variable names
            ds_subset = ds_subset.rename({'lon': 'longitude', 'lat': 'latitude', AWS_PRECIP_VARIABLE[0]: 'tp', 'time1': 'time'})
            self.logger.debug(ds_subset)

            # Write to NetCDF
            ds_subset.to_netcdf(out_file)

            # Delete combined JSON file
            if os.path.exists(cfile):
                os.remove(cfile)

        else:
            self.logger.info("Download file '{}' already exists.".format(out_file))
            outfile_exists = True

        if not os.path.isfile(out_file):
            raise FileNotFoundError("Output file '{}' could not be located.".format(out_file))

        return outfile_exists

import logging
import os
from os.path import expanduser
import glob
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
import s3fs
import ujson

# Logging
logging.basicConfig(level=logging.INFO)

# Shared constants
PRECIP_VARIABLES = ['total_precipitation']
SOILWATER_VARIABLES = ["volumetric_soil_water_layer_1","volumetric_soil_water_layer_2","volumetric_soil_water_layer_3","volumetric_soil_water_layer_4"]

AWSKEY = os.path.join(expanduser('~'), '.aws_api_key')
AWS_PRECIP_VARIABLES = ['precipitation_amount_1hour_Accumulation']

class ERA5Request():
    """
    Object to constrain ERA5 download inputs.
    Built inputs using analysis and config arguments.
    Download can be either:
    - baseline = True: a monthly mean over a long time period to form the mean or baseline against which anomalies can be computed
    - baseline = False: a monthly or hourly value to retrieve data over shorter timescales
    """
    def __init__(self, variables, fname_out, args: config.AnalysisArgs, config: config.Config, baseline=False, aws=False, monthly=True):
        self.latitude = args.latitude
        self.longitude = args.longitude
        self.start_date = config.baseline_start if baseline else args.start_date
        self.end_date = config.baseline_end if baseline else args.end_date
        self.variables = variables
        self.working_dir = config.outdir
        self.fname_out = fname_out
        self.verbose = config.verbose
        self.aws = aws
        self.monthly = baseline or monthly

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
        # Extra identifier for AWS downloaded ERA5 data
        if not self.req.aws:
            aws = ''
        else:
            aws = '-aws'
        return os.path.join(self.req.working_dir, self.req.fname_out + "_{d}{a}.nc".format(d=file_str,a=aws))
    
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

        print("Sam: ",self.req.monthly,self.req.variables[0])
        if self.req.monthly and 'precip' in self.req.variables[0]:

            self._download_aws_data(area=area_box,
                                     out_file=self.download_file_path)
        else:
            sys.exit(1)

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

    # Created with reference to https://github.com/planet-os/notebooks/blob/master/api-examples/ERA5_tutorial.ipynb
    def _download_aws_data(self, area: str, out_file: str) -> bool:

        """
        Executes the AWS download script in a separate process.
        :param area: area of interest box to download data for
        :param out_file: output_file_path: path to the output file containing the requested fields.  Supported output format is NetCDF, determined by file extension.
        :return: nothing
        """

        outfile_exists = False

        if not os.path.exists(out_file):
            self.logger.info("Downloading ERA data for {} {} for {:.3f}:{:.3f} {:.3f}:{:.3f}".format(self.req.start_date, self.req.end_date, float(area[2]), float(area[0]), float(area[1]), float(area[3])))

            # Get list of AWS files
            fs = fsspec.filesystem('s3', anon=True)
            years = list(np.arange(int(self.req.start_date[0:4]), int(self.req.start_date[0:4])+1, 1))
            months = list(np.arange(1,12+1,1))

            urls = []
            for year in years:
                for month in months:
                    if month < 10:
                        mnth = '0'+str(month)
                    else:
                        mnth = month

                    s3file = "s3://era5-pds/{}/{}/data/{}.nc".format(year,mnth,AWS_PRECIP_VARIABLES[0])
                    url = fs.glob(s3file)
                    # Check the file exists online
                    if len(url) > 0:
                        urls.append(s3file)

            self.logger.info("Example S3 URL: {}".format(urls[0]))

            # Start a Dask client
            client = Client(n_workers=8)
            client

            # Create path for generated JSON files
            jdir = os.path.join(self.req.working_dir,'jsons')
            pathlib.Path(jdir).mkdir(exist_ok=True)

            # Extract JSON files
            def gen_json(u, jdir):
                so = dict(
                    mode="rb", anon=True, default_fill_cache=False,
                    default_cache_type="none"
                )
                yr = os.path.basename(os.path.dirname(os.path.dirname(os.path.dirname(u))))
                mnth = os.path.basename(os.path.dirname(os.path.dirname(u)))
                jfile = os.path.join(jdir,"{}-{}-aws-precip.json".format(yr,mnth))
                if not os.path.exists(jfile):
                    with fsspec.open(u, **so) as inf:
                        h5chunks = SingleHdf5ToZarr(inf, u, inline_threshold=300)
                        with open(jfile, 'wb') as outf:
                            outf.write(ujson.dumps(h5chunks.translate()).encode())
                else:
                    print("{} exists".format(jfile))

            dask.compute(*[dask.delayed(gen_json)(u, jdir) for u in urls])

            # Generate json list
            json_list = sorted(glob.glob(os.path.join(jdir,"*.json")))
            self.logger.info("Generated {} JSON files".format(len(json_list)))

            # Make combined JSON file
            mzz = MultiZarrToZarr(
                json_list,
                remote_protocol="s3",
                remote_options={'anon': True},
                concat_dims='time1',
                inline_threshold=0
            )
            cfile = os.path.join(jdir,'combined.json')
            mzz.translate(cfile)

            # Convert into xarray
            fs = fsspec.filesystem(
                "reference",
                fo=cfile,
                remote_protocol="s3",
                remote_options={"anon": True},
                skip_instance_cache=True
            )
            m = fs.get_mapper("")
            ds = xr.open_dataset(m, engine='zarr')
            print(ds)

            # Spatially subset - adjust lon range to 0 to 360
            lonmin = float(area[1])
            lonmax = float(area[3])
            nlonmin = lonmin + 180
            nlonmax = lonmax + 180
            self.logger.info("Longitude conversion {:.3f}:{:.3f} {:.3f}:{:.3f}".format(lonmin, lonmax, nlonmin, nlonmax))
            ds_subset = ds.sel(lat=slice(float(area[2]),float(area[0])), lon=slice(nlonmin,nlonmax))

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
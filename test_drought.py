import os
from sys import exit
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import argparse


# Links from Climate-drought repository
from climate_drought import drought_indices as dri, config

import logging
logging.basicConfig(level=logging.INFO)

INDEX_MAP = {
    'SPI_ECMWF': dri.SPI_ECMWF,
    'SPI_GDO': dri.SPI_GDO,
    'SPI_NCG': dri.SPI_NCG,
    'SMA_ECMWF': dri.SMA_ECMWF,
    'SMA_GDO': dri.SMA_GDO,
    'fAPAR': dri.FPAR_GDO,
    'CDI': dri.CDI,
    'FEATURE_SAFE': dri.FEATURE_SAFE,
    'UTCI': dri.UTCI
}

class DROUGHT:
    """
    Runs the drought processing

    Arguments:

    Requirements:
    """

    def __init__(self,args):

        # Convert latitude and longitude strings to lists
        args.latitude = [float(item) for item in args.latitude.replace('[','').replace(']','').split(',')]
        args.longitude = [float(item) for item in args.longitude.replace('[','').replace(']','').split(',')]
        #print("Latitude: ",args.latitude)

         # Transfer args
        self.product = args.product
        if args.utci:
            self.product = "UTCI"
        self.config = config.Config(args.outdir,args.indir,args.verbose,aws=args.aws,era_daily=args.era_daily)

        if args.product == 'CDI':
            self.args = config.CDIArgs(args.latitude,args.longitude,args.start_date,args.end_date,oformat=args.oformat,spi_source=args.spi_source,sma_source=args.sma_source)
        else:
            self.args = config.AnalysisArgs(args.latitude,args.longitude,args.start_date,args.end_date,product=args.product,oformat=args.oformat)

        # Setup logging
        self.logger = logging.getLogger("test_drought")
        self.logger.setLevel(
            logging.DEBUG if "verbose" in args and args.verbose else logging.INFO
        )

        self.logger.info("\n")

    @property
    def index(self) -> dri.DroughtIndex:
        return INDEX_MAP[self.product](self.config, self.args)


    def run_index(self):

        # Setup default input sources
        if self.product == "SPI":
            self.product = "SPI_ECMWF"
        elif self.product == "SMA":
            self.product = "SMA_ECMWF"
        elif self.product == "SAFE":
            self.product = "FEATURE_SAFE"

        self.logger.debug("Computing {idx} index for {sd} to {ed}.".format(idx=self.product, sd=self.config.baseline_start, ed=self.config.baseline_end))

        exit_code = 0

        idx = self.index

        if os.path.exists(idx.output_file_path):
            self.logger.info("Processed file '{}' already exists.".format(idx.output_file_path))
        else:
            idx.download()
            idx.process()
            self.logger.info("Downloading and processing complete for '{}' completed with format {}.".format(idx.output_file_path, self.args.oformat))

        if os.path.exists(idx.output_file_path):
            exit_code = 1
            self.logger.info("{} processing complete, generated {}".format(self.product, idx.output_file_path))

        else:
            self.logger.info("Processing failed, {} does not exist".format(idx.output_file_path))

        # Load in data and display then plot
        df = gpd.read_file(idx.output_file_path)
        print(df)
        fig, ax1 = plt.subplots()
        ax1.plot(df._date,df.spi,color='b',label='spi')
        ax1.set_ylabel('SPI [blue]')
        tick_list = df._date.values[::3]
        plt.xticks(rotation=45, ticks=tick_list)
        if self.product == 'UTCI':
            ax2 = ax1.twinx()
            ax2.plot(df._date,df.utci,color='r',label='utci')
            ax2.set_ylabel('UTCI [degC, red]')
        plt.tight_layout()
        plt.show()
        
        return exit_code

def main():
    parser = argparse.ArgumentParser(description="Test Drought Indices")

    parser.add_argument(
        "-o",
        "--outdir",
        type=str,
        dest="outdir",
        default='output',
        help="Output data folder",
    )
    parser.add_argument(
        "-i",
        "--indir",
        type=str,
        dest="indir",
        default="input",
        help="Input data folder",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Add extra information to logs",
        action="store_true",
        default=False,
    )
    parser.add_argument("-A", "--accum", action="store_true", default=False, help="Accumulation - not set from command line")
    parser.add_argument("-AWS", "--aws", action="store_true", default=False, help="Download from AWS rather than CDS for SPI")
    parser.add_argument("-y", "--latitude", type=str, dest="latitude")
    parser.add_argument("-x", "--longitude", type=str, dest="longitude")
    parser.add_argument("-p", "--product", type=str, dest="product", default='none')
    parser.add_argument("-of", "--oformat", type=str, dest="oformat", default='GeoJSON')
    parser.add_argument("-t", "--type", type=str, dest="type", default='none')
    parser.add_argument("-s", "--sdate", type=str, dest="start_date", default='20200116', help="Start date as YYYYMMDD")
    parser.add_argument("-e", "--edate", type=str, dest="end_date", default='20200410', help="End date as YYYYMMDD")
    parser.add_argument("-d", "--eradaily", action="store_true", dest="era_daily", default=False)
    parser.add_argument("-sma", "--smasrc", type=str, dest="sma_source", default='GDO', help="'GDO' or 'ECMWF'")
    parser.add_argument("-spi", "--spisrc", type=str, dest="spi_source", default='GDO', help="'GDO' or 'ECMWF'")
    parser.add_argument("-u", "--utci", action="store_true", default=False, help="Download UTCI")

    # define arguments
    args = parser.parse_args()

    print("Args: {}".format(args))
    drought = DROUGHT(args)
    result = drought.run_index()


if __name__ == "__main__":
    exit(main())

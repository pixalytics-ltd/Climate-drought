#!/usr/bin/env python
import os
import shutil
import sys
from sys import exit
import glob
import argparse
from datetime import date, datetime
import numpy as np

# Links from Climate-drought repository
from climate_drought import era5_processing as era, config

import logging
logging.basicConfig(level=logging.INFO)

# ERA5 download range
Sdate = '19850101'
Edate = '20221231'

class DROUGHT:
    """
    Runs the drought processing

    Arguments:

    Requirements:
    """

    def __init__(self,args):

        # Transfer args
        self.config = config.Config(args.outdir,args.verbose)
        self.args = config.AnalysisArgs(args)

        # Setup logging
        self.logger = logging.getLogger("test_drought")
        self.logger.setLevel(
            logging.DEBUG if "verbose" in args and args.verbose else logging.INFO
        )

        self.logger.info("\n")


    def run_spi(self):

        self.logger.debug("Computing SPI index for {sd} to {ed}.".format(sd=self.config.baseline_start, ed=self.config.baseline_end))

        exit_code = 0
       

        spi = era.SPI(self.config,self.args)
        output_file_path = spi.output_file_path

        if os.path.exists(output_file_path):
            self.logger.info("Processed file '{}' already exists.".format(output_file_path))
        else:
            downloaded_file = spi.download()
            processed_file = spi.process()
            self.logger.info("Downloading and processing complete for '{}' completed.".format(output_file_path))
            assert output_file_path == processed_file

        if os.path.exists(output_file_path):
            exit_code = 1
            self.logger.info("SPI processing complete")

        #except Exception as ex:
        #    # Log any errors, and move on to the next date
        #    exit_status = "failed: {}".format(ex)
        #    self.logger.warning("SPI for {d} failed {r}.".format(
        #            d=self.args.start_date, r=exit_status))

        self.logger.info("Processing complete")

        return exit_code


def main():
    parser = argparse.ArgumentParser(description="Test Drought Indices")

    parser.add_argument(
        "-o",
        "--outdir",
        type=str,
        dest="outdir",
        default=True,
        help="Output data folder",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        help="Add extra information to logs",
        action="store_true",
        default=False,
    )
    parser.add_argument("-A", "--accum", action="store_true", default=False, help="Accumulation - not set from cammand line")
    parser.add_argument("-y", "--latitude", type=float, dest="latitude")
    parser.add_argument("-x", "--longitude", type=float, dest="longitude")
    parser.add_argument("-p", "--product", type=str, dest="product", default='none')
    parser.add_argument("-P", "--plot", action="store_true", default=False, help="Create plot for diagnostics")
    parser.add_argument("-t", "--type", type=str, dest="type", default='none')
    parser.add_argument("-s", "--sdate", type=str, dest="start_date", default='none', help="Start date as YYYYMMDD")
    parser.add_argument("-e", "--edate", type=str, dest="end_date", default='none', help="End date as YYYYMMDD")

    # define arguments
    args = parser.parse_args()

    print("Args: {}".format(args))
    drought = DROUGHT(args)
    result = drought.run_spi()


if __name__ == "__main__":
    exit(main())

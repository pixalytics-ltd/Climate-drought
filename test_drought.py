#!/usr/bin/env python
import os
import shutil
import sys
from sys import exit
import glob
import argparse
from datetime import datetime
import numpy as np

import logging
logging.basicConfig(level=logging.INFO)

# Links from Climate-drought repository
from climate_drought import generate_spi

class DROUGHT:
    """
    Runs the drought processing

    Arguments:

    Requirements:
    """

    def __init__(self, args):

        # Transfer args
        self.args = args

        # Extract start date
        date = self.args.start_date.split("/")
        self.args.day = int(date[0])
        self.args.month = int(date[1])
        self.args.year = int(date[2])

        # Setup logging
        self.logger = logging.getLogger("test_drought")
        self.logger.setLevel(
            logging.DEBUG if "verbose" in args and args.verbose else logging.INFO
        )

        self.logger.info("\n")


    def run_drought(self):

        self.logger.debug("Computing SPI index for {sd} to {ed}.".format(sd=self.args.start_date, ed=self.args.end_date))

        exit_code = 0
        #try:

        spi = generate_spi.Era5DailyPrecipProcessing(self.args, self.args.working_dir)
        output_file_path = spi.output_file_path
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
        "-w",
        "--working_dir",
        type=str,
        dest="working_dir",
        default=True,
        help="Working folder",
    )
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
    parser.add_argument("-y", "--latitude", type=float, dest="latitude")
    parser.add_argument("-x", "--longitude", type=float, dest="longitude")
    parser.add_argument("-p", "--product", type=str, dest="product", default='none')
    parser.add_argument("-t", "--type", type=str, dest="type", default='none')
    parser.add_argument("-s", "--sdate", type=str, dest="start_date", default='none')
    parser.add_argument("-e", "--edate", type=str, dest="end_date", default='none')

    # define arguments
    args = parser.parse_args()

    print("Args: {}".format(args))
    drought = DROUGHT(args)
    result = drought.run_drought()


if __name__ == "__main__":
    exit(main())

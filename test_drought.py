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
from climate_drought import drought_indices as dri, config

import logging
logging.basicConfig(level=logging.INFO)

INDEX_MAP = {
    'SPI': dri.SPI,
    'SMA_ECMWF': dri.SMA_ECMWF,
    'SMA_EDO': dri.SMA_EDO,
    'fAPAR': dri.FPAR_EDO
}

class DROUGHT:
    """
    Runs the drought processing

    Arguments:

    Requirements:
    """

    def __init__(self,args):

        # Transfer args
        self.config = config.Config(args.outdir,args.indir,args.verbose)
        self.args = config.AnalysisArgs(args.latitude,args.longitude,args.start_date,args.end_date,args.product)

        # Setup logging
        self.logger = logging.getLogger("test_drought")
        self.logger.setLevel(
            logging.DEBUG if "verbose" in args and args.verbose else logging.INFO
        )

        self.logger.info("\n")

    @property
    def index(self) -> dri.DroughtIndex:
        print(self.config.indir)
        return INDEX_MAP[self.args.index](self.config, self.args)


    def run_index(self):

        self.logger.debug("Computing {idx} index for {sd} to {ed}.".format(idx=self.args.index, sd=self.config.baseline_start, ed=self.config.baseline_end))

        exit_code = 0

        idx = self.index

        if os.path.exists(idx.output_file_path):
            self.logger.info("Processed file '{}' already exists.".format(idx.output_file_path))
        else:
            downloaded_files = idx.download()
            processed_file = idx.process()
            self.logger.info("Downloading and processing complete for '{}' completed.".format(idx.output_file_path))

        if os.path.exists(idx.output_file_path):
            exit_code = 1
            self.logger.info("{} processing complete".format(self.args.index))

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
    result = drought.run_index()


if __name__ == "__main__":
    exit(main())

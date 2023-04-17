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
    'SMA_GDO': dri.SMA_GDO,
    'fAPAR': dri.FPAR_GDO,
    'CDI': dri.CDI
}

class DROUGHT:
    """
    Runs the drought processing

    Arguments:

    Requirements:
    """

    def __init__(self,args):

        # Transfer args
        self.product = args.product
        self.config = config.Config(args.outdir,args.indir,args.verbose)

        if args.product == 'CDI':
            self.args = config.CDIArgs(args.latitude,args.longitude,args.start_date,args.end_date, args.sma_source)
        else:
            self.args = config.AnalysisArgs(args.latitude,args.longitude,args.start_date,args.end_date)

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

        self.logger.debug("Computing {idx} index for {sd} to {ed}.".format(idx=self.product, sd=self.config.baseline_start, ed=self.config.baseline_end))

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
            self.logger.info("{} processing complete".format(self.index))

        self.logger.info("Processing complete")

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
    parser.add_argument("-A", "--accum", action="store_true", default=False, help="Accumulation - not set from cammand line")
    parser.add_argument("-y", "--latitude", type=float, dest="latitude", default=52.5)
    parser.add_argument("-x", "--longitude", type=float, dest="longitude", default=1.25)
    parser.add_argument("-p", "--product", type=str, dest="product", default='SPI')
    parser.add_argument("-P", "--plot", action="store_true", default=False, help="Create plot for diagnostics")
    parser.add_argument("-t", "--type", type=str, dest="type", default='none')
    parser.add_argument("-s", "--sdate", type=str, dest="start_date", default='20200116', help="Start date as YYYYMMDD")
    parser.add_argument("-e", "--edate", type=str, dest="end_date", default='20200410', help="End date as YYYYMMDD")
    parser.add_argument("-S", "--smasrc", type=str, dest="sma_source", default='EDO', help="'EDO' or 'ECMWF")


    # define arguments
    args = parser.parse_args()

    print("Args: {}".format(args))
    drought = DROUGHT(args)
    result = drought.run_index()


if __name__ == "__main__":
    exit(main())

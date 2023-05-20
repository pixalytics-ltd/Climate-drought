
import numpy as np
from climate_indices import compute, indices, utils
from climate_indices.compute import scale_values, Periodicity

import logging
logging.basicConfig(level=logging.INFO)

class INDICES:
    """
    Runs the drought indices

    Arguments:

    Requirements:
    """

    FITTED_INDEX_VALID_MIN = -3.09
    FITTED_INDEX_VALID_MAX = 3.09

    # SPI Variables
    Start_year = 1985 #TODO JC Make same as inputs, specify in config?
    Calib_year_initial = 1900
    Calib_year_final = 2000
    Scale_months = 3

    def __init__(self, verbose=True):

        # Setup logging
        self.logger = logging.getLogger("drought_indices")
        self.logger.setLevel(
            logging.DEBUG if verbose else logging.INFO
        )

        self.logger.info("\n")

    # From https://github.com/monocongo/climate_indices/blob/master/notebooks/spi_simple.ipynb
    def calc_spi(self, values):

        # scale to 3-month convolutions
        scaled_values = scale_values(values, scale=3, periodicity=Periodicity.monthly)
        self.logger.debug("scaled values: {:.3f} {:.3f}".format(np.nanmin(scaled_values),np.nanmax(scaled_values)))

        # compute the fitting parameters on the scaled data
        alphas, betas = \
            compute.gamma_parameters(
                scaled_values,
                data_start_year=self.Start_year,
                calibration_start_year=self.Calib_year_initial,
                calibration_end_year=self.Calib_year_final,
                periodicity=compute.Periodicity.monthly,
            )
        self.logger.debug("alphas: {:.3f} {:.3f} betas: {:.3f} {:.3f}".format(np.nanmin(alphas),np.nanmax(alphas),np.nanmin(betas),np.nanmax(betas)))
        gamma_params = {"alpha": alphas, "beta": betas}

        spi_gamma_3month = \
            indices.spi(
                values,
                scale=self.Scale_months,
                distribution=indices.Distribution.gamma,
                data_start_year=self.Start_year,
                calibration_year_initial=self.Calib_year_initial,
                calibration_year_final=self.Calib_year_final,
                periodicity=compute.Periodicity.monthly,
                fitting_params=gamma_params,
            )
        return spi_gamma_3month
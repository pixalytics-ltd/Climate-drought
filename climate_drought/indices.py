
import numpy as np
from climate_indices import compute, indices, utils

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

    def __init__(self, args):

        # Transfer args
        self.args = args

        # Setup logging
        self.logger = logging.getLogger("drought_indices")
        self.logger.setLevel(
            logging.DEBUG if "verbose" in args and args.verbose else logging.INFO
        )

        self.logger.info("\n")

    # From https://github.com/monocongo/climate_indices/blob/master/notebooks/spi_simple.ipynb
    def spi(self,
            values: np.ndarray,
            scale: int,
            distribution: indices.Distribution,
            data_start_year: int,
            calibration_year_initial: int,
            calibration_year_final: int,
            periodicity: compute.Periodicity,
    ) -> np.ndarray:
        """
        Computes SPI (Standardized Precipitation Index).

        :param values: 1-D numpy array of precipitation values, in any units,
            first value assumed to correspond to January of the initial year if
            the periodicity is monthly, or January 1st of the initial year if daily
        :param scale: number of time steps over which the values should be scaled
            before the index is computed
        :param distribution: distribution type to be used for the internal
            fitting/transform computation
        :param data_start_year: the initial year of the input precipitation dataset
        :param calibration_year_initial: initial year of the calibration period
        :param calibration_year_final: final year of the calibration period
        :param periodicity: the periodicity of the time series represented by the
            input data, valid/supported values are 'monthly' and 'daily'
            'monthly' indicates an array of monthly values, assumed to span full
             years, i.e. the first value corresponds to January of the initial year
             and any missing final months of the final year filled with NaN values,
             with size == # of years * 12
             'daily' indicates an array of full years of daily values with 366 days
             per year, as if each year were a leap year and any missing final months
             of the final year filled with NaN values, with array size == (# years * 366)
        :param fitting_params: optional dictionary of pre-computed distribution
            fitting parameters, if the distribution is gamma then this dict should
            contain two arrays, keyed as "alphas" and "betas", and if the
            distribution is Pearson then this dict should contain four arrays keyed
            as "probabilities_of_zero", "locs", "scales", and "skews"
        :return SPI values fitted to the gamma distribution at the specified time
            step scale, unitless
        :rtype: 1-D numpy.ndarray of floats of the same length as the input array
            of precipitation values
        """

        # we expect to operate upon a 1-D array, so if we've been passed a 2-D array
        # then we flatten it, otherwise raise an error
        shape = values.shape
        if len(shape) == 2:
            values = values.flatten()
        elif len(shape) != 1:
            message = "Invalid shape of input array: {shape}".format(shape=shape) + \
                      " -- only 1-D and 2-D arrays are supported"
            self.logger.error(message)
            raise ValueError(message)

        # if we're passed all missing values then we can't compute
        # anything, so we return the same array of missing values
        if (np.ma.is_masked(values) and values.mask.all()) or np.all(np.isnan(values)):
            return values

        # clip any negative values to zero
        if np.amin(values) < 0.0:
            self.logger.warn("Input contains negative values -- all negatives clipped to zero")
            values = np.clip(values, a_min=0.0, a_max=None)

        # remember the original length of the array, in order to facilitate
        # returning an array of the same size
        original_length = values.size

        # get a sliding sums array, with each time step's value scaled
        # by the specified number of time steps
        values = compute.sum_to_scale(values, scale)

        # reshape precipitation values to (years, 12) for monthly,
        # or to (years, 366) for daily
        if periodicity is compute.Periodicity.monthly:

            values = utils.reshape_to_2d(values, 12)

        elif periodicity is compute.Periodicity.daily:

            values = utils.reshape_to_2d(values, 366)

        else:

            raise ValueError("Invalid periodicity argument: %s" % periodicity)

        if distribution is indices.Distribution.gamma:

            # fit the scaled values to a gamma distribution
            # and transform to corresponding normalized sigmas
            values = compute.transform_fitted_gamma(
                values,
                data_start_year,
                calibration_year_initial,
                calibration_year_final,
                periodicity,
            )
        elif distribution is indices.Distribution.pearson:

            # fit the scaled values to a Pearson Type III distribution
            # and transform to corresponding normalized sigmas
            values = compute.transform_fitted_pearson(
                values,
                data_start_year,
                calibration_year_initial,
                calibration_year_final,
                periodicity,
            )

        else:
    
            message = "Unsupported distribution argument: " + \
                      "{dist}".format(dist=distribution)
            self.logger.error(message)
            raise ValueError(message)

        # clip values to within the valid range, reshape the array back to 1-D
        values = np.clip(values, self.FITTED_INDEX_VALID_MIN, self.FITTED_INDEX_VALID_MAX).flatten()

        # return the original size array
        return values[0:original_length]
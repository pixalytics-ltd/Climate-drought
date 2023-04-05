
import datetime
import pandas as pd
import argparse
import numpy as np


def daterange(sdate, edate, rtv):
    """
    Generates a list of date strings between two given dates using pandas.  The list is then iterated over and
    reformatted to obtain the list of dates for usage in other programs

    :param sdate: start date string formatted as YYYYMMDD
    :type sdate: str
    :param edate: end date string formatted as YYYYMMDD
    :type edate: str
    :param rtv: integer flag to specify if a conversion to julian day of year is required;
     with value = 1 to generate it (TBC) otherwise default is 0
    :type rtv: int
    :return: list of dates in the specified range
    """

    rng = pd.date_range(start=sdate, end=edate)
    dates = []
    # This first for loop takes the pandas date range and slices the date
    # section into an integer string format i.e 20160101
    for i in range(len(rng)):
        t = str(rng[i])
        if rtv == 0:
            y = t[0:4] + t[5:7] + t[8:10]
        elif rtv == 1:
            fmt = "%Y-%m-%d"
            dt = datetime.datetime.strptime(t, fmt)
            tt = dt.timetuple()
            if int(tt[7]) < 100:
                y = t[0:4] + "0" + str(tt[7])
            else:
                y = t[0:4] + str(tt[7])
        dates.append(y)
    return dates

def df_to_dekads(df: pd.DataFrame) -> pd.DataFrame:
    """
    Utility function to resample a DataFrame with frequency greater than 10 days into dekads
    :param df: pd.Dataframe with time index with a frequency > 10 days e.g. daily, hourly
    :return: dataframe with dekad frequency
    """
    d = df.index.day - np.clip((df.index.day-1) // 10, 0, 2)*10 - 1
    date = df.index.values - np.array(d, dtype="timedelta64[D]")
    return df.groupby(date).mean()

def dti_dekads(sdate,edate):
    """
    Utility function to create a datetime index list in dekads between a defined start and end date
    :param sdate: start date, format 'YYYYMMDD'
    :param edate: end date, format 'YYYYMMDD'
    :return: datetimeindex in dekads
    """
    dti = pd.date_range(sdate,edate,freq='1D')
    d = dti.day - np.clip((dti.day-1) // 10, 0, 2)*10 - 1
    date = dti.values - np.array(d, dtype="timedelta64[D]")
    return pd.DatetimeIndex(np.unique(date))

def fill_gaps(index, df: pd.DataFrame) -> pd.DataFrame:
    """
    Utility function to populate missing data in a DataFrame against a defined list of times
    :param index: index we want to populate 
    :param df: pd.DataFrame to be interpolated onto index
    :return: pd.DataFrame with a regular datetime index where missing data is populated with NaNs
    """
    gaps = index[~index.isin(df.index)]
    if len(gaps) > 0:
        df_gaps = pd.DataFrame(index=gaps)
        return pd.concat([df,df_gaps])
    else:
        return df

class setup_args:
    working_dir = '/data/webservice/CLIMATE'
    outdir = '/data/webservice/CLIMATE'
    verbose=True
    accum=True
    latitude=52.5
    longitude=1.25
    product='SPI'
    plot=False
    type='none'
    start_date = '20200101'
    end_date ='20221231'



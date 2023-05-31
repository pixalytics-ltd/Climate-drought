
import datetime
import pandas as pd
import xarray as xr
import numpy as np
import matplotlib.pyplot as plt

from shapely import Polygon


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
    df_daily = df.resample('1D').mean()
    d = df_daily.index.day - np.clip((df_daily.index.day-1) // 10, 0, 2)*10 - 1
    date = df_daily.index.to_numpy() - np.array(d, dtype="timedelta64[D]")
    return df_daily.groupby(date).mean()

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
        return pd.concat([df,df_gaps]).sort_index()
    else:
        return df
    
def crop_df(df,sdate,edate) -> pd.DataFrame:
    """
    Crop a Dataframe between start and end dates
    :param df: pandas dataframe with time index
    :param sdate: pd.Timestamp or date format YYYYMMDD
    :param edate: pd.Timestamp or date format YYYYMMDD
    """
    return df.loc[(df.index >= sdate) & (df.index <= edate)]

def crop_ds(ds,sdate,edate) -> xr.Dataset:
    """
    Crop a Dataframe between start and end dates
    :param ds: xarray dataset with time coordinate
    :param sdate: date format YYYYMMDD
    :param edate: date format YYYYMMDD
    """
    return ds.where((ds.time >= pd.Timestamp(sdate)) & (ds.time <= pd.Timestamp(edate)),drop=True)

def mask_ds_bbox(ds,minlon,maxlon,minlat,maxlat,ds_lon_name='lon',ds_lat_name='lat'):
    """
    Mask a xr.Dataset within bounding box defined by lat and lon mimn and max
    :param ds: dataset with time, lat and lon dimensions
    :param minlat: Minimum latitude of bounding box
    :param maxlat: Maximum latitude of bounding box
    :param minlon: Minimum longitude of bounding box
    :param maxlon: Maximum longitude of bounding box
    :param ds_lat_name: ds coordinate label for latitude if not 'lat'
    :param ds_lon_name: ds coordinate label for longitue if not 'lon'
    """
    valid_lon = (ds[ds_lon_name] >= minlon) & (ds[ds_lon_name] <= maxlon)
    valid_lat = (ds[ds_lat_name] >= minlat) & (ds[ds_lat_name] <= maxlat)
    return ds.where(valid_lat & valid_lon,drop=True)

    
def mask_ds_poly(ds,lats,lons,ds_lat_name='lat',ds_lon_name='lon'):
    """
    Mask a xr.Dataset within Polygon defined by lat and lon coordinate lists.
    :param ds: dataset with time, lat and lom dimensions
    :param lats: list of latitude coordinates to mask within
    :param lons: list of longiude coordinates to mask within (length must equal length of lats)
    :param ds_lat_name: ds coordinate label for latitude if not 'lat'
    :param ds_lon_name: ds coordinate label for longitue if not 'lon'
    :param plot: boolean for whether to produce a plot showing masked area over grid cells
    """
    # Reduce ds to bounding box before cutting out polygon
    ds = mask_ds_bbox(ds,np.min(lons),np.max(lons),np.min(lats),np.max(lats),ds_lon_name,ds_lat_name)

    # Create a polygon of the area to be masked
    pn = Polygon(tuple([(x,y) for x,y in zip(lons,lats)]))

    xnp = ds[ds_lon_name].to_numpy()
    ynp = ds[ds_lat_name].to_numpy()

    # Define the size of each grid cell
    ygrid = np.round(xnp[1]-xnp[0],2)/2#np.mean(np.diff(xnp))/2
    xgrid = np.round(ynp[1]-ynp[0],2)/2#np.mean(np.diff(ynp))/2

    def polycell(x,y):
        """
        Create a new polygon representing the grid cell with centre x,y
        """
        tl = (x-xgrid,y+ygrid)
        tr = (x+xgrid,y+ygrid)
        bl = (x-xgrid,y-ygrid)
        br = (x+xgrid,y-ygrid)
        return Polygon((tl,tr,br,bl))
    
    mask = np.ones((len(xnp),len(ynp))) * np.nan
    for i,x in (enumerate(xnp)):
        for j,y in enumerate(ynp):
            mask[i,j]=pn.overlaps(polycell(x,y))
    
    # Assign a mask to the ds
    ds['mask'] = ((ds_lat_name,ds_lon_name),mask)

    if ds.mask.any():
        rtn = ds.where(ds.mask,drop=True)
    else:
        print('No latitudes or longnitudes fall within the specified area')
        rtn = None

    return rtn

def nearest_dekad(day: int) -> int:
    return 1 if day<11 else (11 if day<21 else 21)

class setup_args:
    working_dir = '/data/webservice/CLIMATE'
    indir = '/data/webservice/CLIMATE/input'
    outdir = '/data/webservice/CLIMATE'
    verbose=True
    accum=True
    latitude=52.5
    longitude=1.25
    index='SPI'
    plot=False
    type='none'
    start_date = '20200101'
    end_date ='20221231'
    aws = False
    oformat = "GeoJSON"
    sma_source = "GDO"



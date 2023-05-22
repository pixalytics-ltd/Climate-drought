import ssl

from urllib.request import urlretrieve
from datetime import datetime
from enum import Enum

URL_POSITION = "https://edr-api-c.mdl.nws.noaa.gov/Climate-EDR//collections/{collection}/position?coords=POINT({lon}%20{lat})&parameter-name={param}&datetime={start}/{end}&crs=EPSG:4326&f=csv"

class NClimGridParams(Enum):
    PRECIPITATION = 'prcp'
    TEMPERATURE_MAX = 'tmax'
    TEMPERATURE_MIN = 'tmin'


def get_nclimgrid(lon, lat, start: str, end: str, param: NClimGridParams, out_filepath: str, cube=False):
    """"
    Returns a dataframe of the parameter 'param' from the nclimgrid_monthly collection
    :param start: the start date in the format 'YYYYMMDD'
    :param end: the end date in the format 'YYYYMMDD'
    """
    str2dt = lambda str: datetime(int(str[0:4]),int(str[4:6]),int(str[6:8]),0,0,0).strftime("%Y-%m-%dT%H:%M:%SZ")

    urlretrieve(
        URL_POSITION.format(
            collection='nclimgrid-monthly',
            lon=lon, lat=lat,
            param=param.value,
            start=str2dt(start),
            end=str2dt(end)),
        out_filepath)
    
    return out_filepath
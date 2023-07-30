import logging
import os
import numpy as np
import pandas as pd
import geojson
from climate_drought import indices

# Logging
logging.basicConfig(level=logging.INFO)

# Find the closest matching lat value
def find_nearest(lons, lats, lon0, lat0):
    idx = ((lons - lon0)**2+(lats - lat0)**2).argmin()
    value_lat =  lats.flat[idx]
    value_lon = lons.flat[idx]
    return value_lat, value_lon

class LoadSAFE():
    """
    Loads the manually provided SAFE file
    """
    def __init__(self, logger: logging.Logger):
        self.logger = logger

    # Load Canadian RCP data from SAFE software exported GeoJSON
    def load_safe(self, df_spi, lat_val = 50.0, lon_val = -97.5):
        infile = os.path.join("input","climateScenarios_rpc4.5_precipTotalMonPoints_MB_2023_2024.geojson")
        if not os.path.exists(infile):
            self.logging.warning("Could not load SAFE Software file: {}".format(infile))
            # Return the original SPI data
            df = df_spi
        else:

            # Load data
            with open(infile) as f:
                data = geojson.load(f)

            # Normalize JSON data into a flat table
            df = pd.json_normalize(data["features"])

            # Extract data from features?
            coords = 'geometry.coordinates'
            df_interim = (df[coords].apply(pd.Series).stack()
                .reset_index(level=1).rename(columns={0: coords, "level_1": "point"})
                .join(df.drop(coords, 1),how='left'))

            # Select specific columns and then rename
            columns = ['point','properties._date','properties.precipTotalMon', 'properties._x', 'properties._y']
            df_safe = pd.DataFrame(df_interim, columns=columns)
            df_safe.rename(columns={'properties._date': 'time', 'properties.precipTotalMon': 'tp_orig', 'properties._x': 'longitude','properties._y': 'latitude'}, inplace=True)

            # Reduce to only the points with value 1
            df_safe = df_safe.loc[(df_safe['point'] == 1)]
            df_safe = df_safe.drop('point', 1)

            # Convert units for precipitation from mm/day to m
            tp = df_safe.tp_orig.values / 1000.0 / 24.0
            df_safe['tp'] = tp
            df_safe['tp'] = df_safe['tp'].astype('float32')
            df_safe = df_safe.drop('tp_orig', 1)

            # Convert to xarray, extract closest lat/lon
            datxr = df_safe.to_xarray()
            latv, lonv = find_nearest(datxr.longitude.values,datxr.latitude.values, lon_val, lat_val)

            # Drop latitude/longitude
            datxr = datxr.where((datxr.latitude == latv)&(datxr.longitude == lonv), drop=True)

            # Convert back to dataframe and drop lat/lon
            df_safe = datxr.to_dataframe()
            df_safe = df_safe.drop('latitude', 1).drop('longitude', 1)

            # Convert time then set as index
            df_safe['time'] = df_safe['time'].astype('datetime64')
            df_safe = df_safe.set_index('time')

            # Add df_safe to existing df_spi dataset and extract precip
            self.logger.debug("df_safe: ",df_safe)
            df_spi = df_spi.drop('spi',1)
            self.logger.debug("df_spi: ",df_spi)
            df = pd.concat([df_spi, df_safe])
            self.logger.info("SAFE Climate scenario extension, df: ",df)

            # Calculate SPI
            spi = indices.INDICES()
            datxr = df.to_xarray()
            precip = datxr.tp.load()
            spi_vals = spi.calc_spi(np.array(precip.values).flatten())
            self.logger.info("SPI, {} values: {:.3f} {:.3f}".format(len(spi_vals), np.nanmin(spi_vals),np.nanmax(spi_vals)))

            # Add SPI and drop Latitude and Longitude
            df['spi'] = spi_vals

        return df

def main():

    df_spi_reanalysis = pd.DataFrame([],columns=['time', 'tp','spi'])
    safe = LoadSAFE(logger=logging)
    df_safe = safe.load_safe(df_spi_reanalysis)
    print("Loaded: ",df_safe)

if __name__ == "__main__":
    exit(main())
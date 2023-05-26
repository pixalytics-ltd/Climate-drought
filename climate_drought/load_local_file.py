import os
import numpy as np
import pandas as pd
import geojson
from climate_drought import indices

# Load Canadian RCP data from SAFE software exported GeoJSON
def load_safe(df_spi, lat_val = 50.0, lon_val = -97.5):
    infile = os.path.join("input","climateScenarios_rpc4.5_precipTotalMonPoints_MB_2023_2024.geojson")
    if not os.path.exists(infile):
        print("Could not load SAFE Software file: {}".format(infile))
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
        #print(df_interim.columns)

        # Select specific columns and then rename
        columns = ['point','properties._date','properties.precipTotalMon', 'properties._x', 'properties._y']
        df_safe = pd.DataFrame(df_interim, columns=columns)
        df_safe.rename(columns={'properties._date': 'time', 'properties.precipTotalMon': 'tp', 'properties._x': 'longitude','properties._y': 'latitude'}, inplace=True)

        # Reduce to only the required lat/lon values
        offset = 0.05
        df_safe = df_safe.loc[(df_safe['longitude'] > lon_val-offset) & (df_safe['longitude'] < lon_val+offset) & (df_safe['latitude'] > lat_val-offset) & (df_safe['latitude'] < lat_val+offset) & (df_safe['point'] == 1)]
        df_safe = df_safe.drop('point', 1)


        # Convert to xarray, extract max lat/lon then drop lat/lon
        datxr = df_safe.to_xarray()
        datxr = datxr.set_index(n_event=['longitude','latitude'])
        print("Sam: ",datxr)
        precip = datxr.tp.max(['latitude', 'longitude']).load()
        df_safe = precip.to_dataframe()
        #df_safe = df_safe.drop('latitude', 1).drop('longitude', 1)

        # Add df_safe to existing df_spi dataset and extract precip
        print("df_safe: ",df_safe)
        print("df_spi: ",df_spi)
        df = pd.concat([df_spi, df_safe])
        print("df: ",df)

        # Calculate SPI
        spi = indices.INDICES()
        precip = df.to_xarray()
        spi_vals = spi.calc_spi(np.array(precip.values).flatten())
        print("SPI, {} values: {:.3f} {:.3f}".format(len(spi_vals), np.nanmin(spi_vals),np.nanmax(spi_vals)))

        # Add SPI and drop Latitude and Longitude
        df['spi'] = spi_vals

        return df

def main():

    df_spi_reanalysis = pd.DataFrame([],columns=['time', 'tp', 'longitude', 'latitude'])
    df_safe = load_safe(df_spi_reanalysis)
    print("Loaded: ",df_safe)

if __name__ == "__main__":
    exit(main())

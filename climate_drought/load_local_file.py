import os
import pandas as pd
from pandas.io.json import json_normalize
import geojson


# Load precip Canadian RCP data from SAFE software
def load_safe():
    infile = os.path.join("input","climateScenarios_rpc4.5_precipTotalMonPoints_MB_2023_2024.geojson")
    if not os.path.exists(infile):
        print("Could not load SAFE Software file: {}".format(infile))
        df_safe = []
    else:
        df = json_normalize(geojson["features"])
        coords = 'properties.geometry.coordinates'
        df_safe = (df[coords].apply(lambda r: [(i[0],i[1]) for i in r[0]])
            .apply(pd.Series).stack()
            .reset_index(level=1).rename(columns={0:coords,"level_1":"point"})
            .join(df.drop(coords,1), how='left')).reset_index(level=0)
        df_safe[['lat','long']] = df_safe[coords].apply(pd.Series)
        print("SAFE:",df_safe)

        return df_safe

def main():

    df_safe = load_safe()
    print("Loaded: ",df_safe)

if __name__ == "__main__":
    exit(main())

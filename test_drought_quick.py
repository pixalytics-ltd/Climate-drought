
import argparse
import datetime
import numpy as np
import xarray as xr
import streamlit as st
import matplotlib.pyplot as plt

# Links from Climate-drought repository
from climate_drought import indices

OUTPUT_DIR = 'output'
FNAME = 'precip_20200101-20221231_52.5_1.25.nc'

@st.cache(hash_funcs={xr.core.dataset.Dataset: id}, allow_output_mutation=True)
def loadnc():
    return xr.open_dataset(OUTPUT_DIR + '/' + FNAME)

# Extract data from NetCDF file
datxr = loadnc()
resamp = datxr.tp.max(['latitude', 'longitude']).load()
precip = resamp[:, 0]
    
with st.sidebar:
    latitude=st.number_input(label='Latitude',value=50)
    longitude=st.number_input(label='Longitude',value=1)
    start_date=st.date_input(label='Start',value=datetime.date(2020,5,3))
    end_date=st.date_input(label='End',value=datetime.date(2022,5,2))

args = argparse.Namespace(
    accum = True,
    latitude = latitude,
    longitude = longitude,
    start_date = start_date.strftime('%Y%m%d'),
    end_date = end_date.strftime('%Y%m%d'),
    product = 'SPI',
    type = 'none',
    verbose = 'False',
    outdir = 'output',
    plot = False
    )

# Calculate SPI
spi = indices.INDICES(args)
spi_vals = spi.calc_spi(np.array(precip.values).flatten())
resamp = resamp.sel(expver=1, drop=True)

# Convert xarray to dataframe Series and add SPI
df = resamp.to_dataframe()
df['spi'] = spi_vals

# Select requested time slice
sdate = r'{}-{}-{}'.format(start_date.year,start_date.month,start_date.day)
edate = r'{}-{}-{}'.format(end_date.year,end_date.month,end_date.day)

df_filtered = df.loc[(df.index >= sdate) & (df.index <= edate)]

# Remove any NaN values
df_filtered = df_filtered[~df_filtered.isnull().any(axis=1)]

#st.table(df_filtered)

fig,ax = plt.subplots(2,1,figsize=(10,6))
ax[0].plot(df_filtered.index,df_filtered.tp,label='Precipitation')
ax[1].plot(df_filtered.index,df_filtered.spi,label='SPI')
ax[0].grid()
ax[1].grid()


st.pyplot(fig)




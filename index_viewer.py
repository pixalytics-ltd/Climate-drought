import datetime
import glob
import numpy as np
import pandas as pd
import xarray as xr
import streamlit as st
import matplotlib.pyplot as plt
import plotly.graph_objects as go

# Links from Climate-drought repository
from climate_drought import config, era5_processing

# Script to generate a web app to view and interact with Index input and output data.
# To run:
# - change 'OUTPUT_DIR' to location of netcdf files
# - in the command line, activate climate-env
# - enter 'streamlit run index_viewer.py'
# The web app will start up in a window in your browser.

OUTPUT_DIR = 'output'

st.set_page_config(layout="wide")

@st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
def create_indices():
    # configure inputs
    aa = config.AnalysisArgs(
        latitude=52.5,
        longitude=1.25,
        start_date='20200101',
        end_date='20221231',
        product='SMA'
    )
    cf = config.Config(outdir= 'output')

    # Make sure everything is already downloaded else it'll take ages
    spi = era5_processing.SPI(cf,aa)
    sma = era5_processing.SoilMoisture(cf,aa)

    spi.download()
    sma.download()

    df_spi = spi.process()
    df_sma = sma.process()

    swvl_fname = sma.swv_monthly_download.download_file_path

    return aa, df_spi, df_sma, swvl_fname

aa, df_spi, df_sma, swvl_fname = create_indices()

boxsz = 0.1
latmax=aa.latitude + boxsz
lonmin=aa.longitude - boxsz
latmin=aa.latitude - boxsz
lonmax=aa.longitude + boxsz

with st.sidebar:
    sma_level = st.selectbox('Soil Water Indicator Level',['1','2','3','4'])

fig = go.Figure(go.Scattermapbox(
    fill = "toself",
    lon = [lonmin,lonmax,lonmax,lonmin], lat = [latmax,latmax,latmin,latmin],
    marker = { 'size': 10, 'color': "orange" }))

fig.update_layout(
    width = 500,
    height = 500,
    margin=dict(l=0, r=20, t=20, b=20),
    mapbox = {
        'style': "stamen-terrain",
        'center': {'lon': aa.longitude, 'lat': aa.latitude },
        'zoom': 7},
    showlegend = False)

col1,col2 = st.columns(2)
with col1:
    st.plotly_chart(fig)

# fig1,ax = plt.subplots(figsize=(10,3))
# ax.plot(df_spi.index,df_spi.tp,label='Precipitation')
# ax.set_title('Total Precipitation')
# ax.grid()

fig2,ax2 = plt.subplots(figsize=(10,3))
ax2.plot(df_spi.index,df_spi.spi,label='SPI')
ax2.set_title('Standardized Precipitation Index')
ax2.grid()

warning = df_spi.spi < -1
lims = ax2.get_ylim()
ax2.fill_between(df_spi.index, *[-4,4], where=warning, facecolor='red', alpha=.2)
ax2.set_ylim(lims)

# access raw soil moisture data
ds_swvl = xr.open_dataset(swvl_fname).isel(expver=0).mean(('latitude','longitude')).drop_vars('expver')

fig3,ax = plt.subplots(figsize=(10,3))
for n in [1,2,3,4]:
    var = 'swvl' + str(n)
    layer_mean = ds_swvl[var].mean()
    im1 = ax.plot(ds_swvl.time,ds_swvl[var],label='Layer {} ('.format(n) + r'$\bar{x}$' + ' = {mean:.2f})'.format(mean=layer_mean))
    ax.plot(ds_swvl.time,[layer_mean for _ in ds_swvl.time],c=im1[0].get_color())

ax.set_title('Soil water volume')
ax.grid()
ax.legend()

fig4,ax = plt.subplots(figsize=(10,3))
for n in [1,2,3,4]:
    ax.plot(df_sma.index,df_sma['zscore_swvl' + str(n)],label='Layer {}'.format(n))

ax.set_title('Soil water volume z-score')
ax.set_xlim(ax2.get_xlim())
ax.grid()
ax.legend()


warning = df_sma['zscore_swvl{}'.format(sma_level)] < -1
lims = ax.get_ylim()
ax.fill_between(df_sma.index, *[-4,4], where=warning, facecolor='red', alpha=.2)
ax.set_ylim(lims)

with col2:
    #st.pyplot(fig1)
    st.pyplot(fig2)
    st.pyplot(fig3)
    st.pyplot(fig4)
    




import datetime
import glob
import numpy as np
import pandas as pd
import xarray as xr
import streamlit as st
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from typing import List

# Links from Climate-drought repository
from climate_drought import config, drought_indices as dri

# Script to generate a web app to view and interact with Index input and output data.
# To run:
# - change 'OUTPUT_DIR' to location of netcdf files
# - in the command line, activate climate-env
# - enter 'streamlit run index_viewer.py'
# The web app will start up in a window in your browser.

OUTPUT_DIR = 'output'

st.set_page_config(layout="wide")

@st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
def plot(df:pd.DataFrame,varnames:List[str],title:str,showmean=False,warning=0,warning_var=None):

    fig, ax = plt.subplots(figsize=(10,3))

    time = df.index

    for var in varnames:
        if showmean:
            var_mean = df[var].mean()
        legend = var + (' ('+ r'$\bar{x}$' + ' = {mean:.2f})'.format(mean=var_mean) if showmean else '')
        im1 = ax.plot(time,df[var],label=legend)
        if showmean:
            im2 = ax.plot(time,[var_mean for _ in time],c=im1[0].get_color())

    ax.set_title(title)
    ax.grid()
    
    if len(varnames) > 1:
        ax.legend()

    if not warning==0: 
        markwarning = df[warning_var] < warning
        lims = ax.get_ylim()
        ax.fill_between(df.index, *[-4,4], where=markwarning, facecolor='red', alpha=.2)
        ax.set_ylim(lims)

    return fig, ax

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
    spi = dri.SPI(cf,aa)
    sma = dri.SMA_ECMWF(cf,aa)

    spi.download()
    sma.download()

    df_spi = spi.process()
    df_sma = sma.process()

    swvl_fname = sma.swv_monthly_download.download_file_path

    return aa, df_spi, df_sma, swvl_fname

@st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
def load_era_soilmoisture(fname):
    return  xr.open_dataset(fname).isel(expver=0).mean(('latitude','longitude')).drop_vars('expver').to_dataframe()

@st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
def draw_map(aa):
    boxsz = 0.1
    latmax=aa.latitude + boxsz
    lonmin=aa.longitude - boxsz
    latmin=aa.latitude - boxsz
    lonmax=aa.longitude + boxsz

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
    return fig

aa, df_spi, df_sma, swvl_fname = create_indices()
ds_swvl = load_era_soilmoisture(swvl_fname)


plot_options = {'SPI':False,
                'Soil Water Vol. (ECMWF)':False,
                'SMA (ECMWF)':False,
                'SMA (EDO)':False}


with st.sidebar:
    st.write('Plots to show')
    for itm in plot_options:
        plot_options[itm] = st.checkbox(itm,key=itm)
    print(plot_options)
    sma_level = st.selectbox('Soil Water Indicator Level',['1','2','3','4'])


col1,col2 = st.columns(2)
with col1:
    st.plotly_chart(draw_map(aa))

figs = []

if plot_options['SPI']:
    fig, ax = plot(df_spi,['spi'],'Standardised Precipitation Index',warning=-1,warning_var='spi')
    figs.append(fig)

if plot_options['Soil Water Vol. (ECMWF)']:
    fig, ax = plot(ds_swvl,['swvl1','swvl2','swvl3','swvl4'],title='Soil Water Volume',showmean=True)
    figs.append(fig)

if plot_options['SMA (ECMWF)']:
    fig, ax = plot(df_sma,['zscore_swvl'+ str(n) for n in[1,2,3,4]],title='Soil Moisture Anomaly (ECMWF)',warning=-1,warning_var='zscore_swvl{}'.format(sma_level))
    figs.append(fig)


with col2:
    for f in figs:
        st.pyplot(f)
    




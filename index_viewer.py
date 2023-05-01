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

# """
# Script to generate a web app to view and interact with Index input and output data.
# To run:
# - change 'OUTPUT_DIR' to location of netcdf files
# - in the command line, activate climate-env
# - enter 'streamlit run index_viewer.py'
# The web app will start up in a window in your browser.
# """

OUTPUT_DIR = 'output'

C_WATCH = 'gold'
C_WARNING = 'darkorange'
C_ALERT1 = 'orangered'
C_ALERT2 = 'crimson'

DOWNLOADED = {'SE England, 2020-2022':config.AnalysisArgs(52.5,1.25,'20200121','20221231'),
              'US West Coast, 2020-2022':config.AnalysisArgs(36,-120,'20200121','20221231')}


st.set_page_config(layout="wide")

#@st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
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
    ax.set_xlim([pd.Timestamp(aa.start_date), pd.Timestamp(aa.end_date)])
    
    if len(varnames) > 1:
        ax.legend()

    if plot_cdi:
        markwatch = cdi['CDI'] == 1
        markwarning = cdi['CDI'] == 2
        markalert1 = cdi['CDI'] == 3
        markalert2 = cdi['CDI'] == 4

        lims = ax.get_ylim()
        h1 = ax.fill_between(df.index, *[-4,4], where=markwatch, facecolor=C_WATCH, alpha=.2)
        h2 = ax.fill_between(df.index, *[-4,4], where=markwarning, facecolor=C_WARNING, alpha=.2)
        h3 = ax.fill_between(df.index, *[-4,4], where=markalert1, facecolor=C_ALERT1, alpha=.2)
        h4 = ax.fill_between(df.index, *[-4,4], where=markalert2, facecolor=C_ALERT2, alpha=.2)

        ax.set_ylim(lims)

        ax.legend(handles=[h1,h2,h3,h4],labels=['Watch','Warning','Alert 1','Alert 2'])

    elif not warning==0: 
        markwarning = df[warning_var] < warning
        lims = ax.get_ylim()
        ax.fill_between(df.index, *[-4,4], where=markwarning, facecolor='red', alpha=.2)
        ax.set_ylim(lims)

    return fig, ax

@st.cache(hash_funcs={dri.DroughtIndex: id},allow_output_mutation=True)
def load_index(index: dri.DroughtIndex,cfg: config.Config,aa:config.AnalysisArgs):
    idx = index(cfg,aa)
    idx.download()
    idx.process()
    return idx

#@st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
def load_indices(aa,cf):

    # Make sure everything is already downloaded else it'll take ages
    spi = load_index(dri.SPI,cf,aa)
    sma_ecmwf = load_index(dri.SMA_ECMWF,cf,aa)
    sma_edo = load_index(dri.SMA_GDO,cf,aa)
    fapar = load_index(dri.FPAR_GDO,cf,aa)

    return spi, sma_ecmwf, sma_edo, fapar

#@st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
def load_cdi(aa: config.AnalysisArgs,cf: config.Config,sma_source,sma_var):
    aa_cdi = config.CDIArgs(
        latitude=aa.latitude,
        longitude=aa.longitude,
        start_date=aa.start_date,
        end_date=aa.end_date,
        sma_source=sma_source,
        sma_var=sma_var
    )
    cdi = load_index(dri.CDI,cf,aa_cdi)
    return cdi.data

# @st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
# def load_era_soilmoisture(fname):
#     return  xr.open_dataset(fname).isel(expver=0).mean(('latitude','longitude')).drop_vars('expver').to_dataframe()

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

cf = config.Config(outdir= 'output')

plot_options = {'SPI':False,
                #'Soil Water Vol. (ECMWF)':False,
                'SMA (ECMWF)':False,
                'SMA (EDO)':False,
                'fAPAR (EDO)': False}

with st.sidebar:

    # Input
    # lat = st.number_input('Latitude',min_value=-90.0,max_value=90.0,value=52.5)
    # lon = st.number_input('Longitude',min_value=-180.0,max_value=180.0,value=1.25)
    # sdate = st.date_input('Start date',value=datetime.date(2020,1,1))
    # edate = st.date_input('End date',value=datetime.date(2022,12,31))
    aa = DOWNLOADED[st.selectbox('Study area',DOWNLOADED.keys())]

    # Select view mode
    view = st.radio('View mode', ['CDI Breakdown','Index Comparison'])

    # COMPARE INDICES
    if view == 'Index Comparison':
        # configure inputs
        # aa = config.AnalysisArgs(
        #     latitude=lat,
        #     longitude=lon,
        #     start_date=sdate.strftime('%Y%m%d'),
        #     end_date=edate.strftime('%Y%m%d'),
        # )
        spi, sma_ecmwf, sma_edo, fpr = load_indices(aa,cf)

        df_spi = spi.data
        df_sma_ecmwf = sma_ecmwf.data
        df_sma_edo = sma_edo.data
        df_fpr = fpr.data

        #ds_swvl = load_era_soilmoisture(sma_ecmwf.download_obj_baseline.download_file_path)

        st.header('Compare Indices:')
        for itm in plot_options:
            plot_options[itm] = st.checkbox(itm,key=itm)
        print(plot_options)
        sma_level = st.selectbox('Soil Water Indicator Level',['1','2','3','4'])
        plot_cdi=False

    # CDI BREAKDOWN
    elif view == 'CDI Breakdown':
        sma_source = st.selectbox('SMA Source',['EDO','ECMWF'])
        if sma_source=='ECMWF':
            sma_var = st.selectbox('Soil Water Indicator Level',['zscore_swvl' + str(i) for i in ['1','2','3','4']])
        elif sma_source=='EDO':
            sma_var = 'smant'

        cdi = load_cdi(aa,cf,sma_source,sma_var)
        plot_cdi=True

col1,col2 = st.columns(2)
with col1:
    st.plotly_chart(draw_map(aa))

figs = []

if view == "Index Comparison":

    if plot_options['SPI']:
        fig, ax = plot(df_spi,['spi'],'Standardised Precipitation Index',warning=-1,warning_var='spi')
        figs.append(fig)

    # if plot_options['Soil Water Vol. (ECMWF)']:
    #     fig, ax = plot(ds_swvl,['swvl1','swvl2','swvl3','swvl4'],title='Soil Water Volume',showmean=True)
    #     figs.append(fig)

    if plot_options['SMA (ECMWF)']:
        fig, ax = plot(df_sma_ecmwf,['zscore_swvl'+ str(n) for n in[1,2,3,4]],title='Soil Moisture Anomaly (ECMWF)',warning=-1,warning_var='zscore_swvl{}'.format(sma_level))
        figs.append(fig)

    if plot_options['SMA (EDO)']:
        fig, ax = plot(df_sma_edo,['smant'],title='Ensemble Soil Moisture Anomaly (EDO)',warning=-1,warning_var='smant')
        figs.append(fig)

    if plot_options['fAPAR (EDO)']:
        fig, ax = plot(df_fpr,['fpanv'],title='Fraction of Absorbed Photosynthetically Active Radiation',warning=-1,warning_var='fpanv')
        figs.append(fig)

elif view == "CDI Breakdown":
    fig, ax = plot(cdi,['spi'],title='SPI')
    figs.append(fig)

    fig, ax = plot(cdi,[sma_var],title='SMA')
    figs.append(fig)

    fig, ax = plot(cdi,['fpanv'],title='fAPAR')
    figs.append(fig)


with col2:
    for f in figs:
        st.pyplot(f)
    




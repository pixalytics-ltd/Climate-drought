import os
import datetime
import glob
import numpy as np
import pandas as pd
from pandas.io.json import json_normalize
import geojson
import xarray as xr
import streamlit as st
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from typing import List

# Links from Climate-drought repository
from climate_drought import config, drought_indices as dri

OUTPUT_DIR = 'output'

C_WATCH = 'gold'
C_WARNING = 'darkorange'
C_ALERT1 = 'orangered'
C_ALERT2 = 'crimson'

DOWNLOADED = {'SE England, 2020-2022':config.AnalysisArgs(52.5,1.25,'20200121','20221231'),
    'US West Coast, 2020-2022':config.AnalysisArgs(36,-120,'20200121','20221231'),
    'Canada CPilot Report, 2022-2023': config.AnalysisArgs(55.5, -99.1, '20220131', '20230331')}

SMA_LEVEL_DEFAULT = 'zscore_swvl3'

# Have pre-loaded locations rather than Latitude/Longitude inputs
RESTRICT_DATA_SELECTION = True

# Load precip anomaly data from SAFE software
LOAD_SAFE = True

st.set_page_config(layout="wide")

# Load precip anomaly data from SAFE software
def load_safe():
    infile = os.path.join("input","cliteScenarios_rpc4.5_precipTotalMonPoints_MB_2023_2024.geojson")
    if not os.path.exists(infile):
        print("Could not load SAFE Software file")
        safe_df = []
    else:
        df = json_normalize(geojson["features"])
        coords = 'properties.geometry.coordinates'
        df_safe = (df[coords].apply(lambda r: [(i[0],i[1]) for i in r[0]])
            .apply(pd.Series).stack()
            .reset_index(level=1).rename(columns={0:coords,"level_1":"point"})
            .join(df.drop(coords,1), how='left')).reset_index(level=0)
        df_safe[['lat','long']] = df_safe[coords].apply(pd.Series)
        print("SAFE:",df_safe)


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
def load_indices(cdi: dri.CDI):

    # Make sure everything is already downloaded else it'll take ages
    spi_ecmwf = load_index(dri.SPI_ECMWF,cdi.config,cdi.aa_spi)
    spi_gdo = load_index(dri.SPI_GDO,cdi.config,cdi.aa_spi)
    sma_ecmwf = load_index(dri.SMA_ECMWF,cdi.config,cdi.aa_sma)
    sma_gdo = load_index(dri.SMA_GDO,cdi.config,cdi.aa_sma)
    fapar = load_index(dri.FPAR_GDO,cdi.config,cdi.aa_fpr)

    return spi_ecmwf, spi_gdo, sma_ecmwf, sma_gdo, fapar

@st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
def load_cdi(aa: config.AnalysisArgs,cf: config.Config,source,sma_var):
    aa_cdi = config.CDIArgs(
        latitude=aa.latitude,
        longitude=aa.longitude,
        start_date=aa.start_date,
        end_date=aa.end_date,
        spi_source=source,
        sma_source=source,
        sma_var=sma_var
    )
    cdi = load_index(dri.CDI,cf,aa_cdi)
    return cdi

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

plot_options = {'SPI (ECMWF)':False,
                'SPI (GDO)': False,
                'SMA (ECMWF)':False,
                'SMA (GDO)':False,
                'fAPAR (GDO)': False}

with st.sidebar:

    # Input
    if RESTRICT_DATA_SELECTION:
        aa = DOWNLOADED[st.selectbox('Study area',DOWNLOADED.keys())]
    else:
        with st.form('inputs'):
            lat = st.number_input('Latitude',min_value=-90.0,max_value=90.0,value=52.5)
            lon = st.number_input('Longitude',min_value=-180.0,max_value=180.0,value=1.25)
            sdate = st.date_input('Start date',value=datetime.date(2020,1,1))
            edate = st.date_input('End date',value=datetime.date(2022,12,31))
            submitted = st.form_submit_button("Submit")

        if submitted:
            aa = config.AnalysisArgs(
                latitude=lat,
                longitude=lon,
                start_date=sdate.strftime('%Y%m%d'),
                end_date=edate.strftime('%Y%m%d'),
            )
        else:
            aa = DOWNLOADED['SE England, 2020-2022']

    # Pre-download CDI options for speed
    cdi_gdo = load_cdi(aa,cf,'GDO','smant')

    # Only do ECMWF if data selection is restricted
    if RESTRICT_DATA_SELECTION:
        cdi_ecmwf = load_cdi(aa,cf,'ECMWF',SMA_LEVEL_DEFAULT)
        view = st.radio('View mode', ['CDI Breakdown','Index Comparison'])
    else:
        view = 'CDI Breakdown'

    if view == 'CDI Breakdown':
        sma_source = st.selectbox('SMA Source',['GDO','ECMWF']) if RESTRICT_DATA_SELECTION else 'GDO'
        if sma_source=='ECMWF': 
            # ERA5 data has multiple layers, so option to choose which layer is used
            sma_var = st.selectbox('Soil Water Indicator Level',['zscore_swvl' + str(i) for i in ['1','2','3','4']])

            # Need to re-initialise the object using the selected layer
            cdi_obj = cdi_ecmwf if sma_var == SMA_LEVEL_DEFAULT else load_cdi(aa,cf,'ECMWF',sma_var)

        elif sma_source=='GDO':
            # Re-use the object initialised earlier
            cdi_obj = cdi_gdo
        cdi = cdi_obj.data
        plot_cdi=True

    elif view == 'Index Comparison':

        #spi, sma_ecmwf, sma_edo, fpr = load_indices(cdi)

        df_spi_ecmwf = cdi_ecmwf.spi.data
        df_spi_gdo = cdi_gdo.spi.data
        df_sma_ecmwf = cdi_ecmwf.sma.data
        df_sma_edo = cdi_gdo.sma.data
        df_fpr = cdi_gdo.fpr.data

        if LOAD_SAFE:
            df_safe = load_safe()

        #ds_swvl = load_era_soilmoisture(sma_ecmwf.download_obj_baseline.download_file_path)

        st.header('Compare Indices:')
        for itm in plot_options:
            plot_options[itm] = st.checkbox(itm,key=itm)
        print(plot_options)
        sma_level = st.selectbox('Soil Water Indicator Level',['1','2','3','4'])
        plot_cdi=False



col1,col2 = st.columns(2)
with col1:
    st.plotly_chart(draw_map(aa))

figs = []

if view == "Index Comparison":

    if plot_options['SPI (ECMWF)']:
        fig, ax = plot(df_spi_ecmwf,['spi'],'Standardised Precipitation Index (ECMWF)',warning=-1,warning_var='spi')
        figs.append(fig)

    if plot_options['SPI (GDO)']:
        fig, ax = plot(df_spi_gdo,['spg03'],'Standardised Precipitation Index (GDO)',warning=-1,warning_var='spg03')
        figs.append(fig)

    # if plot_options['Soil Water Vol. (ECMWF)']:
    #     fig, ax = plot(ds_swvl,['swvl1','swvl2','swvl3','swvl4'],title='Soil Water Volume',showmean=True)
    #     figs.append(fig)

    if plot_options['SMA (ECMWF)']:
        fig, ax = plot(df_sma_ecmwf,['zscore_swvl'+ str(n) for n in[1,2,3,4]],title='Soil Moisture Anomaly (ECMWF)',warning=-1,warning_var='zscore_swvl{}'.format(sma_level))
        figs.append(fig)

    if plot_options['SMA (GDO)']:
        fig, ax = plot(df_sma_edo,['smant'],title='Ensemble Soil Moisture Anomaly (GDO)',warning=-1,warning_var='smant')
        figs.append(fig)

    if plot_options['fAPAR (GDO)']:
        fig, ax = plot(df_fpr,['fpanv'],title='Fraction of Absorbed Photosynthetically Active Radiation',warning=-1,warning_var='fpanv')
        figs.append(fig)

elif view == "CDI Breakdown":
    fig, ax = plot(cdi,[cdi_obj.args.spi_var],title='SPI')
    figs.append(fig)

    fig, ax = plot(cdi,[cdi_obj.args.sma_var],title='SMA')
    figs.append(fig)

    fig, ax = plot(cdi,['fpanv'],title='fAPAR')
    figs.append(fig)


with col2:
    for f in figs:
        st.pyplot(f)
    




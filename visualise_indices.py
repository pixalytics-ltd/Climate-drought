import datetime
import numpy as np
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from typing import List

# Links from Climate-drought repository
from climate_drought import config, drought_indices as dri

# Colours to highlight plots in
C_WATCH = 'gold'
C_WARNING = 'darkorange'
C_ALERT1 = 'orangered'
C_ALERT2 = 'crimson'

# Ensure input paths point to GDO data and output to ECMWF (TODO JC Move ECMWF netcdfs to input)
CONFIG = config.Config(outdir= 'output')

# If RESTRICT_DATA_SELECTION=True, use these arguments
DOWNLOADED = {'SE England, 2020-2022':config.AnalysisArgs(52.5,1.25,'20200121','20221231'),
              'US West Coast, 2020-2022':config.AnalysisArgs(36,-120,'20200121','20221231')}

# If RESTRICT_DATA_SELECTION=True and we're viewing 
SMA_LEVEL_DEFAULT = 'zscore_swvl3'

st.set_page_config(layout="wide")


# ------- PREPARE DATA ----------

with st.sidebar:
     aa = DOWNLOADED[st.selectbox('Study area',DOWNLOADED.keys())]

# Instantiate dummy CDI
dcdi = dri.CDI(CONFIG,config.CDIArgs(aa.latitude,aa.longitude,aa.start_date,aa.end_date))

# Load all indices
@st.cache(hash_funcs={dri.DroughtIndex: id}, allow_output_mutation=True)
def load_index(index: dri.DroughtIndex,aa:config.AnalysisArgs):
    idx = index(CONFIG,aa)
    idx.download()
    idx.process()
    return idx

spi_ecmwf = load_index(dri.SPI_ECMWF,dcdi.aa_spi)
spi_gdo = load_index(dri.SPI_GDO,dcdi.aa_spi)
sma_ecmwf = load_index(dri.SMA_ECMWF,dcdi.aa_sma)
sma_gdo = load_index(dri.SMA_GDO,dcdi.aa_sma)
fapar = load_index(dri.FPAR_GDO,dcdi.aa_fpr)

# --------- PLOT SELECTION -----------

plot_options = {'SPI (ECMWF)':False,
                'SPI (GDO)': False,
                'SMA (ECMWF)':False,
                'SMA (GDO)':False,
                'fAPAR (GDO)': False}

with st.sidebar:
    st.header('Compare Indices:')
    for itm in plot_options:
        plot_options[itm] = st.checkbox(itm,key=itm)
    
    if plot_options['SMA (ECMWF)']:
        sma_level = st.radio('Soil Water Indicator Level',['1','2','3','4'])

# -------- COMPUTE CDI ----------

with st.sidebar:
    plot_cdi = st.checkbox('Show CDI')

    if plot_cdi:
        spi_source = st.selectbox('SPI Source:',['GDO','ECMWF'])
        sma_source = st.selectbox('SMA Source:',['GDO','ECMWF'])
        if sma_source == 'ECMWF':
            sma_var = zscore_swvl = st.radio('Soil Water Indicator Level',['1','2','3','4'])
        else:
            sma_var = 'smant'

if plot_cdi:
    aa_cdi = config.CDIArgs(
        latitude=aa.latitude,
        longitude=aa.longitude,
        start_date=aa.start_date,
        end_date=aa.end_date,
        spi_source=spi_source,
        sma_source=sma_source,
        sma_var=sma_var
    )
    cdi = load_index(dri.CDI,aa_cdi).data

# ----------- DRAW -------------

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

col1,col2 = st.columns(2)
with col1:
    st.plotly_chart(draw_map(aa))

figs = []

if plot_options['SPI (ECMWF)']:
    fig, ax = plot(spi_ecmwf.data,['spi'],'Standardised Precipitation Index (ECMWF)',warning=-1,warning_var='spi')
    figs.append(fig)

if plot_options['SPI (GDO)']:
    fig, ax = plot(spi_gdo.data,['spg03'],'Standardised Precipitation Index (GDO)',warning=-1,warning_var='spg03')
    figs.append(fig)

if plot_options['SMA (ECMWF)']:
    fig, ax = plot(sma_ecmwf.data,['zscore_swvl'+ str(n) for n in[1,2,3,4]],title='Soil Moisture Anomaly (ECMWF)',warning=-1,warning_var='zscore_swvl{}'.format(sma_level))
    figs.append(fig)

if plot_options['SMA (GDO)']:
    fig, ax = plot(sma_gdo.data,['smant'],title='Ensemble Soil Moisture Anomaly (GDO)',warning=-1,warning_var='smant')
    figs.append(fig)

if plot_options['fAPAR (GDO)']:
    fig, ax = plot(fapar.data,['fpanv'],title='Fraction of Absorbed Photosynthetically Active Radiation',warning=-1,warning_var='fpanv')
    figs.append(fig)


with col2:
    for f in figs:
        st.pyplot(f)
    




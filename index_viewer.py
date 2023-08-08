import logging
import datetime
import logging
import numpy as np
import pandas as pd
import io
import cv2
from PIL import Image
import streamlit as st
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from typing import List

# Links from Climate-drought repository
from climate_drought import config, drought_indices as dri
from climate_drought import load_feature_file as local

# Logging
logging.basicConfig(level=logging.INFO)

OUTPUT_DIR = 'output'

v1 = False # Updated colours to create better seperation
if v1:
    C_WATCH = 'gold'
    C_WARNING = 'darkorange'
    C_ALERT1 = 'orangered'
    C_ALERT2 = 'crimson'
else:
    C_WATCH = 'yellow'
    C_WARNING = 'darkorange'
    C_ALERT1 = 'red'
    C_ALERT2 = 'darkred'

DOWNLOADED = {'SE England, 2020-2022':config.AnalysisArgs(52.5,1.25,'20200121','20221231',singleval=True),
              'US West Coast, 2020-2022':config.AnalysisArgs(36,-120,'20200121','20221231',singleval=True),
              'Canada Pilot Report, 2020-2022': config.AnalysisArgs(55.5, -99.1, '20200131', '20221231',singleval=True),
                  'Canada with Safe extraction of climate forecast data, 2022-2022+': config.AnalysisArgs(50.06, -97.49, '20220131', '20221231',singleval=True)}

SMA_LEVEL_DEFAULT = 'zscore_swvl3'


SMA_LEVEL_DEFAULT = 'zscore_swvl3'

# Use pre-loaded locations rather than Latitude/Longitude inputs
RESTRICT_DATA_SELECTION = True

st.set_page_config(layout="wide")


def plot(df:pd.DataFrame,varnames:List[str],title:str,showmean=False,warning=0,warning_var=None):

    fig, ax = plt.subplots(figsize=(10,3))
    time = df.time.values

    for var in varnames:
        #st.info("{} {} {}".format(var, time, df[var]))
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
        h1 = ax.fill_between(time, *[-4,4], where=markwatch, facecolor=C_WATCH, alpha=.2)
        h2 = ax.fill_between(time, *[-4,4], where=markwarning, facecolor=C_WARNING, alpha=.2)
        h3 = ax.fill_between(time, *[-4,4], where=markalert1, facecolor=C_ALERT1, alpha=.2)
        h4 = ax.fill_between(time, *[-4,4], where=markalert2, facecolor=C_ALERT2, alpha=.2)

        ax.set_ylim(lims)

        ax.legend(handles=[h1,h2,h3,h4],labels=['Watch','Warning','Alert 1','Alert 2'])

    elif not warning==0: 
        markwarning = df[warning_var] < warning
        lims = ax.get_ylim()
        ax.fill_between(time, *[-4,4], where=markwarning, facecolor='red', alpha=.2)
        ax.set_ylim(lims)

    return fig

@st.cache(hash_funcs={dri.DroughtIndex: id},allow_output_mutation=True)
def load_index(index: dri.DroughtIndex,cfg: config.Config,aa:config.AnalysisArgs):
    idx = index(cfg,aa)
    idx.download()
    idx.process()
    return idx

#@st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
def load_indices(cdi: dri.CDI):

    # Make sure everything is already downloaded else it'll take ages
    logging.info("Calculating ECMWF SPI")
    spi_ecmwf = load_index(dri.SPI_ECMWF,cdi.config,cdi.aa_spi)
    logging.info("Calculating GDO SPI")
    spi_gdo = load_index(dri.SPI_GDO,cdi.config,cdi.aa_spi)
    logging.info("Calculating ECMWF SMA")
    sma_ecmwf = load_index(dri.SMA_ECMWF,cdi.config,cdi.aa_sma)
    logging.info("Calculating GDO SMA")
    sma_gdo = load_index(dri.SMA_GDO,cdi.config,cdi.aa_sma)
    logging.info("Calculating FAPAR")
    fapar = load_index(dri.FPAR_GDO,cdi.config,cdi.aa_fpr)

    # Load precip anomaly data from SAFE software
    if aa.latitude == 50.06:
        safe = local.LoadSAFE(logger=logging)
        spi_ecmwf = safe.load_safe(spi_ecmwf, lat_val=aa.latitude, lon_val=aa.longitude)
        aa.end_date = '20241231'

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
        sma_var=sma_var,
        singleval=aa.singleval
    )
    logging.info("Calculating CDI")
    cdi = load_index(dri.CDI,cf,aa_cdi)

    return cdi

# @st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
# def load_era_soilmoisture(fname):
#     return  xr.open_dataset(fname).isel(expver=0).mean(('latitude','longitude')).drop_vars('expver').to_dataframe()

@st.cache(hash_funcs={pd.DataFrame: id}, allow_output_mutation=True)
def draw_map(aa):
    boxsz = 0.1
    latmax = np.nanmax(aa.latitude) + boxsz
    lonmin = np.nanmin(aa.longitude) - boxsz
    latmin = np.nanmin(aa.latitude) - boxsz
    lonmax = np.nanmax(aa.longitude) + boxsz

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

plot_options = {'Precip (ECMWF)':False,
                'SPI (ECMWF)':False,
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
                singleval = True
            )
        else:
            aa = DOWNLOADED['SE England, 2020-2022']

    # Pre-download CDI options for speed and process CDI calc
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
        cdi = cdi_obj.data_df
        #st.info("CDI: {}".format(cdi))
        plot_cdi=True

    elif view == 'Index Comparison':

        #spi, sma_ecmwf, sma_edo, fpr = load_indices(cdi)

        df_spi_ecmwf = cdi_ecmwf.spi.data_df
        df_spi_gdo = cdi_gdo.spi.data_df
        df_sma_ecmwf = cdi_ecmwf.sma.data_df
        df_sma_edo = cdi_gdo.sma.data_df
        df_fpr = cdi_gdo.fpr.data_df

        # Load precip anomaly data from SAFE software
        if aa.latitude == 50.06:

            safe = local.LoadSAFE(logger=logging)
            df_spi_ecmwf = safe.load_safe(df_spi_ecmwf, lat_val=aa.latitude, lon_val=aa.longitude)
            aa.end_date = '20241231'

        #ds_swvl = load_era_soilmoisture(sma_ecmwf.download_obj_baseline.download_file_path)

        st.header('Compare Indices:')
        for itm in plot_options:
            plot_options[itm] = st.checkbox(itm,key=itm)
        #st.info(plot_options)
        sma_level = st.selectbox('Soil Water Indicator Level',['1','2','3','4'])
        plot_cdi=False



col1,col2 = st.columns(2)
with col1:
    st.plotly_chart(draw_map(aa))

figs = []

if view == "Index Comparison":

    if plot_options['Precip (ECMWF)']:
        fig = plot(df_spi_ecmwf,['tp'],'Precipitation (ECMWF)',warning=-1,warning_var='tp')
        figs.append(fig)

    if plot_options['SPI (ECMWF)']:
        fig = plot(df_spi_ecmwf,['spi'],'Standardised Precipitation Index (ECMWF)',warning=-1,warning_var='spi')
        figs.append(fig)

    if plot_options['SPI (GDO)']:
        fig = plot(df_spi_gdo,['spg03'],'Standardised Precipitation Index (GDO)',warning=-1,warning_var='spg03')
        figs.append(fig)

    # if plot_options['Soil Water Vol. (ECMWF)']:
    #     fig = plot(ds_swvl,['swvl1','swvl2','swvl3','swvl4'],title='Soil Water Volume',showmean=True)
    #     figs.append(fig)

    if plot_options['SMA (ECMWF)']:
        fig = plot(df_sma_ecmwf,['zscore_swvl'+ str(n) for n in[1,2,3,4]],title='Soil Moisture Anomaly (ECMWF)',warning=-1,warning_var='zscore_swvl{}'.format(sma_level))
        figs.append(fig)

    if plot_options['SMA (GDO)']:
        fig = plot(df_sma_edo,['smant'],title='Ensemble Soil Moisture Anomaly (GDO)',warning=-1,warning_var='smant')
        figs.append(fig)

    if plot_options['fAPAR (GDO)']:
        fig = plot(df_fpr,['fpanv'],title='Fraction of Absorbed Photosynthetically Active Radiation',warning=-1,warning_var='fpanv')
        figs.append(fig)

elif view == "CDI Breakdown":

    fig = plot(cdi,[cdi_obj.args.spi_var],title='SPI')
    figs.append(fig)

    fig = plot(cdi,[cdi_obj.args.sma_var],title='SMA')
    figs.append(fig)

    fig = plot(cdi,['fpanv'],title='fAPAR')
    figs.append(fig)

# Display plots and make available to download
buf = io.BytesIO()
fn = 'output.png'
with col2:
    for i,fig in enumerate(figs):
        st.pyplot(fig)
        fig.savefig(buf, format='png', dpi=600)
        buf.seek(0)
        img_arr = np.frombuffer(buf.getvalue(), dtype=np.uint8)
        img = cv2.imdecode(img_arr, 1)
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if i == 0:
            v_img = img.copy()
        else:
            v_img = cv2.vconcat([v_img, img])

    #cv2.imwrite(fn, v_img)

    def process_image(v_img):
        buf = io.BytesIO()
        fig, ax = plt.subplots()
        ax.imshow(v_img)
        plt.axis('off')
        ax.axes.get_xaxis().set_visible(False)
        ax.axes.get_yaxis().set_visible(False)
        fig.savefig(buf, format='png', dpi=600, bbox_inches='tight', pad_inches = 0)
        return buf

    if len(figs) > 0:

        btn = st.download_button(
            label="Download image",
            data=process_image(v_img),
            file_name=fn,
            mime="image/png"
        )



import argparse
import datetime
import glob
import numpy as np
import xarray as xr
import streamlit as st
import matplotlib.pyplot as plt
import plotly.graph_objects as go

# Links from Climate-drought repository
from climate_drought import indices

# Script to generate a web app to view and interact with Index input and output data.
# To run:
# - change 'OUTPUT_DIR' to location of netcdf files
# - in the command line, activate climate-env
# - enter 'streamlit run index_viewer.py'
# The web app will start up in a window in your browser.

OUTPUT_DIR = 'output'

st.set_page_config(layout="wide")

@st.cache(hash_funcs={xr.core.dataset.Dataset: id}, allow_output_mutation=True)
def loadnc(fname):
    return xr.open_dataset(fname)
    
with st.sidebar:
    fname = None
    fname = st.selectbox('Select dataset',glob.glob(OUTPUT_DIR + '/soil*.nc'))

if fname:
    data = loadnc(fname)
    resamp = data.tp.max(['latitude', 'longitude']).load()
    precip = resamp[:, 0]

    with st.sidebar:
        st.header('Selected dataset: ')
        # TODO JC 27/03/23 Make more robust against different filenames
        latlon = fname.split('_')[3:]
        latitude = latlon[0]
        longitude = latlon[1].split('.nc')[0]
        st.write('Latitude = ' + latitude)
        st.write('Longitude = ' + longitude)

        start_date=st.date_input(label='Start',value=datetime.date(2020,5,3))
        end_date=st.date_input(label='End',value=datetime.date(2022,5,2))

    # Select requested time slice
    sdate = r'{}-{}-{}'.format(start_date.year,start_date.month,start_date.day)
    edate = r'{}-{}-{}'.format(end_date.year,end_date.month,end_date.day)


    latitude = float(latitude)
    longitude = float(longitude)

    boxsz = 0.1
    latmax=latitude + boxsz
    lonmin=longitude - boxsz
    latmin=latitude - boxsz
    lonmax=longitude + boxsz

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
            'center': {'lon': longitude, 'lat': latitude },
            'zoom': 7},
        showlegend = False)

    col1,col2 = st.columns(2)
    with col1:
        st.plotly_chart(fig)

    fig1,ax = plt.subplots(figsize=(10,3))
    ax.plot(df_filtered.index,df_filtered.tp,label='Precipitation')
    ax.set_title('Total Precipitation')
    ax.grid()

    fig2,ax = plt.subplots(figsize=(10,3))
    ax.plot(df_filtered.index,df_filtered.spi,label='SPI')
    ax.set_title('Standardized Precipitation Index')
    ax.grid()

warning = df_filtered.spi < -1
lims = ax.get_ylim()
ax.fill_between(df_filtered.index, *[-4,4], where=warning, facecolor='red', alpha=.2)
ax.set_ylim(lims)

with col2:
    st.pyplot(fig1)
    st.pyplot(fig2)




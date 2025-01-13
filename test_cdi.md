---
jupyter:
  jupytext:
    formats: ipynb,md
    text_representation:
      extension: .md
      format_name: markdown
      format_version: '1.3'
      jupytext_version: 1.16.6
  kernelspec:
    display_name: climate_env
    language: python
    name: python3
---

```python
# ensure classes imported from .py files are dynamically updated
%load_ext autoreload
%autoreload 2

# plot matplots nicely
%matplotlib inline  
```

```python
import numpy as np
import pandas as pd
import datetime
import xarray as xr
from climate_drought import config, drought_indices as dri, utils
import matplotlib.pyplot as plt

```

```python
# Set up analysis args
# pt = point, bb = bounding box, pn = polygon
cf = config.Config(outdir= 'output',indir='input',verbose=False)
aa_pt = config.AnalysisArgs(latitude=38.5,longitude=-119.5,start_date='20210121',end_date='20230531',oformat='cov')
aa_bb = config.AnalysisArgs(latitude=[38.5,40.5],longitude=[-119.5,-117.5],start_date='20210121',end_date='20230531')
aa_pn = config.AnalysisArgs(latitude=[38.5,40.5,38,38.5,38.5],longitude=[-119.5,-117.5,-118,-117.5,-116.5],start_date='20210121',end_date='20230531',oformat='cov')
```

```python
# create cdi args, using already created args
caa_pn = config.CDIArgs(aa_pn.latitude,aa_pn.longitude,aa_pn.start_date,aa_pn.end_date,oformat='cov')
caa_bb = config.CDIArgs(aa_bb.latitude,aa_bb.longitude,aa_bb.start_date,aa_bb.end_date,oformat='csv')
caa_pt = config.CDIArgs(aa_pt.latitude,aa_pt.longitude,aa_pt.start_date,aa_pn.end_date)
```

```python
# initialise a point, bounding box and polygon cdi
cdi_pt = dri.CDI(cf,caa_pt)
cdi_bb = dri.CDI(cf,caa_bb)
cdi_pn = dri.CDI(cf,caa_pn)
```

```python
# ensure data is downloaded
cdi_pt.download()
cdi_bb.download()
cdi_pn.download()
```

```python
cdi_pt.process()
cdi_bb.process()
cdi_pn.process()
```

```python
# check impact of time reindexing using point cdi
fig, axs = plt.subplots(4,1,figsize=(12,10))
spi_pre = cdi_pt.spi.data_ds.spg03.squeeze()
spi_pro = cdi_pt.data_ds.spg03.squeeze()
sma_pre = cdi_pt.sma.data_ds.smant.squeeze()
sma_pro = cdi_pt.data_ds.smant.squeeze()
fpr_pre = cdi_pt.fpr.data_ds.fpanv.squeeze()
fpr_pro = cdi_pt.data_ds.fpanv.squeeze()
cdi_pro = cdi_pt.data_ds.CDI.squeeze()
axs[0].plot(spi_pre.time,spi_pre)
axs[0].plot(spi_pro.time,spi_pro)
xg = axs[0].get_xlim()
axs[1].plot(sma_pre.time,sma_pre)
axs[1].plot(sma_pro.time,sma_pro)
axs[1].set_xlim(xg)
axs[2].plot(fpr_pre.time,fpr_pre)
axs[2].plot(fpr_pro.time,fpr_pro)
axs[2].set_xlim(xg)
axs[3].plot(cdi_pro.time,cdi_pro)
axs[3].set_xlim(xg)
```

```python
fig, axs = plt.subplots(4,1,figsize=(12,10))
spi_pre = cdi_bb.spi.data_ds.sel({'latitude':aa_pt.latitude,'longitude':aa_pt.longitude},method='nearest').spg03.squeeze()
spi_pro = cdi_bb.data_ds.sel({'latitude':aa_pt.latitude,'longitude':aa_pt.longitude},method='nearest').spg03.squeeze()
sma_pre = cdi_bb.sma.data_ds.sel({'latitude':aa_pt.latitude,'longitude':aa_pt.longitude},method='nearest').smant.squeeze()
sma_pro = cdi_bb.data_ds.sel({'latitude':aa_pt.latitude,'longitude':aa_pt.longitude},method='nearest').smant.squeeze()
fpr_pre = cdi_bb.fpr.data_ds.sel({'latitude':aa_pt.latitude,'longitude':aa_pt.longitude},method='nearest').fpanv.squeeze()
fpr_pro = cdi_bb.data_ds.sel({'latitude':aa_pt.latitude,'longitude':aa_pt.longitude},method='nearest').fpanv.squeeze()
cdi_pro = cdi_bb.data_ds.sel({'latitude':aa_pt.latitude,'longitude':aa_pt.longitude},method='nearest').CDI.squeeze()
axs[0].plot(spi_pre.time,spi_pre)
axs[0].plot(spi_pro.time,spi_pro)
xg = axs[0].get_xlim()
axs[1].plot(sma_pre.time,sma_pre)
axs[1].plot(sma_pro.time,sma_pro)
axs[1].set_xlim(xg)
axs[2].plot(fpr_pre.time,fpr_pre)
axs[2].plot(fpr_pro.time,fpr_pro)
axs[2].set_xlim(xg)
axs[3].plot(cdi_pro.time,cdi_pro)
axs[3].set_xlim(xg)
```

```python
# check interpolation method using bbox data
t=pd.Timestamp(2021,5,1)

fig, axs = plt.subplots(3,2,figsize=(8,10))
spi_raw = cdi_bb.spi.data_ds.spg03.sel(time=t,method='nearest')
sma_raw = cdi_bb.sma.data_ds.smant.sel(time=t,method='nearest')
fpr_raw = cdi_bb.fpr.data_ds.fpanv.sel(time=t,method='nearest')
spi_pro = cdi_bb.data_ds.spg03.sel(time=t,method='nearest')
sma_pro = cdi_bb.data_ds.smant.sel(time=t,method='nearest')
fpr_pro = cdi_bb.data_ds.fpanv.sel(time=t,method='nearest')


def plot_regridded(ax,da,da2,title):
    c1=ax[0].pcolor(da.longitude,da.latitude,da,vmin=-1.5,vmax=1.5)
    c2=ax[1].pcolor(da2.longitude,da2.latitude,da2,vmin=-1.5,vmax=1.5)
    fig.colorbar(c1,ax=ax[0])
    fig.colorbar(c2,ax=ax[1])
    ax[0].set_title(title + ' raw')
    ax[1].set_title(title + ' regridded')

plot_regridded(axs[0],spi_raw,spi_pro,'SPI')
plot_regridded(axs[1],sma_raw,sma_pro,'SMA')
plot_regridded(axs[2],fpr_raw,fpr_pro,'FAPAR')



```

```python
# check interpolation method using polygon data
t=pd.Timestamp(2021,5,1)

fig, axs = plt.subplots(3,2,figsize=(8,10))
spi_raw = cdi_pn.spi.data_ds.spg03.sel(time=t,method='nearest')
sma_raw = cdi_pn.sma.data_ds.smant.sel(time=t,method='nearest')
fpr_raw = cdi_pn.fpr.data_ds.fpanv.sel(time=t,method='nearest')
spi_pro = cdi_pn.data_ds.spg03.sel(time=t,method='nearest')
sma_pro = cdi_pn.data_ds.smant.sel(time=t,method='nearest')
fpr_pro = cdi_pn.data_ds.fpanv.sel(time=t,method='nearest')


def plot_regridded(ax,da,da2,title):
    da=da.where(da != dri.OUTSIDE_AREA_SELECTION,drop=True)
    da2=da2.where(da2 != dri.OUTSIDE_AREA_SELECTION,drop=True)
    c1=ax[0].pcolor(da.longitude,da.latitude,da,vmin=-1.5,vmax=1.5)
    c2=ax[1].pcolor(da2.longitude,da2.latitude,da2,vmin=-1.5,vmax=1.5)
    fig.colorbar(c1,ax=ax[0])
    fig.colorbar(c2,ax=ax[1])
    ax[0].set_title(title + ' raw')
    ax[1].set_title(title + ' regridded')

plot_regridded(axs[0],spi_raw,spi_pro,'SPI')
plot_regridded(axs[1],sma_raw,sma_pro,'SMA')
plot_regridded(axs[2],fpr_raw,fpr_pro,'FAPAR')



```

```python
print(cdi_bb.sma.data_ds.smant.sel({'latitude':38.5,'longitude':-118.5},method='nearest').isel(time=15).values)
print(cdi_pn.sma.data_ds.smant.sel({'latitude':38.5,'longitude':-118.5},method='nearest').isel(time=15).values)
print(cdi_bb.data_ds.smant.sel({'latitude':38.5,'longitude':-118.5},method='nearest').isel(time=15).values)
print(cdi_pn.data_ds.smant.sel({'latitude':38.5,'longitude':-118.5},method='nearest').isel(time=15).values)


```

```python
da_sma = cdi_pt.sma.data_ds.smant
da = da_sma.reindex({'time': cdi_pt.time_dekads})
da.interp({'latitude'}=36,method='nearest')
```

```python
cdi_pt.process()
```

```python
sma_pt = dri.SMA_GDO(cf,aa_pt)
sma_bb = dri.SMA_GDO(cf,aa_bb)
sma_pn = dri.SMA_GDO(cf,aa_pn)
spi_pt = dri.SPI_GDO(cf,aa_pt)
spi_bb = dri.SPI_GDO(cf,aa_bb)
spi_pn = dri.SPI_GDO(cf,aa_pn)
fpr_pt = dri.FPAR_GDO(cf,aa_pt)
fpr_bb = dri.FPAR_GDO(cf,aa_bb)
fpr_pn = dri.FPAR_GDO(cf,aa_pn)
```

```python
sma_pt.download()
sma_bb.download()
sma_pn.download()
```

```python
spi_pt.download()
spi_bb.download()
spi_pn.download()
```

```python
fpr_pt.download()
fpr_bb.download()
fpr_pn.download()
```

```python
sma_pt.process()
```

```python
sma_bb.process()
```

```python
sma_pn.process()
```

```python
spi_pt.process()
spi_bb.process()
spi_pn.process()
```

```python
fpr_pt.process()
fpr_bb.process()
fpr_pn.process()
```

```python
caa = config.CDIArgs(aa_pn.latitude,aa_pn.longitude,aa_pn.start_date,aa_pn.end_date,oformat='cov')
caa = config.CDIArgs([36],[-120],aa_pt.start_date,aa_pn.end_date,oformat='csv')

```

```python
cdi = dri.CDI(cf,caa)
cdi.download()
```

```python
cdi.process()
```

```python
spi_era = dri.SPI_ECMWF(cf,aa_pn)
spi_era.download()
```

```python
spi_era.process()
```

```python
spi_era.data_ds.spi.isel(time=10).plot()
```

```python
aa_pt = config.AnalysisArgs(latitude=38.5,longitude=-119.5,start_date='20210121',end_date='20210411',oformat='cov')
aa_bb = config.AnalysisArgs(latitude=[38.5,40.5],longitude=[-119.5,-117.5],start_date='20210121',end_date='20210411',oformat='csv')
aa_pn = config.AnalysisArgs(latitude=[38.5,40.5,38,38.5,38.5],longitude=[-119.5,-117.5,-118,-117.5,-116.5],start_date='20210121',end_date='20210411',oformat='csv')
```

```python
sma_ecmwf = dri.SMA_ECMWF(cf,aa_pn)
sma_ecmwf.download()
```

```python
sma_ecmwf.process()
```

```python
sma_ecmwf.data_ds.swvl3.isel(time=4).plot()
```

```python
ds=xr.open_dataset('output/soilwater_20210121-20210411_38.5-40.5_-119.5--117.5_hourly.nc')
#ds = ds.sortby('time').resample({'time':'1D'}).mean()
```

```python
utils.ds_to_dekads(ds)
```

```python
ds.assign(day=)
```

```python
time = ds.time.to_numpy()
time = pd.date_range(aa_pn.start_date,aa_pn.end_date,freq='1h')
ds = ds.reindex({'time':time},method='ffill')
fig,ax = plt.subplots()
ax.plot(np.diff(time),'.')

```

```python
ds.time.to_numpy()
```

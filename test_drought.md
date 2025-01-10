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
    name: climate_env
---

```python
import os
import sys
import numpy as np
import matplotlib.pyplot as plt
import argparse

import geojson

# import drought indicies
from climate_drought import drought_indices as dri, config

INDEX_MAP = {
    'SPI_ECMWF': dri.SPI_ECMWF,
    'SPI_GDO': dri.SPI_GDO,
    'SPI_NCG': dri.SPI_NCG,
    'SMA_ECMWF': dri.SMA_ECMWF,
    'SMA_GDO': dri.SMA_GDO,
    'fAPAR': dri.FPAR_GDO,
    'CDI': dri.CDI,
    'FEATURE_SAFE': dri.FEATURE_SAFE,
    'UTCI': dri.UTCI
}

```

```python
class Drought:
    def __init__(self,product,latitude,longitude,start_date,end_date):
        # Setup paramaters
        self.verbose = True

        self.indir = '/home/seadas/sajh/pixinternal/Climate-drought/input'
        self.outdir = '/home/seadas/sajh/pixinternal/Climate-drought/output'
        self.oformat = 'GeoJSON'
        self.product = product
        self.start_date = start_date
        self.end_date = end_date
        
        # Convert latitude and longitude strings to lists
        self.latitude = [float(item) for item in latitude.replace('[','').replace(']','').split(',')]
        self.longitude = [float(item) for item in longitude.replace('[','').replace(']','').split(',')]

        # setup config and args
        self.cfg = config.Config(self.outdir,self.indir)
        self.args = config.AnalysisArgs(latitude,longitude,
            start_date,end_date,product=product,oformat=self.oformat)

```

```python
product = "UTCI"
latitude = '52.5' 
longitude = '1.25'
start_date = '20220101'
end_date = '20221231'

print("Running {} for {} {} from {} to {}".format(product, 
    latitude, longitude, start_date, end_date))
 
obj = Drought(product,latitude,longitude,start_date,end_date)
```

```python
# Run processing
def drought_index(obj) -> dri.DroughtIndex:
   return INDEX_MAP[obj.product](obj.cfg, obj.args)

idx = drought_index(obj)

print("Computing {} index for {} to {}.".format(obj.product, 
    obj.cfg.baseline_start, obj.cfg.baseline_end))

if os.path.exists(idx.output_file_path):
    print("Processed file '{}' already exists.".format(idx.output_file_path))
else:
    idx.download()
    idx.process()
    print("Downloading and processing complete for '{}' completed with format {}.".format(idx.output_file_path, obj.oformat))

if os.path.exists(idx.output_file_path):
    exit_code = 1
    print("{} processing complete, generated {}".format(product, idx.output_file_path))

else:
    print("Processing failed, {} does not exist".format(idx.output_file_path))

```

```python
import geopandas as gpd

# Load in data and display then plot
df = gpd.read_file(idx.output_file_path)
print(df)

```

```python
# plotting

fig, ax1 = plt.subplots()
ax1.plot(df._date,df.spi,color='b',label='spi')
ax1.set_ylabel('SPI [blue]')
tick_list = df._date.values[::3]
plt.xticks(rotation=45, ticks=tick_list)
if product == 'UTCI':
    ax1.plot(df._date,df.hindex,color='g',label='utci')
    ax1.set_ylabel('SPI [blue], Health index [green]')
    ax2 = ax1.twinx()
    ax2.plot(df._date, df.utci, color = 'r', label = 'utci')
    ax2.set_ylabel('UTCI [degC, red]')
plt.tight_layout()
plt.show()      
```

```python

```

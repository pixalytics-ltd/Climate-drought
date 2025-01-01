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
from sys import exit
import numpy as np
import geopandas as gpd
import matplotlib.pyplot as plt
import argparse

# Links from Climate-drought repository
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
# Setup paramaters
verbose = True

indir = '/home/seadas/sajh/pixinternal/Climate-drought/input'
outdir = '/home/seadas/sajh/pixinternal/Climate-drought/output'
oformat = 'GeoJSON'

product = "UTCI"
latitude = '52.5' 
longitude = '1.25'
start_date = '19900101'
end_date = '19941231'

print("Running {} for {} {} from {} to {}".format(product, latitude, longitude, start_date, end_date))
```

```python
# Convert latitude and longitude strings to lists
latitude = [float(item) for item in latitude.replace('[','').replace(']','').split(',')]
longitude = [float(item) for item in longitude.replace('[','').replace(']','').split(',')]

# setup config and args
config = config.Config(outdir,indir)
args = config.AnalysisArgs(latitude,longitude,start_date,end_date,
    product=product,oformat=oformat)
 
```

```python
# Run processing
def index(product,config,args) -> dri.DroughtIndex:
   return INDEX_MAP[product](config, args)

idx = index

if os.path.exists(idx.output_file_path):
    self.logger.info("Processed file '{}' already exists.".format(idx.output_file_path))
else:
    idx.download()
    idx.process()
    self.logger.info("Downloading and processing complete for '{}' completed with format {}.".format(idx.output_file_path, self.args.oformat))

if os.path.exists(idx.output_file_path):
    exit_code = 1
    self.logger.info("{} processing complete, generated {}".format(self.product, idx.output_file_path))

else:
    self.logger.info("Processing failed, {} does not exist".format(idx.output_file_path))

```

```python
# Load in data and display then plot
df = gpd.read_file(idx.output_file_path)
print(df)
fig, ax1 = plt.subplots()
ax1.plot(df._date,df.spi,color='b',label='spi')
ax1.set_ylabel('SPI')
tick_list = df._date.values[::3]
plt.xticks(rotation=45, ticks=tick_list)
if self.product == 'UTCI':
    ax2 = ax1.twinx()
    ax2.plot(df._date,df.utci,color='r',label='utci')
    ax2.set_ylabel('UTCI')
plt.tight_layout()
plt.show()      
```

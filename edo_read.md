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
import xarray as xr
import numpy as np
import pandas as pd
from climate_drought import utils
```

```python
import glob
#flist=glob.glob('input/spg03/spg03*.nc')
flist=glob.glob('input/smant/sma*.nc')
#flist = glob.glob('input/fpanv/f*.nc')
len(flist)
```

```python
xr.open_dataset(flist[0])
```

```python
dses = [xr.open_dataset(fname).sel(lat=62,lon=-100,method='nearest').drop_vars(['lat','lon','4326']) for fname in flist]
```

```python
df = xr.merge(dses).to_dataframe()
```

```python
df[(df.index > pd.Timestamp(2016,4,16)) & (df.index < pd.Timestamp(2022,12,31))].smant.plot()
```

```python
sdate = '20200101'
edate = '20230101'
daterange = utils.daterange(sdate,edate,rtv=False)
```

```python
def fill_gaps(sdate,edate,df):
    dti = pd.date_range(sdate,edate,freq='1D')
    dti_dekads = utils.dti_to_dekads(dti)
    gaps = dti_dekads[~dti_dekads.isin(df.index)]
    if len(gaps) > 0:
        df_gaps = pd.DataFrame(index=gaps)
        return pd.concat([df,df_gaps])
    else:
        return df
```

```python
dti = pd.date_range(sdate,edate,freq='1D')
```

```python
dti_dekads = utils.dti_to_dekads(dti)
```

```python
dti_dekads
```

```python
gaps = dti_dekads[~dti_dekads.isin(df.index)]
```

```python
df_gaps = pd.DataFrame(index=gaps)
```

```python
pd.concat([df,df_gaps])
```

```python
d = dti.day - np.clip((dti.day-1) // 10, 0, 2)*10 - 1
date = dti.values - np.array(d, dtype="timedelta64[D]")
```

```python
np.unique(date)
```

```python
dekads = utils.to_dekads(pd.DataFrame(np.zeros(len(daily_times)),index=daily_times)).index
```

```python
df = df.loc[(df.index >= '20200101') & (df.index <= '20221231')]
```

```python
df.fpanv.plot()
```

```python
df.fpanv.fillna(df.fapan, inplace=True)
del df['fapan']
df
```

```python
df = ds.drop_vars(['lat','lon','4326']).to_dataframe()
```

```python
ds.smant.plot()
```

```python
ds.isel(time=0).smand.plot()
```

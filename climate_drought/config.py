from datetime import datetime,timedelta

class AnalysisArgs():
    def __init__(self, latitude, longitude, start_date, end_date, product='SPI', oformat='GeoJSON', singleval=False):

        self.singleval = singleval # Used for viewer
        if singleval:
            self.latitude = latitude if type(latitude) == list else latitude
            self.longitude = longitude if type(longitude) == list else longitude
        else:
            self.latitude = latitude if type(latitude) == list else [latitude]
            self.longitude = longitude if type(longitude) == list else [longitude]

            if len(self.longitude)!=len(self.latitude):
                raise ValueError('Number of latitude and longitudes must be equal')
        self.start_date = start_date
        self.end_date = end_date
        self.indicator = product
        self.oformat = oformat

class CDIArgs(AnalysisArgs):
    def __init__(self, latitude, longitude, start_date, end_date, spi_source='GDO',sma_source='GDO', sma_var=None, oformat='GeoJSON',singleval=False):
        super().__init__(latitude, longitude, start_date, end_date, product='CDI', oformat=oformat)
        self.spi_source = spi_source
        self.sma_source = sma_source
        self.spi_var = 'spg03' if spi_source=='GDO' else 'spi'
        self.sma_var = sma_var or ('smant' if spi_source=='GDO' else 'zscore_swvl3')
        self.fpr_var = 'fpanv'
        self.singleval = singleval # Used for viewer

class Config():
    def __init__(self,outdir='output',indir='input',verbose=True,baseline_start='19850101',baseline_end=None,aws=False,era_daily=False):
        self.outdir = outdir
        self.indir = indir
        self.verbose = verbose
        self.baseline_start = baseline_start
        self.aws = aws
        self.era_daily = era_daily

        if baseline_end is None:
            # Set to the last day of the last month
            ddn = datetime.now().replace(day=1) - timedelta(days=1)
            yyyy = str(ddn.year)
            mm = ('0' if ddn.month<10 else '') + str(ddn.month)
            dd = ('0' if ddn.day<10 else '') + str(ddn.day)
            baseline_end = yyyy + mm + dd

        self.baseline_end = baseline_end


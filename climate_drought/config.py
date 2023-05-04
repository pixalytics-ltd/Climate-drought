class AnalysisArgs():
    def __init__(self, latitude, longitude, start_date, end_date):
        self.latitude = latitude
        self.longitude = longitude
        self.start_date = start_date
        self.end_date = end_date

class CDIArgs(AnalysisArgs):
    def __init__(self, latitude, longitude, start_date, end_date, spi_source='GDO',sma_source='GDO', sma_var=None):
        super().__init__(latitude, longitude, start_date, end_date)
        self.spi_source = spi_source
        self.sma_source = sma_source
        self.spi_var = 'spg03' if spi_source=='GDO' else 'spi'
        self.sma_var = sma_var or ('smant' if spi_source=='GDO' else 'zscore_swvl3')
        self.fpr_var = 'fpanv'

class Config():
    def __init__(self,outdir='output',indir='input',verbose=True,baseline_start='19850101',baseline_end='20221231',aws=False):
        self.outdir = outdir
        self.indir = indir
        self.verbose = verbose
        self.baseline_start = baseline_start
        self.baseline_end = baseline_end
        self.aws = aws
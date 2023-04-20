class AnalysisArgs():
    def __init__(self, latitude, longitude, start_date, end_date):
        self.latitude = latitude
        self.longitude = longitude
        self.start_date = start_date
        self.end_date = end_date

class CDIArgs(AnalysisArgs):
    def __init__(self, latitude, longitude, start_date, end_date, sma_source='EDO', spi_var='spi', sma_var='smant', fpr_var='fpanv'):
        super().__init__(latitude, longitude, start_date, end_date)
        self.sma_source = sma_source
        self.spi_var = spi_var
        self.sma_var = sma_var
        self.fpr_var = fpr_var

class Config():
    def __init__(self,outdir='output',indir='input',verbose=True,baseline_start='19850101',baseline_end='20221231'):
        self.outdir = outdir
        self.indir = indir
        self.verbose = verbose
        self.baseline_start = baseline_start
        self.baseline_end = baseline_end
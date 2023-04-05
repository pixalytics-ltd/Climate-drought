class AnalysisArgs():
    def __init__(self, latitude, longitude, start_date, end_date, product, sma_source = 'EDO'):
        self.latitude = latitude
        self.longitude = longitude
        self.start_date = start_date
        self.end_date = end_date
        self.index = product
        self.sma_source = sma_source

class Config():
    def __init__(self,outdir='output',indir='input',verbose=True,baseline_start='19850101',baseline_end='20221231'):
        self.outdir = outdir
        self.indir = indir
        self.verbose = verbose
        self.baseline_start = baseline_start
        self.baseline_end = baseline_end
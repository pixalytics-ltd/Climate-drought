class AnalysisArgs():
    def __init__(self, latitude, longitude, start_date, end_date, product):
        self.latitude = latitude
        self.longitude = longitude
        self.start_date = start_date
        self.end_date = end_date
        self.index = product

class Config():
    def __init__(self,outdir='outdir',verbose=True,baseline_start='19850101',baseline_end='20221231'):
        self.outdir = outdir
        self.verbose = verbose
        self.baseline_start = baseline_start
        self.baseline_end = baseline_end
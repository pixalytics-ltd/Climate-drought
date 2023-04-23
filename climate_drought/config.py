class AnalysisArgs():
    def __init__(self, latitude, longitude, start_date, end_date, product, oformat):
        self.latitude = latitude
        self.longitude = longitude
        self.start_date = start_date
        self.end_date = end_date
        self.index = product
        self.oformat = oformat

class Config():
    def __init__(self,outdir='outdir',verbose=True,baseline_start='19850101',baseline_end='20221231',aws=False):
        self.outdir = outdir
        self.verbose = verbose
        self.baseline_start = baseline_start
        self.baseline_end = baseline_end
        self.aws = aws
class AnalysisArgs():
    def __init__(self, args):
        self.latitude = args.latitude
        self.longitude = args.longitude
        self.start_date = args.start_date
        self.end_date = args.end_date
        self.index = args.product
        self.accum = args.accum

class Config():
    def __init__(self,outdir='outdir',verbose=True,baseline_start='19850101',baseline_end='20221231'):
        self.outdir = outdir
        self.verbose = verbose
        self.baseline_start = baseline_start
        self.baseline_end = baseline_end
class AnalysisArgs():
    def __init__(self, args):
        self.latitude = args.latitude
        self.longitude = args.longitude
        self.start_date = args.start_date
        self.end_date = args.end_date
        self.index = args.product

class Config():
    def __init__(self,outdir='outdir',verbose=True,baseline_start='19850101',baseline_end='20221231'):
        self.outdir = outdir
        self.verbose = verbose
        self.baseline_start = baseline_start
        self.baseline_end = baseline_end

class ERA5Request():
    def __init__(self,variables,monthly,fname_out,args: AnalysisArgs,config: Config,baseline=False):
        self.latitude = args.latitude
        self.longitude = args.longitude
        self.start_date = config.baseline_start if baseline else args.start_date
        self.end_date = config.baseline_end if baseline else args.end_date
        self.variables = variables
        self.working_dir = config.outdir
        self.fname_out = fname_out
        self.verbose = config.verbose
        self.monthly = monthly
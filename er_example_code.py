from owslib.wps import WebProcessingService, monitorExecution

# contact the WPS client
wps = WebProcessingService("http://api.pixalytics.com/climate/wps", skip_caps=True)

# GetCapabilities
wps.getcapabilities()

# Execute
inputs = [ ("start_date", '20200101'),
        ("end_date", '20221231'),
        ("latitude", '55.5'),
        ("longitude", '-99.1')]

execution = wps.execute("drought", inputs, "output")

outfile = "temp.json"
monitorExecution(execution,download=True,filepath=outfile)

# Wait 5 seconds and check
execution.checkStatus(sleepSecs=5)

# show status
print('Percent complete {}%, generated {}'.format(execution.percentCompleted, outfile))

# If there's an error print the error information
for error in execution.errors:
    print("Error: ",error.code, error.locator, error.text)
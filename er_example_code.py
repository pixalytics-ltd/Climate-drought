from owslib.wps import WebProcessingService, monitorExecution

# contact the WPS client
wps = WebProcessingService("http://api.pixalytics.com/climate/wps", skip_caps=True)

# GetCapabilities
wps.getcapabilities()

# Execute
calltype= 'point'
if calltype == 'box':
    latvals = '[49.03 , 60.00]'
    lonvals = '[-101.35, -89.16]'
elif calltype == 'polygon': # Manitoba example
    latvals = '[59.98 , 58.66, 58.63, 57.17, 57.12, 56.63, 52.79, 49.03, 49.06, 60.00, 59.98]'
    lonvals = '[-94.80, -94.75, -93.01, -92.54, -90.58, -89.16, -95.17, -95.17, -101.35, -102.03, -94.80]'
else: #point
    latvals = '55.5'
    lonvals = '-99.1'

print("Making a call as a {}".format(calltype))

inputs = [ ("start_date", '20200101'),
        ("end_date", '20221231'),
        ("latitude", latvals),
        ("longitude", lonvals)]

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
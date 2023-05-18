import os
import logging

from urllib.request import urlopen, urlretrieve

URL="https://edo.jrc.ec.europa.eu/gdo/php/util/getData2download.php?year={year}&scale_id=gdo&prod_code={prod_code}&format=nc&action=getUrls"

class GDODownload():
    """
    Represents a single download file from the Global Drought Observatory
    """
    def __init__(self,year,prod_code,logger: logging.Logger):
        #build url string which is called by the webservice once a dataset and year have been selected and the 'Download' button is pushed
        def build_url(year,prod_code):
            return URL.format(year=year,prod_code=prod_code)

        self.logger = logger

        #return the address of the file in the fileserver
        try:
            page = urlopen(build_url(year,prod_code))
            html_bytes = page.read()
            html = html_bytes.decode("utf-8")

            #turn into a string which works as a url
            self.url = html[2:-2].replace('\/','/').replace(" ", "%20")
            self.filename = self.url.split("/")[-1]

            self.logger.info("Successfully obtained URL for GDO file with year: {0}, prod_code {1}".format(year,prod_code))
        except:
            self.logger.error("Couldn't retrieve URL for GDO file with year: {0}, prod_code {1}".format(year,prod_code))

    def download(self,output_folder):

        filepath = output_folder + "/" + self.filename

        if os.path.isfile(filepath):
            self.logger.info("File already exists at: {}".format(filepath))
        else:
            urlretrieve(self.url,filename=filepath)
            self.logger.info("Downloaded file from GDO: {}".format(filepath))
        
        return filepath
        
import os
import logging

from urllib.request import urlopen, urlretrieve

URL="https://edo.jrc.ec.europa.eu/gdo/php/util/getData2download.php?year={year}&scale_id=gdo&prod_code={prod_code}&format=nc&action=getUrls"

class GDODownload():
    """
    Represents a single download file from the Global Drought Observatory
    """
    def __init__(self,year,prod_code,logger: logging.Logger):
        
        def build_url(year,prod_code):
            """ 
            Build the url string which is produced by the website once the 'Download' button is pushed
            for a given product code and year.
            Opening this url returns further urls corresponding to ftp files which fit the product code and year.
            """
            return URL.format(year=year,prod_code=prod_code)

        self.logger = logger

        try:
            # Simulate clicking the 'download' button for a given dataset and year
            page = urlopen(build_url(year,prod_code))
            html_bytes = page.read()
            html = html_bytes.decode("utf-8")

            # html is a string of a list of strings - convert to list
            urls = eval(html)

            # reformat so they work as web addresses
            self.urls = [u.replace('\/','/').replace(" ", "%20") for u in urls if len(u)>0]

            # Get the name of the file to be downloaded from the end of the file address (so we can also save it under this name)
            self.filenames = [u.split("/")[-1] for u in self.urls if len(u)>0]

            self.success = len(self.filenames) > 0
        except:
            self.success = False

        self.logger.info(("Successfully retrieved" if self.success else "Couldn't retrieve") + " URL for GDO file with year: {0}, prod_code {1}".format(year,prod_code))

        # if self.success:
        #     print(self.url)

    def download(self,output_folder):

        downloaded_filenames = []
        for url, filename in zip(self.urls,self.filenames):
            filepath = output_folder + "/" + filename

            print(url)

            if os.path.isfile(filepath):
                self.logger.info("File already exists at: {}".format(filepath))
                downloaded_filenames.append(filepath)
            else:
                try:
                    urlretrieve(url,filename=filepath)
                    self.logger.info("Downloaded file from GDO: {}".format(filepath))
                    downloaded_filenames(filepath)
                except:
                    self.logger.info("Could not download file: {}".format(filepath))
        
        # update filenames with those which have been downloaded
        self.filenames = downloaded_filenames
        return downloaded_filenames
        
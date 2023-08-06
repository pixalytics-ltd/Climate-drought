import os
import logging

import glob
from urllib.request import urlopen, urlretrieve
import ssl


URL="https://edo.jrc.ec.europa.eu/gdo/php/util/getData2download.php?year={year}&scale_id=gdo&prod_code={prod_code}&format=nc&action=getUrls"

class GDODownload():
    """
    Represents a single download file from the Global Drought Observatory
    """
    def __init__(self,year,prod_code,output_folder,logger: logging.Logger):
        
        def build_url(year,prod_code):
            """ 
            Build the url string which is produced by the website once the 'Download' button is pushed
            for a given product code and year.
            Opening this url returns further urls corresponding to ftp files which fit the product code and year.
            """
            return URL.format(year=year,prod_code=prod_code)

        self.logger = logger

        # Check if already downloaded first
        files = glob.glob(os.path.join(output_folder,"{}_m_wld_{}*.nc".format(prod_code, year)))
        self.success = True
        if len(files) > 0:
            self.files_to_download = []
            for f in files:
                self.files_to_download.append(os.path.basename(f))
            self.logger.info("{} already downloaded".format(self.files_to_download))
        else:
            self.logger.info("No {} file in {}".format(year, output_folder))
  
            # Simulate clicking the 'download' button for a given dataset and year
            url = build_url(year,prod_code)
            try:
                page = urlopen(url)
            except:
                self.logger.info("Failed to open URL: {}".format(url))
                self.success = False
            
            if self.success:
                html_bytes = page.read()
                html = html_bytes.decode("utf-8")
          
                # html is a string of a list of strings - convert to list
                urls = eval(html)
                
                # reformat so they work as web addresses
                self.urls = [u.replace('\/','/').replace(" ", "%20") for u in urls if len(u)>0]
                self.logger.info("Built URL: {} urls: {}".format(url,urls))
          
                # Get the name of the file to be downloaded from the end of the file address (so we can also save it under this name)
                self.files_to_download = [u.split("/")[-1] for u in self.urls if len(u)>0]
          
                self.success = len(self.files_to_download) > 0
    
            self.filenames = []
            self.logger.info(("Successfully retrieved" if self.success else "Couldn't retrieve") + " URL for GDO file with year: {0}, prod_code {1}".format(year,prod_code))

    def download(self,output_folder):

        ssl._create_default_https_context = ssl._create_unverified_context

        self.logger.info("Downloading files to {}".format(output_folder))
        for url, filename in zip(self.urls,self.files_to_download):
            filepath = output_folder + "/" + filename
            if os.path.isfile(filepath):
                self.logger.info("File already exists at: {}".format(filepath))
            else:
                try:
                    urlretrieve(url,filename=filepath)
                    self.logger.info("Downloaded file from GDO: {}".format(filepath))
                except Exception as e:
                    self.logger.info("Could not download file: {}".format(filepath))
                    self.logger.info("Error: {}".format(e))
            
            # check
            if os.path.isfile(filepath):
                self.filenames.append(filename)

        return self.filenames
        
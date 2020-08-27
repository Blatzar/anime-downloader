import os
import copy
import logging
import threading
import time

from anime_downloader.downloader.base_downloader import BaseDownloader
from anime_downloader import session
import requests
import requests_cache

session = session.get_session()
session = requests
logger = logging.getLogger(__name__)

class HTTPDownloader(BaseDownloader):
    def _download(self):
        logger.warning('Using internal downloader which might be slow. Use aria2 for full bandwidth.')
        if self.range_size is None:
            self._non_range_download()
        else:
            self._ranged_download()


    def _ranged_download(self):
        http_chunksize = self.range_size

        range_start = 0
        range_end = http_chunksize

        url = self.source.stream_url
        headers = self.source.headers
        if 'user-agent' not in headers:
            headers['user-agent'] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101Firefox/56.0",

        if self.source.referer:
            headers['Referer'] = self.source.referer
        
        logger.info('Testing threads.')
        # Default value.
        number_of_threads = 8
        # Just checks the site how many threads are allowed.
        # animeout only allows 1 max for example.
        # This can probably be threaded too, but getting return values from threads isn't very easy.
        number_of_threads = self.test_download(url, headers, number_of_threads)
        logger.info('Using {} thread{}.'.format(number_of_threads, (number_of_threads > 1) *'s'))

        # Creates an empty part file, this comes at the cost of not really knowing if a file is fully completed.
        # We could possibly add some end bytes on completion?
        part = int(self._total_size) / number_of_threads
        fp = open(self.path, "wb")
        fp.write(b'0' * self._total_size)
        fp.close()

        self.start_time = time.time()

        for i in range(number_of_threads):
            start = int(part * i)
            end = start + part

            t = threading.Thread(target=self.thread_downloader,
                kwargs={'url': url, 'start':start, 'end': end, 'headers':set_range(start, end, headers)})
            t.setDaemon(True)
            t.start()

        main_thread = threading.current_thread()
        for t in threading.enumerate():
            if t is main_thread:
                continue
            t.join()


    def _non_range_download(self):
        url = self.source.stream_url
        headers = {
            'user-agent': "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Gecko/20100101Firefox/56.0",
        }
        if self.source.referer:
            headers['Referer'] = self.source.referer
        r = session.get(url, headers=headers, stream=True)

        if r.status_code == 200:
            with open(self.path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=self.chunksize):
                    if chunk:
                        f.write(chunk)
                        self.report_chunk_downloaded()


    def thread_downloader(self, url, start, end, headers):
        # specify the starting and ending of the file
        # request the specified part and get into variable
        with requests.get(url, headers=headers, stream=True) as r:
            # open the file and write the content of the html page
            # into file.
            with open(self.path, "r+b") as fp:
                fp.seek(start)
                var = fp.tell()
                for chunk in r.iter_content(chunk_size=self.chunksize):
                    if chunk:
                        fp.write(chunk)
                        self.report_chunk_downloaded()


    def test_download(self, url, headers, threads):
        for i in range(threads):
            r = requests.get(url, headers=headers, stream=True)
            if not r.headers.get('content-length') or r.status_code not in [200, 206]:
                return i
        return threads


def set_range(start=0, end='', headers=None):
    if headers is None:
        headers = {}
    headers = copy.copy(headers)

    headers['Range'] = 'bytes={}-{}'.format(start, end)
    return headers

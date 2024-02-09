from .web import Driver
from seleniumwire.webdriver.request import Request as WireRequest
from seleniumwire.proxy.client import ProxyException
import requests
import json
from typing import Set
from .util import dict_walk
from selenium.webdriver.common.by import By
from json.decoder import JSONDecodeError
from urllib.parse import quote_plus, unquote_plus
from functools import cache
import time
import logging
from .cache import Cache

logger = logging.getLogger(__name__)

S = requests.Session()


class UrlCache(Cache):
    def parse_file_name(self, url: str, **kargv):
        h = "".join(c for c in url if c.isalpha() or c.isdigit() or c==' ').rstrip()
        return f"{self.file}/{h}.json"


class SearchWire(Driver):
    URL = "https://www.xbox.com/es-ES/games/browse?locale=es-ES"
    PAGE_SIZE = 25

    @staticmethod
    def get_preload_state(url=None):
        if url is None:
            url = SearchWire.URL
        text = S.get(url).text
        return SearchWire.__get_preload_state(text)

    @staticmethod
    def __get_preload_state(text):
        for ln in text.split("\n"):
            ln = ln.strip()
            if ln.startswith("window.__PRELOADED_STATE__"):
                ln = ln.split("=", 1)[-1].strip().rstrip(";")
                return json.loads(ln)

    def __init__(self):
        super().__init__(browser="wirefirefox", wait=10)

    def get_preload_state_ids(self, url: str):
        def __get(url: str):
            obj = SearchWire.get_preload_state(url)
            obj = dict_walk(obj, 'core2', 'products', 'productSummaries')
            return set(obj.keys())
        ids = __get(url+'&orderby=Title+Asc')
        if len(ids) >= SearchWire.PAGE_SIZE:
            ids = ids.union(__get(url+'&orderby=Title+Desc'))
        ids = tuple(sorted(ids))
        return ids

    def __find_ids(self, done: Set[str]):
        path = "://emerald.xboxservices.com/xboxcomfd/browse"
        new_ids = set()
        while True:
            for js in self.iter_requests_json(path):
                ids = set((i['productId'] for i in js['productSummaries']))
                new_ids = new_ids.union(ids.difference(done))
            if len(new_ids) > 0:
                return new_ids

    def iter_requests_json(self, path: str):
        r: WireRequest
        for r in self._driver.requests:
            if path not in r.path:
                continue
            if not (r.response and r.response.body):
                continue
            bdy: bytes = r.response.body
            txt = bdy.decode('utf-8')
            txt = txt.strip()
            try:
                yield json.loads(txt)
            except JSONDecodeError:
                continue

    def run_script(self, file: str):
        with open(file, "r") as f:
            js = f.read()
        return self.execute_script(js)

    @cache
    def get_choices(self, filter):
        obj = dict_walk(self.get_preload_state(), 'core2',
                        'filters', 'Browse', 'data')
        if not isinstance(obj, dict):
            return None
        if filter not in obj:
            return None
        return tuple([c['id'] for c in obj[filter]['choices']])

    def query(self, filter: str, value: str):
        url = SearchWire.URL+'&'+filter+"="+quote_plus(value)
        if (filter, value) != ("PlayWith", "XboxSeriesX|S"):
            return self.__query(url)
        choices = {
            k: list(self.get_choices(k)) for k in ('MaturityRating', 'Price') if self.get_choices(k)
        }
        if len(choices) == 0:
            return self.__query(url)

        root = SearchWire.URL + f'&{filter}={quote_plus(value)}&'

        def yield_urls():
            ksy = tuple(choices.keys())
            if 'Price' in ksy:
                for c in ("0", "70To"):
                    if c in choices['Price']:
                        yield root + 'Price='+c
                        choices['Price'].remove(c)
            if 'MaturityRating' in ksy:
                provisional = tuple(
                    (i for i in choices['MaturityRating'] if not i[-1].isdigit()))
                for c in (("PEGI:!",)+provisional):
                    if c in choices['MaturityRating']:
                        yield root + 'MaturityRating='+c
                        choices['MaturityRating'].remove(c)

            ksy = tuple([k for k, v in choices.items() if len(v) > 0])
            for c0 in choices[ksy[0]]:
                url = root + f'{ksy[0]}={quote_plus(c0)}'
                if len(ksy) == 1:
                    yield url
                else:
                    for c1 in choices[ksy[1]]:
                        yield url + f'&{ksy[1]}={quote_plus(c1)}'

        ids = set()
        for url in yield_urls():
            self.close()
            ids = ids.union(self.__query(url))
        return tuple(sorted(ids))

    def getProductSummaries(self, url):
        while True:
            try:
                self.get(url)
                obj = SearchWire.__get_preload_state(self.source)
                obj = dict_walk(obj, 'core2', 'products', 'productSummaries')
                if obj is not None:
                    return obj
            except ProxyException:
                pass
            self.close()
            time.sleep(10)

    @UrlCache("rec/br/tmp/")
    def __query(self, url: str):
        query = " ".join(map(
            lambda kv: kv[0]+'='+unquote_plus(kv[1]),
            map(
                lambda kv: kv.split("="),
                url[len(SearchWire.URL)+1:].split("&")
            )
        ))
        p_ids = self.get_preload_state_ids(url)
        if len(p_ids) < (SearchWire.PAGE_SIZE*2):
            logger.info(f"{query} {len(p_ids)}")
            return p_ids

        obj = self.getProductSummaries(url)
        ids = set(obj.keys())
        if len(ids) == 0:
            logger.info(f"{query} 0")
            return tuple()
        self.run_script('js/ol.js')
        while True:
            if 1 != self.safe_click('//button[@aria-label="Cargar más"]', by=By.XPATH):
                logger.info(f"{query}, {len(ids)}")
                return tuple(sorted(ids))
            new_ids = self.__find_ids(ids)
            if len(new_ids):
                ids = ids.union(new_ids)

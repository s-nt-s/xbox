from .web import Driver
from seleniumwire.webdriver.request import Request as WireRequest
from seleniumwire.proxy.client import ProxyException
import requests
import json
from typing import Set
from .util import dict_walk as util_dict_walk
from selenium.webdriver.common.by import By
from json.decoder import JSONDecodeError
from urllib.parse import quote_plus, unquote_plus
from functools import cache
import time
import logging
from .cache import Cache, StaticCache
import re

logger = logging.getLogger(__name__)

S = requests.Session()
re_sp = re.compile(r"\s+")


class RetryException(Exception):
    pass


def dict_walk(obj, path: str):
    data = util_dict_walk(obj, *path.split("/"))
    if data is None:
        raise RetryException(path+" no encontrado")
    return data


class SafeCache(Cache):
    def parse_file_name(self, url: str, **kargv):
        url = re_sp.sub("", url)
        h = "".join(c for c in url if c.isalpha() or c.isdigit())
        return f"{self.file}/{h}.json"


class DefaultBrowkserCache(StaticCache):
    def parse_file_name(self, url: str = None):
        if url in (None, SearchWire.URL):
            return "rec/games_browse.json"


class SearchWire(Driver):
    URL = "https://www.xbox.com/es-ES/games/browse?locale=es-ES"
    PAGE_SIZE = 25

    @staticmethod
    @StaticCache("rec/br/{0}={1}.json")
    def do_games_browse_search(filter, value):
        while True:
            try:
                with SearchWire() as web:
                    return web.query(filter, value)
            except (ProxyException, JSONDecodeError, RetryException) as e:
                logger.critical(str(e))
                time.sleep(60)

    @staticmethod
    @StaticCache("rec/br/filter.json")
    def get_filters():
        while True:
            try:
                obj = SearchWire.get_preload_state()
                return dict_walk(obj, 'core2/filters/Browse/data')
            except (ProxyException, JSONDecodeError, RetryException) as e:
                logger.critical(str(e))
                time.sleep(60)

    @staticmethod
    @DefaultBrowkserCache("rec/games_browse.json")
    def get_preload_state(url: str = None):
        if url is None:
            url = SearchWire.URL
        text = S.get(url).text
        return SearchWire.__get_preload_state(text)

    @staticmethod
    def __get_preload_state(text: str):
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
            obj = dict_walk(obj, 'core2/products/productSummaries')
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
                logger.critical("NOT JSON: "+r.path)
                continue

    @cache
    def get_choices(self, filter):
        obj = dict_walk(self.get_filters(), f'{filter}/choices')
        return tuple([c['id'] for c in obj])

    def query(self, filter: str, value: str):
        url = SearchWire.URL+'&'+filter+"="+quote_plus(value)
        if (filter, value) != ("PlayWith", "XboxSeriesX|S"):
            return self.__query(url)

        root = SearchWire.URL + f'&{filter}={quote_plus(value)}&'
        choices = {
            k: list(self.get_choices(k)) for k in ('MaturityRating', 'Price')
        }
        main_choices = {
            'Price': ("0", "70To"),
            'MaturityRating': ("PEGI:!", ) + tuple(
                    (i for i in (choices.get('MaturityRating') or []) if not i[-1].isdigit())
                )
        }

        def yield_urls():
            for k, chs in main_choices.items():
                if k in choices:
                    for c in chs:
                        if c in choices[k]:
                            yield root + k+'='+c
                            choices[k].remove(c)

            ksy = tuple([k for k, v in choices.items() if len(v) > 0])
            if len(ksy) == 0:
                yield root[:-1]
            else:
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
        self.get(url)
        obj = SearchWire.__get_preload_state(self.source)
        obj = dict_walk(obj, 'core2/products/productSummaries')
        return set(obj.keys())

    @SafeCache("rec/br/tmp/")
    def __query(self, url: str):
        query = " ".join(map(
            lambda kv: kv[0]+'='+unquote_plus(kv[1]),
            map(
                lambda kv: kv.split("="),
                url[len(SearchWire.URL)+1:].split("&")
            )
        ))
        ids = self.get_preload_state_ids(url)
        if len(ids) != SearchWire.PAGE_SIZE and (len(ids) < (SearchWire.PAGE_SIZE*2)):
            logger.info(f"{query} {len(ids)}")
            return ids

        ids = self.getProductSummaries(url)
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

from .web import Driver
from seleniumwire.webdriver.request import Request as WireRequest
from seleniumwire.proxy.client import ProxyException
import requests
import json
from typing import Set
from .util import dict_walk as util_dict_walk
from selenium.webdriver.common.by import By
from json.decoder import JSONDecodeError
from urllib.parse import quote_plus
import time
import logging
from .cache import Cache
import re
from typing import Union, Dict
from .endpoint import EndPoint, _get_preload_state, EndPointCache

logger = logging.getLogger(__name__)

S = requests.Session()
re_sp = re.compile(r"\s+")

URL_GAMES_BROWSER = "https://www.xbox.com/es-ES/games/browse?locale=es-ES"
PAGE_SIZE = 25


def dict_walk(obj, path: str):
    data = util_dict_walk(obj, path)
    if data is None:
        raise KeyNotFound(path+" no encontrado")
    return data


class KeyNotFound(ValueError):
    pass


class EndPointSearchCache(EndPointCache):
    def parse_file_name(self, *args, slf: "EndPointSearchPreloadState", **kargv):
        if slf.id:
            name = "&".join((f"{k}={v}" for k, v in slf.id.items()))
        else:
            name = "games_browse"
        return f"{self.file}/{name}.json"


class EndPointSearchPreloadState(EndPoint):

    def __init__(self, id: Dict[str, str] = None):
        if id is None:
            id = {}
        self.id = {k: v for k, v in id.items() if v is not None}

    @property
    def url(self):
        url = str(URL_GAMES_BROWSER)
        for filter, value in self.id.items():
            url = url + f'&{filter}={quote_plus(value)}'
        return url

    def parse(self, text: str):
        ps = _get_preload_state(text)
        if ps is None:
            raise KeyNotFound("__PRELOADED_STATE__ NOT FOUND")
        return ps

    @EndPointSearchCache(f"rec/search/max{PAGE_SIZE}/")
    def json(self) -> Union[Dict, None]:
        text = S.get(self.url).text
        return self.parse(text)

    @EndPointCache("rec/search/filters.json")
    def filters(self) -> Union[Dict, None]:
        obj = dict_walk(self.json(), 'core2/filters/Browse/data')
        must = {
            'orderby': ("Title Asc", "Title Desc"),
            'PlayWith': ("XboxSeriesX|S",),
            "Price": ("0", "70To"),
            'MaturityRating':  tuple(),
            'IncludedInSubscription': tuple()
        }
        for filter, choices in must.items():
            if filter not in obj:
                raise KeyNotFound(
                    f"NOT FOUND core2/filters/Browse/data/{filter}")
            if 'choices' not in obj[filter]:
                raise KeyNotFound(
                    f"NOT FOUND core2/filters/Browse/data/{filter}/choices")
            for c in choices:
                if c not in map(lambda x: x['id'], obj[filter]['choices']):
                    raise KeyNotFound(
                        f"NOT FOUND core2/filters/Browse/data/{filter}/choices/{c}")
        return obj

    def productSummaries(self) -> Union[Dict, None]:
        return dict_walk(self.json(), 'core2/products/productSummaries')

    def ids(self):
        return tuple(sorted(self.productSummaries().keys()))


class EndPointSearchXboxSeries(EndPointSearchPreloadState):
    def __init__(self, id: Dict[str, str] = None):
        super().__init__(id)
        if "PlayWith" not in self.id:
            id["PlayWith"] = "XboxSeriesX|S"

    @EndPointSearchCache("rec/search/full/")
    def productSummaries(self) -> Union[Dict, None]:
        obj = {}
        for query in self.yield_queries():
            ps = EndPointSearchPreloadState(query).productSummaries()
            if len(ps) >= PAGE_SIZE:
                ps = SearchWire.do_games_browse_search(query)
            obj = {**obj, **ps}
        return obj

    @EndPointSearchCache("rec/search/")
    def ids(self):
        return tuple(sorted(self.productSummaries().keys()))

    def yield_queries(self):
        filters = dict(self.filters())
        query = dict(self.id)
        choices = {
            k: list(map(lambda x: x['id'], filters[k]['choices'])) for k in ('MaturityRating', 'Price')
        }
        for c in list(choices['MaturityRating']):
            if len(EndPointSearchPreloadState({
                'MaturityRating': c,
                'PlayWith': query.get('PlayWith')
            }).ids()) == 0:
                choices['MaturityRating'].remove(c)

        main_choices = {
            'Price': ("0", "70To"),
            'MaturityRating': tuple(
                (i for i in choices['MaturityRating'] if not i[-1].isdigit())
            )
        }
        for k in query.keys():
            if k in main_choices:
                del main_choices[k]

        for k, chs in main_choices.items():
            for c in list(chs):
                yield {**query, **{k: c}}
                choices[k].remove(c)

        ksy = tuple([k for k, v in choices.items() if len(v) > 0])
        if len(ksy) == 0:
            yield dict(query)
        else:
            for c0 in choices[ksy[0]]:
                qr = {**query, **{ksy[0]: c0}}
                if len(ksy) == 1:
                    yield qr
                else:
                    for c1 in choices[ksy[1]]:
                        yield {**qr, **{ksy[1]: c1}}


class SafeCache(Cache):
    def parse_file_name(self, url: str, **kargv):
        url = re_sp.sub("", url)
        h = "".join(c for c in url if c.isalpha() or c.isdigit())
        return f"{self.file}/{h}.json"


class SearchWire(Driver):
    @staticmethod
    def do_games_browse_search(query: Dict[str, str]):
        while True:
            try:
                with SearchWire() as web:
                    return web.query(query)
            except (ProxyException, JSONDecodeError, KeyNotFound) as e:
                logger.critical(str(e))
                time.sleep(60)

    def __init__(self):
        super().__init__(browser="wirefirefox", wait=10)

    def query(self, query: Dict[str, str]):
        squery = " ".join(f"{k}={v}" for k, v in query.items())
        url = URL_GAMES_BROWSER + '&' + \
            '&'.join(map(lambda kv: kv[0]+'=' +
                     quote_plus(kv[1]), query.items()))
        ids = self.__query_from_url(url)
        logger.info(f"{squery} {len(ids)}")
        return ids

    @SafeCache("rec/search/url/")
    def __query_from_url(self, url: str):
        self.get(url)
        obj = _get_preload_state(self.source)
        obj = dict_walk(obj, 'core2/products/productSummaries')
        if len(obj) == 0:
            return list(obj.values())

        self.run_script('js/ol.js')
        while True:
            if 1 != self.safe_click('//button[@aria-label="Cargar más"]', by=By.XPATH):
                return obj
            new_obj = self.__find_ids(set(obj.keys()))
            if len(new_obj):
                obj = {**obj, **new_obj}

    def __find_ids(self, done: Set[str]):
        path = "://emerald.xboxservices.com/xboxcomfd/browse"
        new_obj = {}
        while True:
            for js in self.__iter_requests_json(path):
                aux = {v['productId']: v for v in js['productSummaries'] if v['productId'] not in done}
                new_obj = {**new_obj, **aux}
            if len(new_obj) > 0:
                return new_obj

    def __iter_requests_json(self, path: str):
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
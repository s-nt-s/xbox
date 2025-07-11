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
from .timeout import timeout

logger = logging.getLogger(__name__)

S = requests.Session()
re_sp = re.compile(r"\s+")

URL_GAMES_BROWSER = "https://www.xbox.com/es-ES/games/browse?locale=es-ES"
URL_GAMES_BROWSER_DEAL = "https://www.xbox.com/es-ES/games/browse/DynamicChannel.GameDeals?locale=es-ES"

PAGE_SIZE = 25


def dict_walk(obj, path: str):
    data = util_dict_walk(obj, path)
    if data is None:
        raise KeyNotFound(path+" no encontrado")
    return data


class AuxCache(Cache):
    def parse_file_name(self, obj, **kwargs):
        name = re_sp.sub("", str(obj))
        name = "".join(c for c in name if c.isalpha() or c.isdigit())
        return f"{self.file}/{name}.json"


class KeyNotFound(ValueError):
    pass


class EndPointSearchCache(EndPointCache):
    def parse_file_name(self, *args, slf: "EndPointSearchPreloadState", **kwargs):
        name = ""
        if slf.root == URL_GAMES_BROWSER_DEAL:
            name = "deal_"
        if slf.id:
            name = name + "&".join((f"{k}={v}" for k, v in slf.id.items()))
        else:
            name = name + "games_browse"
        return self.file.format(name)


class EndPointSearchFilterCache(EndPointCache):
    def parse_file_name(self, *args, slf: "EndPointSearchPreloadState", **kwargs):
        name = ""
        if slf.root == URL_GAMES_BROWSER_DEAL:
            name = "deal_"
        return self.file.format(name)


class EndPointSearchPreloadState(EndPoint):

    def __init__(self, id: Dict[str, str] = None, root=URL_GAMES_BROWSER):
        if id is None:
            id = {}
        self.id = {k: v for k, v in id.items() if v is not None}
        self.__root = root

    @property
    def root(self):
        return self.__root

    @property
    def url(self):
        url = str(self.__root)
        for filter, value in self.id.items():
            url = url + f'&{filter}={quote_plus(value)}'
        return url

    def parse(self, text: str):
        ps = _get_preload_state(text)
        if ps is None:
            raise KeyNotFound("__PRELOADED_STATE__ NOT FOUND")
        return ps

    @EndPointSearchCache(f"rec/search/max{PAGE_SIZE}/{{}}.json")
    def json(self) -> Union[Dict, None]:
        text = S.get(self.url).text
        return self.parse(text)

    @EndPointSearchFilterCache("rec/search/{}filters.json")
    def filters(self) -> Union[Dict, None]:
        obj = dict_walk(self.json(), 'core2/filters/Browse/data')
        must = {
            'orderby': ("Title Asc", "Title Desc"),
            'PlayWith': ("XboxSeriesX|S",),
            "Price": ("0", "40To70", "70To"),
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


class EndPointGiftPreloadState(EndPointSearchPreloadState):
    def __init__(self):
        super().__init__({'Price': "0"}, root=URL_GAMES_BROWSER_DEAL)


class EndPointSearchXboxSeries(EndPointSearchPreloadState):
    def __init__(self, id: Dict[str, str] = None, root=URL_GAMES_BROWSER):
        self.__root = root
        self.__keys = tuple(sorted(id.keys()))
        super().__init__({**{"PlayWith": "XboxSeriesX|S"}, **id})

    @EndPointSearchCache("rec/search/full/{}.json")
    def productSummaries(self) -> Union[Dict, None]:
        qrs = list(self.yield_queries())
        if len(qrs) == 0:
            return {}
        if len(qrs) == 1:
            return self.__productSummariesPage(qrs[0])
        obj = {}
        for query in qrs:
            ps = self.__productSummariesPage(query)
            obj = {**obj, **ps}
        squery = " ".join(f"{k}={v}" for k, v in self.id.items())
        logger.info(f"{len(obj):>4} {squery}")
        return obj

    @AuxCache("rec/search/aux/")
    def __productSummariesPage(self, query: Dict[str, str]):
        ps = EndPointSearchPreloadState(query, root=self.__root).productSummaries()
        if len(ps) >= PAGE_SIZE:
            ps = SearchWire.do_games_browse_search(self.__root, query)
        squery = " ".join(f"{k}={v}" for k, v in query.items())
        logger.info(f"{len(ps):>4} {squery}")
        return ps

    @EndPointSearchCache("rec/search/{}.txt")
    def ids(self):
        return tuple(sorted(self.productSummaries().keys()))

    def yield_queries(self):
        if self.__keys == ('IncludedInSubscription', ):
            yield dict(self.id)
            return
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
            'Price': ("0", "40To70", "70To"),
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
            return
        for c0 in choices[ksy[0]]:
            qr = {**query, **{ksy[0]: c0}}
            if len(ksy) == 1:
                yield qr
            else:
                for c1 in choices[ksy[1]]:
                    yield {**qr, **{ksy[1]: c1}}


class SearchWire(Driver):
    @staticmethod
    def do_games_browse_search(root: str, query: Dict[str, str]):
        url = None
        while True:
            try:
                with timeout(seconds=60*40):
                    with SearchWire(root=root) as web:
                        url = web.query_to_url(query)
                        return web.query(query)
            except (ProxyException, JSONDecodeError, KeyNotFound, TimeoutError, EOFError) as e:
                logger.critical(f"do_games_browse_search({url}) " + str(e))
                time.sleep(60)

    def __init__(self, root: str = URL_GAMES_BROWSER):
        super().__init__(browser="wirefirefox", wait=10)
        self.button = '//button[@aria-label="Cargar más"]'
        self.__root = root

    def query(self, query: Dict[str, str]):
        url = self.query_to_url(query)
        ids = self.__query_from_url(url)
        return ids

    def query_to_url(self, query: Dict[str, str]):
        url = self.__root + '&' + \
            '&'.join(map(lambda kv: kv[0]+'=' +
                     quote_plus(kv[1]), query.items()))
        return url

    def __query_from_url(self, url: str):
        self.get(url)
        obj = _get_preload_state(self.source)
        obj = dict_walk(obj, 'core2/products/productSummaries')
        if len(obj) == 0:
            return obj

        self.run_script('js/ol.js')
        while True:
            if 1 != self.safe_click(self.button, by=By.XPATH):
                return obj
            new_obj = self.__find_ids(set(obj.keys()))
            if len(new_obj):
                obj = {**obj, **new_obj}

    def __find_ids(self, done: Set[str]):
        path = "://emerald.xboxservices.com/xboxcomfd/browse"
        new_obj = {}
        try:
            with timeout(seconds=60):
                while True:
                    for js in self.__iter_requests_json(path):
                        aux = {
                            v['productId']: v for v in js['productSummaries'] if v['productId'] not in done}
                        new_obj = {**new_obj, **aux}
                    if len(new_obj) > 0:
                        return new_obj
                    error = self.__get_error()
                    if error:
                        logger.error(error)
                        return new_obj
        except TimeoutError:
            if self.safe_wait(self.button) is None:
                return {}
            return self.__find_ids(done)

    def __get_error(self):
        n = self.safe_wait("//div[contains(@class, '_errorText_')]", seconds=1)
        if n is None:
            return None
        txt = re_sp.sub(' ', n.text).strip()
        return txt

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
                logger.critical(f"NOT JSON: {r.path}")
                continue

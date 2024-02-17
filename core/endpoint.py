from typing import Union, Dict, Tuple
from .cache import Cache
from abc import ABC, abstractproperty
from functools import cached_property, cache
import requests
import json
from json.decoder import JSONDecodeError
import logging
from .findwireresponse import FindWireResponse
import re

logger = logging.getLogger(__name__)

S = requests.Session()
re_sp = re.compile(r"\s+")


class AccessDenied(Exception):
    pass


def _get_preload_state(text: str):
    for ln in text.split("\n"):
        ln = ln.strip()
        if ln.startswith("window.__PRELOADED_STATE__"):
            ln = ln.split("=", 1)[-1].strip().rstrip(";")
            return json.loads(ln)
    if "Access Denied" in text:
        raise AccessDenied()


class EndPointCache(Cache):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, kwself='slf', **kwargs)

    def parse_file_name(self, *args, slf: "EndPoint", **kargv):
        return self.file.format(id=slf.id)

    def save(self, file, data, *args, **kwargs):
        if data is not None:
            return super().save(file, data, *args, **kwargs)

    def read(self, file, *args, **kwargs):
        try:
            return super().read(file, *args, **kwargs)
        except JSONDecodeError:
            logger.critical("NOT JSON "+file)
            return None


class EndPoint(ABC):
    def __init__(self, id: str):
        self.id = id

    @abstractproperty
    def url(self) -> str:
        pass

    def parse(self, obj: Union[str, Dict, None]) -> Union[str, Dict, None]:
        return obj

    @cached_property
    def cache(self) -> EndPointCache:
        cache = getattr(self.json, "__cache_obj__", None)
        if not isinstance(cache, EndPointCache):
            raise NotImplementedError("needed EndPointCache in json method")
        return cache

    @cached_property
    def file(self) -> str:
        return self.cache.parse_file_name(slf=self)

    def save_in_cache(self, obj):
        self.cache.save(self.file, self.parse(obj))


class EndPointCollection(EndPoint):
    COLS = ("XboxIndieGames", "TopFree", "TopPaid", "New", "BestRated", "ComingSoon", "Deal", "MostPlayed")

    @property
    def url(self):
        if self.id == "XboxIndieGames":
            return "https://reco-public.rec.mp.microsoft.com/channels/Reco/v8.0/lists/collection/XboxIndieGames?itemTypes=Game&DeviceFamily=Windows.Xbox&market=es&count=2000"
        return "https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/"+self.id+"?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000"

    def get_list(self, url):
        js = S.get(url).json()
        rt = {i['Id']: i for i in js['Items']}
        tt = js['PagingInfo']['TotalItems']
        while len(rt) < tt:
            js = S.get(url+"&skipitems="+str(len(rt))).json()
            for i in js['Items']:
                rt[i['Id']] = i
        rt = sorted(rt.values(), key=lambda x: x['Id'])
        return rt

    @EndPointCache("rec/collection/{id}.json")
    def json(self) -> Union[Dict, None]:
        js = self.get_list(self.url)
        if js is None:
            logger.info("NON "+self.id)
        else:
            logger.info(f"{len(js):>3} {self.id}")
        return js

    @cache
    def ids(self) -> Tuple[str]:
        obj = self.json()
        gen = map(lambda x: x['Id'], (i for i in obj))
        return tuple(sorted(gen))


class EndPointCatalogList(EndPoint):
    UUID = r'"(\w{8}-\w{4}-\w{4}-\w{4}-\w{12})"'

    def __init__(self):
        self.id = "index"

    @property
    def url(self):
        return "https://www.xbox.com/en-US/xbox-game-pass/games/js/xgpcatPopulate-MWF2.js"

    def __get_key(self, d):
        t = re_sp.sub(" ", d[0]['title'])
        if re.search(r"EA ?Play", t):
            return "EAPlay"
        if t == "Juegos independientes":
            return "XboxIndieGames"
        if re.search(r"Game ?Pass", t) and "Próximamente" not in t:
            return "GamePass"
        if re.search(r"Ubisoft", t):
            return "Ubisoft"
        if t == "Bethesda Softworks":
            return "Bethesda"
        if "Xbox Series X|S" in t:
            return "XboxSeries"

    @EndPointCache("rec/catalog/{id}.json")
    def json(self) -> Union[Dict, None]:
        obj = dict(
            GamePass=["f6f1f99f-9b49-4ccd-b3bf-4d9767a77f5e"],
            EAPlay=["b8900d09-a491-44cc-916e-32b5acae621b"],
            Ubisoft=["aed03b50-b954-4ee4-a426-fe1686b64f85"],
            Bethesda=[]
        )
        text = S.get(self.url).text
        for w in sorted(set(re.findall(EndPointCatalogList.UUID, text))):
            d = EndPointCatalog(w).json()
            k = self.__get_key(d) or w
            if k not in obj:
                obj[k] = []
            if w not in obj[k]:
                obj[k].append(w)
        catalogs: Dict[str, Tuple[str]] = {k: tuple(sorted(v)) for k,v in obj.items()}
        logger.info(f"{len(catalogs):>3} catalogs")
        return catalogs


class EndPointCatalog(EndPoint):
    @property
    def url(self):
        return "https://catalog.gamepass.com/sigls/v2?language=es-es&market=ES&id="+self.id

    @EndPointCache("rec/catalog/{id}.json")
    def json(self) -> Union[Dict, None]:
        js = S.get(self.url).json()
        if js is None:
            logger.info("NON "+self.id)
        else:
            logger.info(f"{len(js):>3} {self.id}")
        return js

    @cache
    def ids(self) -> Tuple[str]:
        obj = self.json()
        gen = map(lambda x: x['id'], obj[1:])
        return tuple(sorted(gen))


class EndPointProduct(EndPoint):
    @property
    def url(self):
        MSCV = 'MS-CV=DGU1mcuYo0WMMp+F.1'
        return "https://displaycatalog.mp.microsoft.com/v7.0/products?" + MSCV + "&market=ES&languages=es-es&bigIds="+self.id

    def parse(self, js: Dict) -> Union[Dict, None]:
        for i in js['Products']:
            if i['ProductId'] == self.id:
                return i

    @EndPointCache("rec/product/{id}.json")
    def json(self) -> Union[Dict, None]:
        js = S.get(self.url).json()
        js = self.parse(js)
        return js


class EndPointProductPreloadState(EndPoint):
    @property
    def url(self):
        return "https://www.xbox.com/es-es/games/store/a/"+self.id

    def parse(self, text: str):
        data = _get_preload_state(text)
        if data is not None:
            return data['core2']

    @EndPointCache("rec/preload/{id}.json")
    def json(self) -> Union[Dict, None]:
        text = S.get(self.url).text
        return self.parse(text)


class EndPointWire(EndPoint):
    @property
    def path(self) -> str:
        raise NotImplementedError()

    @property
    def url(self):
        return None

    def find_response(self):
        return FindWireResponse.find_response(
            "https://www.xbox.com/es-es/games/store/a/"+self.id,
            self.path+self.id,
            keypath=self.path,
            keyarg=self.id
        )

    def _json(self):
        r = self.find_response()
        if r is None:
            return self.parse(None)
        return self.parse(r.json(self.id))


class EndPointActions(EndPointWire):
    @property
    def path(self):
        return "://emerald.xboxservices.com/xboxcomfd/productActions/"

    @EndPointCache("rec/action/{id}.json")
    def json(self) -> Union[Dict, None]:
        return self._json()


class EndPointReviews(EndPointWire):
    @property
    def path(self):
        return "://emerald.xboxservices.com/xboxcomfd/ratingsandreviews/summaryandreviews/"

    @EndPointCache("rec/review/{id}.json")
    def json(self) -> Union[Dict, None]:
        return self._json()

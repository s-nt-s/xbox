from typing import Union, Dict, Tuple, List
from .cache import Cache
from abc import ABC, abstractproperty
from functools import cached_property, cache
import requests
import json
from json.decoder import JSONDecodeError
import logging
from .findwireresponse import FindWireResponse, WireResponse
import re
from .util import dict_del, trim
from requests.exceptions import RequestException, Timeout, TooManyRedirects, HTTPError, ConnectionError
#                 id=endpoint.id,

logger = logging.getLogger(__name__)

S = requests.Session()
re_sp = re.compile(r"\s+")


def s_get(url: str):
    try:
        return S.get(url)
    except (RequestException, Timeout, TooManyRedirects, HTTPError, ConnectionError):
        logger.critical(f"Request failed: {url}")
        raise


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
        if data is None:
            return
        if file.endswith(".txt"):
            if not isinstance(data, (set, list, tuple)):
                raise ValueError(
                    "Para guardar como txt el objeto debe ser una lista de strings")
            ldata = list(data)
            if len(ldata) > 0 and not isinstance(ldata[0], str):
                raise ValueError(
                    "Para guardar como txt el objeto debe ser una lista de strings")
            data = "\n".join(sorted(set(ldata)))
        return super().save(file, data, *args, **kwargs)

    def read(self, file, *args, **kwargs):
        try:
            obj = super().read(file, *args, **kwargs)
            if isinstance(obj, str):
                lines = set(re.split(r"\s+", obj.strip()))
                if "" in lines:
                    lines.remove("")
                return tuple(sorted(lines))
            return obj
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

    @cache
    def get_cache(self) -> EndPointCache:
        cch = getattr(self.json, "__cache_obj__", None)
        if not isinstance(cch, EndPointCache):
            raise NotImplementedError("needed EndPointCache in json method")
        return cch

    @cached_property
    def file(self) -> str:
        return self.get_cache().parse_file_name(slf=self)

    def save_in_cache(self, obj):
        self.get_cache().save(self.file, self.parse(obj))


class EndPointCollection(EndPoint):
    COLS = ("XboxIndieGames", "TopFree", "TopPaid", "New",
            "BestRated", "ComingSoon", "Deal", "MostPlayed")

    @property
    def url(self):
        if self.id == "XboxIndieGames":
            return "https://reco-public.rec.mp.microsoft.com/channels/Reco/v8.0/lists/collection/XboxIndieGames?itemTypes=Game&DeviceFamily=Windows.Xbox&market=es&count=2000"
        return "https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/"+self.id+"?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000"

    def get_list(self, url):
        js = s_get(url).json()
        rt = {i['Id']: i for i in js['Items']}
        tt = js['PagingInfo']['TotalItems']
        while len(rt) < tt:
            js = s_get(url+"&skipitems="+str(len(rt))).json()
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
            logger.info(f"{len(js):>4} {self.id}")
        return js

    @EndPointCache("rec/collection/{id}.txt")
    def ids(self) -> Tuple[str]:
        obj = self.json()
        ids = list(map(lambda x: trim(x['Id']), (i for i in obj)))
        if None in ids:
            ids.remove(None)
        return tuple(ids)


class EndPointCatalogList(EndPoint):
    UUID = r'"(\w{8}-\w{4}-\w{4}-\w{4}-\w{12})"'

    def __init__(self):
        self.id = "index"

    @property
    def url(self):
        return "https://www.xbox.com/en-US/xbox-game-pass/games/js/xgpcatPopulate-MWF2.js"

    @EndPointCache("rec/catalog/{id}.txt")
    def json(self) -> Tuple[str]:
        catalogs = set()
        ids = [
            "f6f1f99f-9b49-4ccd-b3bf-4d9767a77f5e",
            "b8900d09-a491-44cc-916e-32b5acae621b",
            "aed03b50-b954-4ee4-a426-fe1686b64f85"
        ]
        text = s_get(self.url).text
        for w in sorted(set(ids+re.findall(EndPointCatalogList.UUID, text))):
            e = EndPointCatalog(w)
            if set(e.title.split()).intersection({"PC", "Próximamente"}):
                continue
            if len(e.json()):
                catalogs.add(w)
        logger.info(f"{len(catalogs):>4} catalogs")
        return tuple(sorted(catalogs))


class EndPointCatalog(EndPoint):
    @property
    def url(self):
        return "https://catalog.gamepass.com/sigls/v2?language=es-es&market=ES&id="+self.id

    @EndPointCache("rec/catalog/{id}.json")
    def json(self) -> Union[Dict, None]:
        js = s_get(self.url).json()
        if js is None:
            logger.info("NON "+self.id)
        else:
            logger.info(f"{len(js):>4} {self.id}")
        return js

    @cached_property
    def title(self):
        return re_sp.sub(" ", self.json()[0]['title'])

    @cached_property
    def tag(self):
        if re.search(r"EA ?Play", self.title):
            return "EAPlay"
        if self.title == "Juegos independientes":
            return "XboxIndieGames"
        if re.search(r"Game ?Pass", self.title):
            return "GamePass"
        if re.search(r"Ubisoft", self.title):
            return "Ubisoft"
        if self.title == "Bethesda Softworks":
            return "Bethesda"
        if "Xbox Series X|S" in self.title:
            return "XboxSeries"

    @EndPointCache("rec/catalog/{id}.txt")
    def ids(self) -> Tuple[str]:
        obj = self.json()
        ids = sorted(map(lambda x: trim(x['id']), obj[1:]))
        if None in ids:
            ids.remove(None)
        return tuple(ids)


class EndPointProduct(EndPoint):
    @property
    def url(self):
        MSCV = 'MS-CV=DGU1mcuYo0WMMp+F.1'
        return "https://displaycatalog.mp.microsoft.com/v7.0/products?" + MSCV + "&market=ES&languages=es-es&bigIds="+self.id

    def __parse(self, obj: Dict):
        dict_del(obj, 'LocalizedProperties/0/SearchTitles')
        return obj

    def parse(self, js: Dict) -> Union[Dict, None]:
        if 'Products' not in js:
            raise KeyError(f'Products not found in {self.url} {js}')
        for i in js['Products']:
            if i['ProductId'] == self.id:
                return self.__parse(i)

    @EndPointCache("rec/product/{id}.json")
    def json(self) -> Union[Dict, None]:
        js = s_get(self.url).json()
        js = self.parse(js)
        return js


class EndPointProductPreloadState(EndPoint):
    @property
    def url(self):
        return "https://www.xbox.com/es-es/games/store/a/"+self.id

    def parse(self, text: str):
        data = _get_preload_state(text)
        if data is None:
            return None

        def rm_other_games(obj: Union[Dict, List]):
            if not isinstance(obj, (dict, list)):
                return False
            if isinstance(obj, dict) and self.id not in obj:
                obj = list(obj.values())
            if isinstance(obj, list):
                rt_arr = []
                for i in obj:
                    rt_arr.append(rm_other_games(i))
                return any(rt_arr)
            for k in list(obj.keys()):
                if k != self.id and len(k) == 12 and k.upper() == k:
                    del obj[k]
            return True

        data = data['core2']
        for k in (
            'wishlist',
            'cart',
            'accountLink',
            'contextualStore',
            'search',
            'filters',
            'support',
            'serviceErrorMessages',
            # 'A los usuarios también les gusta esto'
            'channels/channelsData/PAL_' + self.id,
            'products/layouts'
        ):
            dict_del(data, k)
        if rm_other_games(data) is False:
            return 404
        return data

    @EndPointCache("rec/preload/{id}.json")
    def json(self) -> Union[Dict, None]:
        text = s_get(self.url).text
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
            path=self.path+self.id,
            keypath=self.path,
            keyarg=self.id
        )

    def _json(self):
        r = self.find_response()
        if not isinstance(r, WireResponse):
            return self.parse(r)
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

from typing import Union, Dict
from .cache import Cache
from abc import ABC, abstractproperty, abstractmethod
from functools import cached_property
import requests
import json
from json.decoder import JSONDecodeError
import logging
from .findwireresponse import FindWireResponse

logger = logging.getLogger(__name__)

S = requests.Session()


class EndPointCache(Cache):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, kwself='slf', **kwargs)

    def parse_file_name(self, *args, slf: "EndPoint", **kargv):
        return self.file.format(id=slf.id)

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

    @abstractproperty
    def parse(self, obj: Union[str, Dict]) -> Dict:
        pass

    @abstractmethod
    def json(self):
        pass

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


class EndPointGame(EndPoint):
    @property
    def url(self):
        MSCV = 'MS-CV=DGU1mcuYo0WMMp+F.1'
        return "https://displaycatalog.mp.microsoft.com/v7.0/products?" + MSCV + "&market=ES&languages=es-es&bigIds="+self.id

    def parse(self, js: Dict) -> Union[Dict, None]:
        for i in js['Products']:
            if i['ProductId'] == self.id:
                return i

    @EndPointCache("rec/gm/{id}.json")
    def json(self) -> Union[Dict, None]:
        js = S.get(self.url).json()
        return self.parse(js)


class EndPointPreloadState(EndPoint):
    @property
    def url(self):
        return "https://www.xbox.com/es-es/games/store/a/"+self.id

    def parse(self, text: str):
        for ln in text.split("\n"):
            ln = ln.strip()
            if ln.startswith("window.__PRELOADED_STATE__"):
                ln = ln.split("=", 1)[-1].strip().rstrip(";")
                return json.loads(ln)

    @EndPointCache("rec/ps/{id}.json")
    def json(self, text: Union[None, str] = None) -> Union[Dict, None]:
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

    def parse(self, js: Dict):
        return js

    @EndPointCache("rec/ac/{id}.json")
    def json(self) -> Union[Dict, None]:
        return self._json()


class EndPointReviews(EndPointWire):
    @property
    def path(self):
        return "://emerald.xboxservices.com/xboxcomfd/ratingsandreviews/summaryandreviews/"

    @property
    def url(self):
        return None

    def parse(self, js: Dict):
        if js is None:
            return None
        if 'ratingsSummary' not in js:
            if js.get('totalReviews') == 0:
                return {
                    "totalRatingsCount": 0
                }
            logger.critical(self.id+" revies bad format "+str(js))
            return None
        return js['ratingsSummary']

    @EndPointCache("rec/rw/{id}.json")
    def json(self, js: Union[None, Dict] = None) -> Union[Dict, None]:
        return self._json()

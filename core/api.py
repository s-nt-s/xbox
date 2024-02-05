from functools import lru_cache

import requests
from munch import Munch
from simplejson.errors import JSONDecodeError

from .cache import Cache
from .web import get_session, Driver
import json
from seleniumwire.webdriver.request import Request as WireRequest
from typing import NamedTuple, Union, Tuple
from core.game import Game, MSCV

'''
https://www.reddit.com/r/XboxGamePass/comments/jt214y/public_api_for_fetching_the_list_of_game_pass/

https://reco-public.rec.mp.microsoft.com/channels/Reco/v8.0/lists/collection/XboxIndieGames?itemTypes=Game&DeviceFamily=Windows.Xbox&market=es&count=200&skipItems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/TopFree?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/TopPaid?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/New?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/BestRated?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/ComingSoon?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/Deal?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/TopFree?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/MostPlayed?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
'''

S = requests.Session()

ss = None


def myex(e, msg):
    largs = list(e.args)
    if len(largs) == 1 and isinstance(largs, str):
        largs[0] = largs[0]+' '+msg
    else:
        largs.append(msg)
    e.args = tuple(largs)
    return e


def chunks(lst, n):
    arr = []
    for i in lst:
        arr.append(i)
        if len(arr) == n:
            yield arr
            arr = []
    if arr:
        yield arr


def get_js(url):
    global ss
    if ss is None:
        ss = get_session("https://www.xbox.com/es-ES/games/free-to-play")
    rq = ss._get(url)
    try:
        return rq.json()
    except JSONDecodeError as e:
        text = rq.text.strip()
        if len(text) == 0:
            raise myex(e, 'becouse request.get("%s") is empty' % (url))
        raise myex(e, 'in request.get("%s") = %s' % (url, rq.text))


class WR(NamedTuple):
    id: str
    requests: WireRequest
    body: dict

    def replay(self, id):
        s = requests.Session()
        s.headers = self.requests.headers
        r = requests.request(
            self.requests.method,
            self.requests.path.replace(self.id, id),
            headers=self.requests.headers
        )
        return r.json()


class ApiDriver:
    def __init__(self, *args, **kwargs):
        self.__web = None
        self.__args = args
        self.__kwargs = kwargs
        self.__endpoints: dict[str, WR] = {}

    def __enter__(self, *args, **kwargs):
        return self

    def __exit__(self, *args, **kwargs):
        if self.__web is not None:
            self.__web.close()

    @property
    def web(self):
        if self.__web is None:
            self.__web = Driver(*self.__args, **self.__kwargs)
        return self.__web

    def find_requests(self, id, path):
        url = Api.get_url_html(id)
        self.web.get(url)
        while True:
            if "Error response" in str(self.web.get_soup()):
                self.web.get(url)
            for r in self.web._driver.requests:
                if (path+id) not in r.path:
                    continue
                if r.response and r.response.body:
                    js = r.response.body
                    js = js.decode('utf-8')
                    js = js.strip()
                    js = json.loads(js)
                    return WR(
                        id=id,
                        requests=r,
                        body=js
                    )

    def get(self, id, path):
        if path in self.__endpoints:
            js = self.__endpoints[path].replay(id)
            return js
        r = self.find_requests(id, path)
        self.__endpoints[path] = r
        return r.body

    def get_enpoint(self, path):
        return self.__endpoints.get(path)


class Api:
    COLS = ("XboxIndieGames", "TopFree", "TopPaid", "New",
            "BestRated", "ComingSoon", "Deal", "MostPlayed")
    GMPS = dict(
        GamePass="f6f1f99f-9b49-4ccd-b3bf-4d9767a77f5e",
        EAPlay="b8900d09-a491-44cc-916e-32b5acae621b"
    )

    def __init__(self):
        pass

    @staticmethod
    def get_url_collection(collection):
        if collection == "XboxIndieGames":
            return "https://reco-public.rec.mp.microsoft.com/channels/Reco/v8.0/lists/collection/XboxIndieGames?itemTypes=Game&DeviceFamily=Windows.Xbox&market=es&count=200"
        return "https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/"+collection+"?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000"

    @staticmethod
    def get_url_gamepass(id):
        return "https://catalog.gamepass.com/sigls/v2?language=es-es&market=ES&id="+id

    @staticmethod
    def get_url_game(id: Union[str, Tuple[str]]):
        if isinstance(id, tuple):
            id = ",".join(id)
        return "https://displaycatalog.mp.microsoft.com/v7.0/products?" + MSCV + "&market=ES&languages=es-es&bigIds="+id

    @staticmethod
    def get_path_actions():
        return "://emerald.xboxservices.com/xboxcomfd/productActions/"

    @staticmethod
    def get_path_reviews():
        return "://emerald.xboxservices.com/xboxcomfd/ratingsandreviews/summaryandreviews/"
    
    def get_list(self, url):
        js = S.get(url).json()
        rt = {i['Id']: i for i in js['Items']}
        tt = js['PagingInfo']['TotalItems']
        while len(rt) < tt:
            js = get_js(url+"&skipitems="+str(len(rt)))
            for i in js['Items']:
                rt[i['Id']] = i
        rt = sorted(rt.values(), key=lambda x: x['Id'])
        return rt

    @Cache("rec/{}.json")
    def get_collection(self, collection):
        url = Api.get_url_collection(collection)
        return self.get_list(url)

    @Cache("rec/{}.json")
    def get_gamepass(self, id):
        url = Api.get_url_gamepass(id)
        return S.get(url).json()

    @lru_cache(maxsize=None)
    def get_catalog(self):
        def to_tup(id, gen):
            return tuple(sorted(set(i[id] for i in gen)))
        rt = {}
        for k, id in Api.GMPS.items():
            js = self.get_gamepass(id)
            rt[k] = to_tup('id', js[1:])
        for c in Api.COLS:
            rt[c] = to_tup('Id', self.get_collection(c))
        return Munch.fromDict(rt)

    def get_all(self):
        rt = {}
        for col in Api.COLS:
            for i in self.get_collection(col):
                rt[i['Id']] = i
        rt = sorted(rt.values(), key=lambda x: x['Id'])
        return rt

    def get_ids(self):
        ids = set(i['Id'] for i in self.get_all())
        ids = tuple(sorted(ids))
        return ids

    @Cache("rec/gm/{0}.json")
    def get_item(self, id):
        url = Api.get_url_game(id)
        js = get_js(url)
        rt = js['Products']
        if len(rt) == 1:
            return rt[0]
        return None

    @staticmethod
    def get_url_html(id: str):
        return "https://www.xbox.com/es-es/games/store/a/"+id

    @Cache("rec/ps/{0}.json", maxOld=10)
    def get_preload_state(self, id, **kvargs):
        url = Api.get_url_html(id)
        r = S.get(url)
        for ln in r.text.split("\n"):
            ln = ln.strip()
            if ln.startswith("window.__PRELOADED_STATE__"):
                ln = ln.split("=", 1)[-1].strip().rstrip(";")
                ln = json.loads(ln)
                return ln

    @Cache("rec/ac/{1}.json", maxOld=10)
    def get_actions(self, web: ApiDriver, id, **kvargs):
        js = web.get(id, Api.get_path_actions())
        return js

    @Cache("rec/rw/{1}.json", maxOld=10)
    def get_reviews(self, web: ApiDriver, id, **kvargs):
        js = web.get(id, Api.get_path_reviews())
        if 'ratingsSummary' not in js and js.get('totalReviews') == 0:
            return {
                "totalRatingsCount": 0
            }
        return js['ratingsSummary']

    def get_items(self, *ids) -> list[Game]:
        if len(ids) == 0:
            ids = [i['Id'] for i in self.get_all()]
        ids = sorted(set(ids))
        rt = [self.get_item(id) for id in ids]
        gm = []
        for i in rt:
            id = i['ProductId']
            collections = set()
            for k, v in self.get_catalog().items():
                if id in v:
                    collections.add(k)
            i = Game(i, tuple(sorted(collections)))
            gm.append(i)
        return gm

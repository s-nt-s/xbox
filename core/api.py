from functools import cache

import requests

from .cache import Cache
from .web import Driver
from .util import dict_walk
import json
from seleniumwire.webdriver.request import Request as WireRequest
from typing import NamedTuple, Dict, Set, Tuple
import re
import logging
from .searchwire import SearchWire


logger = logging.getLogger(__name__)
re_sp = re.compile(r"\s+")

'''
https://www.reddit.com/r/XboxGamePass/comments/jt214y/public_api_for_fetching_the_list_of_game_pass/

https://reco-public.rec.mp.microsoft.com/channels/Reco/v8.0/lists/collection/XboxIndieGames?itemTypes=Game&DeviceFamily=Windows.Xbox&market=es&count=200&skipItems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/TopFree?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/TopPaid?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/New?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/BestRated?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/ComingSoon?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/Deal?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/MostPlayed?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
'''

S = requests.Session()


def chunks(lst, n):
    arr = []
    for i in lst:
        arr.append(i)
        if len(arr) == n:
            yield arr
            arr = []
    if arr:
        yield arr


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
        self.__endpoints: Dict[str, WR] = {}

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
    CATALOG = dict(
        GamePass=["f6f1f99f-9b49-4ccd-b3bf-4d9767a77f5e"],
        EAPlay=["b8900d09-a491-44cc-916e-32b5acae621b"],
        Ubisoft=["aed03b50-b954-4ee4-a426-fe1686b64f85"],
        Bethesda=[]
    )

    def __init__(self):
        pass

    @staticmethod
    def get_url_collection(collection):
        if collection == "XboxIndieGames":
            return "https://reco-public.rec.mp.microsoft.com/channels/Reco/v8.0/lists/collection/XboxIndieGames?itemTypes=Game&DeviceFamily=Windows.Xbox&market=es&count=2000"
        return "https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/"+collection+"?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000"

    @staticmethod
    def get_url_catalog(id):
        return "https://catalog.gamepass.com/sigls/v2?language=es-es&market=ES&id="+id

    def search_catalog(self):
        def _key(d):
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
        r = S.get("https://www.xbox.com/en-US/xbox-game-pass/games/js/xgpcatPopulate-MWF2.js")
        for w in sorted(set(re.findall(r'"(\w{8}-\w{4}-\w{4}-\w{4}-\w{12})"', r.text))):
            d = self.get_catalog(w)
            k = _key(d) or w
            if k not in Api.CATALOG:
                Api.CATALOG[k] = []
            if w not in Api.CATALOG[k]:
                Api.CATALOG[k].append(w)

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

    @Cache("rec/{}.json")
    def get_collection(self, collection):
        url = Api.get_url_collection(collection)
        return self.get_list(url)

    @Cache("rec/{}.json")
    def get_catalog(self, id):
        url = Api.get_url_catalog(id)
        return S.get(url).json()

    @cache
    def get_dict_catalog(self):
        rt: Dict[str, Set[str]] = {}

        def __add(k, id, gen):
            if k not in rt:
                rt[k] = set()
            rt[k] = rt[k].union((i[id] for i in gen))

        self.search_catalog()
        for k, cats in Api.CATALOG.items():
            for cat in cats:
                __add(k, 'id', self.get_catalog(cat)[1:])
        for k in Api.COLS:
            __add(k, 'Id', self.get_collection(k))
        for k, ids in self.do_games_browse_search().items():
            if k not in rt:
                rt[k] = set()
            rt[k] = rt[k].union(ids)

        data: Dict[str, Tuple[str]] = {}
        for k, ids in rt.items():
            data[k] = tuple(sorted(ids))
        return data

    def get_ids(self):
        ids = set()
        for cids in self.get_dict_catalog().values():
            ids = ids.union(cids)
        ids = tuple(ids)
        return ids

    def do_games_browse_search(self):
        def _key(filter: str, choice: Dict):
            t = re_sp.sub(" ", choice['title'])
            if filter == "PlayWith" and re.search(r"Xbox ?Series", t):
                return "XboxSeries"
            if filter != "IncludedInSubscription":
                return None
            if re.search(r"\bPC\b", t):
                return None
            if re.search(r"Game ?Pass", t):
                return "GamePass"
            if re.search(r"EA ?Play", t):
                return "EAPlay"
            if re.search(r"Ubisoft", t):
                return "Ubisoft"
            logger.info("Nueva susbscripción %s", choice)
            return "IncludedInSubscription="+choice['id']

        obj = SearchWire.get_filters()
        data = {}
        for filter, v in obj.items():
            for c in v['choices']:
                k = _key(filter, c)
                if k is None:
                    continue
                data[k] = SearchWire.do_games_browse_search(v['id'], c['id'])
        return data


if __name__ == "__main__":
    Api().do_games_browse_search()

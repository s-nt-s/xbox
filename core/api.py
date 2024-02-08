from functools import cache

import requests

from .cache import Cache
from .web import Driver
import json
from seleniumwire.webdriver.request import Request as WireRequest
from typing import NamedTuple

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
            return "https://reco-public.rec.mp.microsoft.com/channels/Reco/v8.0/lists/collection/XboxIndieGames?itemTypes=Game&DeviceFamily=Windows.Xbox&market=es&count=2000"
        return "https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/"+collection+"?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000"

    @staticmethod
    def get_url_gamepass(id):
        return "https://catalog.gamepass.com/sigls/v2?language=es-es&market=ES&id="+id

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
    def get_gamepass(self, id):
        url = Api.get_url_gamepass(id)
        return S.get(url).json()

    @cache
    def get_catalog(self):
        def to_tup(id, gen):
            return tuple(sorted(set(i[id] for i in gen)))
        rt = {}
        for k, id in Api.GMPS.items():
            js = self.get_gamepass(id)
            rt[k] = to_tup('id', js[1:])
        for c in Api.COLS:
            rt[c] = to_tup('Id', self.get_collection(c))
        return rt

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

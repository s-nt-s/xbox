from .bulkrequests import BulkRequestsFileJob
from .api import Api, ApiDriver, WR
from .cache import Cache
from aiohttp import ClientSession
from typing import Tuple
from os.path import isfile
import json
import time


class BulkRequestsCollection(BulkRequestsFileJob):
    def __init__(self, id: str):
        self.api = Api()
        self.id = id
        self.cache: Cache = getattr(self.api.get_collection, "__cache_obj__")

    @property
    def url(self):
        return Api.get_url_collection(self.id)

    @property
    def file(self):
        return self.cache.parse_file_name(self.id)

    async def __do(self, session: ClientSession, url: str) -> dict:
        async with session.get(url) as response:
            js = await response.json()
            return js

    async def do(self, session: ClientSession) -> bool:
        data = {}
        tail = ""
        while True:
            js = await self.__do(session, self.url+tail)
            for i in js['Items']:
                data[i['Id']] = i
            tt = js['PagingInfo']['TotalItems']
            if len(data) >= tt:
                break
            tail = "&skipitems="+str(len(data))
        rt = sorted(data.values(), key=lambda x: x['Id'])
        self.cache.save(self.file, rt)
        return True


class BulkRequestsGamepass(BulkRequestsFileJob):
    def __init__(self, id: str):
        self.api = Api()
        self.id = id
        self.cache: Cache = getattr(self.api.get_gamepass, "__cache_obj__")

    @property
    def url(self):
        return Api.get_url_gamepass(self.id)

    @property
    def file(self):
        return self.cache.parse_file_name(self.id)

    async def do(self, session: ClientSession) -> bool:
        async with session.get(self.url) as response:
            js = await response.json()
            self.cache.save(self.file, js)
            return True


class BulkRequestsGame(BulkRequestsFileJob):
    def __init__(self, ids: Tuple[str]):
        self.api = Api()
        self.ids = ids
        self.cache: Cache = getattr(self.api.get_item, "__cache_obj__")

    @property
    def url(self):
        return Api.get_url_game(self.ids)

    @property
    def file(self):
        raise NotImplementedError()

    def done(self) -> bool:
        for id in self.ids:
            file = self.cache.parse_file_name(id)
            if not isfile(file):
                return False
        return True

    async def do(self, session: ClientSession) -> bool:
        async with session.get(self.url) as response:
            js = await response.json()
            for i in js['Products']:
                file = self.cache.parse_file_name(i['ProductId'])
                self.cache.save(file, i)
            return True


class BulkRequestsPreloadState(BulkRequestsFileJob):
    def __init__(self, id: str):
        self.api = Api()
        self.id = id
        self.cache: Cache = getattr(self.api.get_preload_state, "__cache_obj__")

    @property
    def url(self):
        return Api.get_url_html(self.id)

    @property
    def file(self):
        return self.cache.parse_file_name(self.id)

    async def do(self, session: ClientSession) -> bool:
        async with session.get(self.url) as response:
            text = await response.text()
            for ln in text.split("\n"):
                ln = ln.strip()
                if ln.startswith("window.__PRELOADED_STATE__"):
                    ln = ln.split("=", 1)[-1].strip().rstrip(";")
                    js = json.loads(ln)
                    self.cache.save(self.file, js)
                    time.sleep(0.5)
                    return True


class BulkRequestsActions(BulkRequestsFileJob):
    _WR: WR = None

    def __init__(self, id: str):
        self.api = Api()
        self.id = id
        self.cache: Cache = getattr(self.api.get_actions, "__cache_obj__")

    @property
    def wr(self) -> WR:
        if BulkRequestsActions._WR is None:
            with ApiDriver(browser="wirefirefox") as web:
                web.get(self.id, Api.get_path_actions())
                BulkRequestsActions._WR = web.get_enpoint(Api.get_path_actions())
        return BulkRequestsActions._WR

    @property
    def url(self):
        raise NotImplementedError()

    @property
    def file(self):
        return self.cache.parse_file_name(None, self.id)

    async def do(self, session: ClientSession) -> bool:
        async with session.request(
            self.wr.requests.method,
            self.wr.requests.path.replace(self.wr.id, self.id),
            headers=self.wr.requests.headers

        ) as response:
            js = await response.json()
            self.cache.save(self.file, js)
            return True


class BulkRequestsReviews(BulkRequestsFileJob):
    _WR: WR = None

    def __init__(self, id: str):
        self.api = Api()
        self.id = id
        self.cache: Cache = getattr(self.api.get_reviews, "__cache_obj__")

    @property
    def wr(self) -> WR:
        if BulkRequestsActions._WR is None:
            with ApiDriver(browser="wirefirefox") as web:
                web.get(self.id, Api.get_path_reviews())
                BulkRequestsActions._WR = web.get_enpoint(Api.get_path_reviews())
        return BulkRequestsActions._WR

    @property
    def url(self):
        raise NotImplementedError()

    @property
    def file(self):
        return self.cache.parse_file_name(None, self.id)

    async def do(self, session: ClientSession) -> bool:
        async with session.request(
            self.wr.requests.method,
            self.wr.requests.path.replace(self.wr.id, self.id),
            headers=self.wr.requests.headers

        ) as response:
            js = await response.json()
            self.cache.save(self.file, js)
            return True

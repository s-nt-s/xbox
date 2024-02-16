from .bulkrequests import BulkRequestsFileJob
from aiohttp import ClientSession
from typing import Tuple
from os.path import isfile
from .endpoint import EndPointProduct, EndPointProductPreloadState, EndPointActions, EndPointReviews
import time


class BulkRequestsGame(BulkRequestsFileJob):
    def __init__(self, ids: Tuple[str]):
        self.ids = ids

    @property
    def url(self):
        return EndPointProduct(",".join(self.ids)).url

    @property
    def file(self):
        raise NotImplementedError()

    def done(self) -> bool:
        for id in self.ids:
            file = EndPointProduct(id).file
            if not isfile(file):
                return False
        return True

    async def do(self, session: ClientSession) -> bool:
        async with session.get(self.url) as response:
            js = await response.json()
            for i in js['Products']:
                endpoint = EndPointProduct(i['ProductId'])
                endpoint.save_in_cache(js)
            return True


class BulkRequestsPreloadState(BulkRequestsFileJob):
    def __init__(self, id: str):
        self.endpoint = EndPointProductPreloadState(id)

    @property
    def url(self):
        return self.endpoint.url

    @property
    def file(self):
        return self.endpoint.file

    async def do(self, session: ClientSession) -> bool:
        async with session.get(self.url) as response:
            text = await response.text()
            self.endpoint.save_in_cache(text)
            time.sleep(0.5)  # Evitar baneo
            return self.done()


class BulkRequestsActions(BulkRequestsFileJob):
    def __init__(self, id: str):
        self.endpoint = EndPointActions(id)

    @property
    def url(self):
        return self.endpoint.url

    @property
    def file(self):
        return self.endpoint.file

    async def do(self, session: ClientSession) -> bool:
        wr = self.endpoint.find_response()
        if wr is None:
            return False
        async with session.request(
            wr.requests.method,
            wr.requests.path.replace(wr.key, self.endpoint.id),
            headers=wr.requests.headers
        ) as response:
            js = await response.json()
            self.endpoint.save_in_cache(js)
            return True


class BulkRequestsReviews(BulkRequestsFileJob):
    def __init__(self, id: str):
        self.endpoint = EndPointReviews(id)

    @property
    def url(self):
        return self.endpoint.url

    @property
    def file(self):
        return self.endpoint.file

    async def do(self, session: ClientSession) -> bool:
        wr = self.endpoint.find_response()
        if wr is None:
            return False
        async with session.request(
            wr.requests.method,
            wr.requests.path.replace(wr.key, self.endpoint.id),
            headers=wr.requests.headers
        ) as response:
            js = await response.json()
            self.endpoint.save_in_cache(js)
            return True

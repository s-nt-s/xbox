from typing import NamedTuple, Dict
import requests
import json
from .web import Driver
from seleniumwire.webdriver.request import Request as WireRequest
from json.decoder import JSONDecodeError
import time
import logging

logger = logging.getLogger(__name__)


class WireResponse(NamedTuple):
    key: str
    requests: WireRequest
    body: dict

    def json(self, key) -> Dict:
        path = self.requests.path.replace(self.key, key)
        if path == self.requests.path:
            return self.body
        s = requests.Session()
        s.headers = self.requests.headers
        r = requests.request(
            self.requests.method,
            path,
            headers=self.requests.headers
        )
        return r.json()


class FindWireResponse:
    WR: Dict[str, WireResponse] = {}

    @staticmethod
    def __find_response(url: str, path: str, keyarg: str):
        with Driver(browser="wirefirefox") as web:
            web.get(url)
            while True:
                if "Access Denied" in str(web.get_soup()):
                    web.close()
                    logger.critical("AccessDenied when find_response")
                    time.sleep(600)
                    web.get(url)
                r: WireRequest
                for r in web._driver.requests:
                    if path not in r.path:
                        continue
                    if r.response and r.response.body:
                        bdy: bytes = r.response.body
                        txt = bdy.decode('utf-8')
                        txt = txt.strip()
                        try:
                            js = json.loads(txt)
                        except JSONDecodeError:
                            continue
                        return WireResponse(
                            key=keyarg,
                            requests=r,
                            body=js
                        )

    @staticmethod
    def find_response(url: str, path: str, keypath=None, keyarg=None):
        if keypath is None:
            keypath = path
        if FindWireResponse.WR.get(keypath) is None:
            FindWireResponse.WR[keypath] = FindWireResponse.__find_response(url, path, keyarg)
        return FindWireResponse.WR[keypath]

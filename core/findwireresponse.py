from typing import NamedTuple, Dict
import requests
import json
from .web import Driver
from seleniumwire.webdriver.request import Request as WireRequest
from json.decoder import JSONDecodeError
import time
import logging
from .timeout import timeout

logger = logging.getLogger(__name__)


class WireResponse(NamedTuple):
    key: str
    requests: WireRequest
    body: dict
    headers: dict

    def json(self, key, **kwargs) -> Dict:
        path = self.requests.path.replace(self.key, key)
        if path == self.requests.path:
            return self.body
        r = requests.request(
            self.requests.method,
            path,
            headers=self.requests.headers,
            **kwargs
        )
        return r.json()

    def get_session(self):
        s = requests.Session()
        s.headers = self.requests.headers
        return s


class FindWireResponse:
    WR: Dict[str, WireResponse] = {}

    @staticmethod
    def __find_response(*urls: str, path: str = None, keyarg: str, browser="wirefirefox"):
        with Driver(browser=browser) as web:
            def __go_to_url():
                for u in urls[:-1]:
                    web.get(u)
                    time.sleep(5)
                web.get(urls[-1])
            __go_to_url()
            while True:
                if "No se encuentra la página solicitada" in str(web.get_soup()):
                    return 404
                if "Access Denied" in str(web.get_soup()):
                    web.close()
                    logger.critical("AccessDenied when find_response")
                    time.sleep(600)
                    __go_to_url()
                if "Please complete a security check to continue" in str(web.get_soup()):
                    web.close()
                    logger.critical("Captcha when find_response")
                    time.sleep(600)
                    __go_to_url()
                for r in web.wirerequests:
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
                            body=js,
                            headers=r.headers
                        )
                for r in web.logged_requests:
                    r_url = r.get('url')
                    if not isinstance(r_url, str) or path not in r_url:
                        continue
                    txt = r.get('response', {}).get("body")
                    if not isinstance(txt, str):
                        continue
                    txt = txt.strip()
                    try:
                        js = json.loads(txt)
                    except JSONDecodeError:
                        continue
                    return WireResponse(
                        key=keyarg,
                        requests=None,
                        body=js,
                        headers=r.get("headers", {})
                    )

    @staticmethod
    def __safe_find_response(*urls: str, path: str = None, keyarg: str, browser="wirefirefox"):
        try:
            with timeout(seconds=60*30):
                return FindWireResponse.__find_response(*urls, path=path, keyarg=keyarg, browser=browser)
        except TimeoutError as e:
            logger.critical(f"Timeout in FindWireResponse.find_response({urls}, {path})")
            return 404

    @staticmethod
    def find_response(*urls: str, path: str = None, keypath=None, keyarg=None, browser="wirefirefox"):
        if not isinstance(path, str):
            raise ValueError(f"path must be str, not {path}")
        if len(urls) == 0:
            raise ValueError("urls must len >= 1")
        if keypath is None:
            keypath = path
        if FindWireResponse.WR.get(keypath) is None:
            r = FindWireResponse.__safe_find_response(*urls, path=path, keyarg=keyarg, browser=browser)
            if isinstance(r, int):
                return r
            FindWireResponse.WR[keypath] = r
        return FindWireResponse.WR[keypath]

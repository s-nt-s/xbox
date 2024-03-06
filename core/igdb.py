import requests
from functools import cached_property, cache
from typing import Tuple, Dict, Union
import logging

logger = logging.getLogger(__name__)


class IGDBException(Exception):
    pass


def get_chunks(array, size):
    array = tuple(array)
    for i in range(0, len(array), size):
        arr = tuple(array[i:i + size])
        if len(arr) > 0:
            yield arr


class IGDB:
    def __init__(self):
        self.s = requests.Session()
        self.s.headers.update({"Accept": "application/json"})

    def login(self, id: str, secret: str):
        r = self.s.post(
            f"https://id.twitch.tv/oauth2/token?client_id={id}&client_secret={secret}&grant_type=client_credentials")
        access_token = r.json()['access_token']
        self.s.headers.update({
            "Accept": "application/json",
            "Client-ID": id,
            "Authorization": "Bearer "+access_token
        })
        logger.debug("login OK")

    @cache
    def get(self, path: str, query: str, chunkme: Union[Tuple, None] = None) -> Tuple[Dict]:
        if chunkme is not None:
            return self.__get_chunk(path, query, chunkme, 2000)
        hasLimit = True
        arr = []
        ori_quey = str(query)
        offset = ''
        if "limit" not in query:
            query = query + ' limit 500;'
            hasLimit = False
        while True:
            chunk = self.__get(path, query+offset)
            arr.extend(chunk)
            if len(chunk) < 500 or hasLimit:
                logger.debug(f"{len(arr):>4} {path} {ori_quey}")
                return tuple(arr)
            offset = f'offset {len(arr)};'

    def __get_chunk(self, path: str, query: str, chunkme: Tuple, chunksize: int) -> Tuple[Dict]:
        if chunkme is None:
            raise ValueError("chunkme debe not None")
        if not isinstance(chunkme, tuple):
            raise ValueError(f"chunkme debe ser una tupla, no un {type(chunkme)}")
        if len(chunkme) == 0:
            raise ValueError("chunkme debe ser una tupla no vacía")
        if len(chunkme) <= chunksize:
            return self.get(path, query.format(chunkme), chunkme=None)
        arr = []
        for chunk in get_chunks(chunkme, chunksize):
            arr.extend(self.get(path, query.format(chunk), chunkme=None))
        logger.debug(f"{len(arr):>4} {path} {query.format(chunkme)}")
        return tuple(arr)

    def __get(self, path, query):
        url = 'https://api.igdb.com/v4/'+path
        r = self.s.post(url, data=query)
        js = r.json()
        if not isinstance(js, list):
            raise IGDBException(f"{url} {query} {str(js)}")
        if len(js) != 1:
            return js
        obj = js[0]
        if not isinstance(obj, dict):
            raise IGDBException(f"{url} {query} {str(obj)}")
        if len(set({"title", "status"}).difference(obj.keys())) == 0:
            raise IGDBException(f"{url} {query} {str(obj)}")
        return js

    def get_ids(self, path: str, query: str, chunkme: Union[Tuple, None] = None, idname='id') -> Tuple[int]:
        ids = set()
        for r in self.get(path, query, chunkme=chunkme):
            ids.add(r[idname])
        ids = tuple(sorted(ids))
        if chunkme is not None:
            query = query.format(chunkme)
        logger.info(f"{len(ids):>4} = {path} {query} == " + " ".join(map(str, ids)))
        return ids

    @cached_property
    def spanish(self):
        return self.get_ids("languages", 'fields locale; where locale = "es"*;')

    @cached_property
    def xbox(self):
        ids = self.get_ids('platforms', 'fields abbreviation,alternative_name; where name = "Xbox Series X|S";')
        return ids[0]

    @cached_property
    def language_support_types(self):
        lang = {}
        for r in self.get("language_support_types", 'fields name;'):
            lang[r['name'].lower()] = r['id']
        return lang

    def get_spanish_games(self) -> Dict[str, Tuple[int]]:
        lang_support = {}
        for name, support_type in self.language_support_types.items():
            lang_support[name] = self.get_ids('games', f'fields id; where release_dates.platform = {self.xbox} & language_supports.language = {self.spanish} & language_supports.language_support_type = {support_type};')
        return lang_support

    @cached_property
    def id_to_xbox(self):
        # https://api-docs.igdb.com/?python#external-game-enums
        data = {}
        category = 11
        for r in self.get('external_games', f'fields game, url; where category = {category};'):
            xbox: str = r['url'].split("/")[-1]
            if len(xbox) == 12 and xbox.upper() == xbox:
                data[r['game']] = xbox
        return data

    @cached_property
    def xbox_to_id(self):
        return {v: k for k, v in self.id_to_xbox.items()}

    @cache
    def get_language_supports(self, support_type):
        ids = tuple(sorted(self.id_to_xbox.keys()))
        noSpa = " & ".join(map(lambda x: f'language_supports.language != {x}', self.spanish))
        isSpa = self.get_ids(
            'games',
            f'fields id; where language_supports.language_support_type = {support_type} & language_supports.language = {self.spanish} & id = {{}};',
            chunkme=ids
        )
        isExt = self.get_ids(
            'games',
            f'fields id; where language_supports.language_support_type = {support_type} & {noSpa} & id = {{}};',
            chunkme=ids
        )
        return isSpa, isExt

    @cache
    def get_spanish(self, xboxid):
        igdbid = self.xbox_to_id.get(xboxid)
        if igdbid is None:
            return None

        def _is(st):
            isSpa, isExt = self.get_language_supports(st)
            if igdbid in isSpa:
                return True
            if igdbid in isExt:
                return False
            return None

        spanish = {}
        for name, support_type in self.language_support_types.items():
            spanish[name] = _is(support_type)
        vls = set(spanish.values())
        if len(vls) == 1 and vls.pop() is None:
            return None
        slog = []
        for k, v in spanish.items():
            if v is not None:
                slog.append(k+"="+str(v))
        logger.debug(f"{xboxid} {igdbid} {' '.join(slog)}")
        return spanish

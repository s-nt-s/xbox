import requests
from functools import cached_property, cache
from typing import Tuple, Dict


class IGDBException(Exception):
    pass


def get_chunks(array, size):
    array = list(array)
    for i in range(0, len(array), size):
        # Añadimos el trozo actual al resultado
        yield tuple(array[i:i + size])


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

    @cache
    def get(self, path, quey) -> Tuple[Dict]:
        def raise_if_error(url, data, chunk):
            if not isinstance(chunk, list):
                raise IGDBException(f"{url} {data} {str(chunk)}")
            if len(chunk) != 1:
                return
            obj = chunk[0]
            if not isinstance(obj, dict):
                raise IGDBException(f"{url} {data} {str(obj)}")
            if len(set({"title", "status"}).difference(obj.keys())) == 0:
                raise IGDBException(f"{url} {data} {str(obj)}")
        hasLimit = True
        arr = []
        if "limit" not in quey:
            quey = quey + 'limit 500;'
            hasLimit = False
        offset = ''
        while True:
            url = 'https://api.igdb.com/v4'+path
            data = quey+offset
            r = self.s.post(url, data=data)
            chunk = r.json()
            raise_if_error(url, data, chunk)
            arr.extend(chunk)
            if len(chunk) < 500 or hasLimit:
                return tuple(arr)
            offset = f'offset {len(arr)};'

    def get_ids(self, path, quey) -> Tuple[int]:
        ids = set()
        for r in self.get(path, quey):
            ids.add(r['id'])
        return tuple(sorted(ids))

    @cached_property
    def spanish(self):
        return self.get_ids("/languages", 'fields locale; where locale = "es"*;')

    @cached_property
    def xbox(self):
        ids = self.get_ids('/platforms', 'fields abbreviation,alternative_name; where name = "Xbox Series X|S";')
        return ids[0]

    @cached_property
    def language_support_types(self):
        lang = {}
        for r in self.get("/language_support_types", 'fields name;'):
            lang[r['name'].lower()] = r['id']
        return lang

    def get_spanish_games(self) -> Dict[str, Tuple[int]]:
        lang_support = {}
        for name, support_type in self.language_support_types.items():
            lang_support[name] = self.get_ids('/games', f'fields id; where release_dates.platform = {self.xbox} & language_supports.language = {self.spanish} & language_supports.language_support_type = {support_type};')
        return lang_support

    @cached_property
    def id_to_xbox(self):
        # https://api-docs.igdb.com/?python#external-game-enums
        data = {}
        category = 11
        for r in self.get('/external_games', f'fields game, url; where category = {category};'):
            xbox: str = r['url'].split("/")[-1]
            if len(xbox) == 12 and xbox.upper() == xbox:
                data[r['game']] = xbox
        return data

    @cached_property
    def xbox_to_id(self):
        return {v: k for k, v in self.id_to_xbox.items()}

    @cache
    def get_language_supports(self, support_type):
        isSpa = set()
        isExt = set()
        for chunk in get_chunks(self.id_to_xbox.keys(), 2000):
            isSpa = isSpa.union(self.get_ids('/games', f'fields id; where id = {chunk} & language_supports.language_support_type = {support_type} & language_supports.language = {self.spanish};'))
            isExt = isExt.union(self.get_ids('/games', f'fields id; where id = {chunk} & language_supports.language_support_type = {support_type} & ' + " & ".join(map(lambda x: f'language_supports.language != {x}', self.spanish))+' ;'))
        return tuple(sorted(isSpa)), tuple(sorted(isExt))

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
        return spanish

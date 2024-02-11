from functools import cache

import requests

from typing import Dict, Set, Tuple
import re
import logging
from .searchwire import SearchWire
from core.endpoint import EndPointCollection, EndPointCatalogList, EndPointCatalog


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


class Api:
    def __init__(self):
        pass

    @cache
    def get_dict_catalog(self):
        rt: Dict[str, Set[str]] = {}

        def __add(k, ids: Tuple[str]):
            if k not in rt:
                rt[k] = set()
            rt[k] = rt[k].union(ids)

        for k, cats in EndPointCatalogList().json().items():
            for cat in cats:
                __add(k, EndPointCatalog(cat).ids())
        for k in EndPointCollection.COLS:
            __add(k, EndPointCollection(k).ids())
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
        ids = tuple(sorted(ids))
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

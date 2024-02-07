import inspect
import re
from os.path import isfile
from functools import cached_property, cache
from typing import Union, Tuple, Dict
from math import ceil
from dataclasses import dataclass
from datetime import date
import json
from math import floor
from .endpoint import EndPointGame, EndPointPreloadState, EndPointActions, EndPointReviews
from .api import Api

YEAR = date.today().year+1
re_compras = re.compile(r"\bcompras\b", re.IGNORECASE)
re_date = re.compile(r"^\d{4}-\d{2}-\d{2}.*")


@cache
def collection():
    api = Api()
    data: Dict[str, Tuple[str]] = {}
    for id in api.get_ids():
        collections = set()
        for k, v in api.get_catalog().items():
            if id in v:
                collections.add(k)
        data[id] = tuple(sorted(collections))
    return data


def read_json(file):
    if isfile(file):
        with open(file, "r") as f:
            return json.load(f)


def iter_kv(obj, *breadcrumbs):
    if obj is None:
        yield "/".join(breadcrumbs), None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if isinstance(v, (dict, list)):
                yield from iter_kv(v, *breadcrumbs, k)
            else:
                yield "/".join(breadcrumbs+(k,)), v
    if isinstance(obj, list):
        for k, v in enumerate(obj):
            yield from iter_kv(v, *breadcrumbs, "["+str(k)+"]")


class Game:
    def __init__(self, id: str):
        self.id = id

    @cached_property
    def collections(self):
        return collection().get(self.id)

    @cached_property
    def i(self):
        return EndPointGame(self.id).json()

    @cached_property
    def productActions(self):
        return EndPointActions(self.id).json() or {"productActions": []}

    @cached_property
    def preload_state(self):
        return EndPointPreloadState(self.id).json()

    @cached_property
    def reviewsInfo(self):
        return EndPointReviews(self.id).json() or {}

    @cached_property
    def price(self) -> float:
        return self.i["DisplaySkuAvailabilities"][0]["Availabilities"][0]["OrderManagementData"]["Price"]["ListPrice"]

    @cached_property
    def discount(self) -> float:
        if self.preload_state is None:
            return 0
        obj = dict(self.preload_state)
        for k in ('core2', 'products', 'productSummaries', self.id, 'specificPrices', 'purchaseable'):
            obj = obj.get(k)
            if obj is None:
                return 0
        if not isinstance(obj, list) or len(obj) == 0 or not isinstance(obj[0], dict):
            return 0
        d = obj[0].get('discountPercentage') or 0
        return d

    @property
    def rate(self) -> float:
        averageRating = self.reviewsInfo.get('averageRating')
        if averageRating is not None:
            return averageRating
        AverageRating = self.i["MarketProperties"][0]["UsageData"][-1]["AverageRating"]
        return AverageRating

    @property
    def reviews(self) -> int:
        return self.reviewsInfo.get('totalRatingsCount')

    @cached_property
    def title(self) -> str:
        return self.i["LocalizedProperties"][0]["ProductTitle"]

    @cached_property
    def url(self) -> str:
        return "https://www.xbox.com/es-es/games/store/a/"+self.id

    @cached_property
    def productType(self) -> str:
        return self.i["ProductType"]

    @cached_property
    def imgs(self) -> tuple[str]:
        return tuple(["https:"+x["Uri"] for x in self.i["LocalizedProperties"][0]["Images"]])

    @cached_property
    def poster(self) -> str:
        for i in self.i["LocalizedProperties"][0]["Images"]:
            if i['ImagePurpose'] == 'Poster':
                return "https:"+i["Uri"]
        return self.imgs[0]

    @cached_property
    def thumbnail(self) -> str:
        return self.poster+"?q=40&w=150&h=225"

    @cached_property
    def attributes(self) -> tuple[str]:
        att = set()
        for a in (self.i['Properties']['Attributes'] or []):
            if 'Xbox' in (a['ApplicablePlatforms'] or []) or a['Name'].startswith("Xb"):
                att.add(a['Name'])
        return tuple(sorted(att))

    @property
    def actions(self) -> tuple[str]:
        act = set()
        for x in self.productActions["productActions"]:
            if x['productId'] != self.id:
                continue
            for a in x['productActions']:
                if a['actionArguments'].get('ProductId') != self.id:
                    continue
                act.add(a['actionType'])
            for aa in x['skuActionsBySkuId'].values():
                for a in aa:
                    if a['actionArguments'].get('ProductId') != self.id:
                        continue
                    act.add(a['actionType'])
        act = tuple(sorted(act))
        return act

    @property
    def legalNotices(self) -> tuple[str]:
        if self.preload_state is None:
            return []
        obj = dict(self.preload_state)
        for k in ('core2', 'products', 'productSummaries', self.id, 'legalNotices'):
            obj = obj.get(k)
            if obj is None:
                return tuple()
        if obj is None:
            return tuple()
        return tuple(obj)

    @property
    def interactiveDescriptions(self) -> tuple[str]:
        if self.preload_state is None:
            return []
        obj = dict(self.preload_state)
        for k in ('core2', 'products', 'productSummaries', self.id, 'contentRating', 'interactiveDescriptions'):
            obj = obj.get(k)
            if obj is None:
                return tuple()
        if obj is None:
            return tuple()
        return tuple(obj)

    @property
    def compras(self) -> tuple[str]:
        cmp = set()
        for x in self.interactiveDescriptions:
            if re_compras.search(x):
                cmp.add(x)
        return tuple(sorted(cmp))

    @property
    def tragaperras(self) -> bool:
        return len(self.compras) > 0 and 'TopFree' in self.collections

    @property
    def requiresGame(self) -> bool:
        return 'DlcRequiresGame' in self.legalNotices

    @property
    def notSoldSeparately(self) -> bool:
        return 'NotSoldSeparately' in self.actions

    @property
    def notAvailable(self) -> bool:
        return 'Acquisition' not in self.actions

    @property
    def onlyGamepass(self) -> bool:
        return self.gamepass and self.notSoldSeparately

    @cached_property
    def langs(self) -> tuple[str]:
        def find_lang(lng: str, arr: list[str]):
            for ln in arr:
                ln = ln.lower()
                if ln == lng or ln.startswith(lng+'-'):
                    return True
            return False
        langs = set()
        for x in (self.i['DisplaySkuAvailabilities'] or []):
            for m in (x['Sku']['MarketProperties'] or []):
                if find_lang('es', m['SupportedLanguages']):
                    langs.add('ES')
                elif find_lang('en', m['SupportedLanguages']):
                    langs.add('EN')
        langs = sorted(langs)
        return tuple(langs)

    @cached_property
    def categories(self) -> tuple[str]:
        return tuple(self.i['Properties']['Categories'] or [])

    @property
    def gamepass(self) -> bool:
        return 'GamePass' in self.collections or 'EAPlay' in self.collections

    @property
    def bundle(self) -> bool:
        return self.i["DisplaySkuAvailabilities"][0]["Sku"]['Properties']['IsBundle']

    @property
    def preorder(self) -> bool:
        if self.onlyGamepass:
            return False
        return self.i["DisplaySkuAvailabilities"][0]["Sku"]['Properties']['IsPreOrder']

    @property
    def trial(self) -> bool:
        return 'Trial' in self.actions

    @cached_property
    def releaseDate(self) -> Union[date, None]:
        dts = set()
        for k, v in iter_kv(self.i):
            if "Date" in k and isinstance(v, str) and re_date.match(v):
                dts.add(tuple(map(int, v[:10].split("-"))))
        for dt in sorted(dts):
            dt = date(*dt)
            if dt.year > 1951 and dt.year < YEAR:
                return dt

    @property
    def tags(self) -> tuple[str]:
        tags = []
        if self.productType != 'Game':
            tags.append(self.productType)
        if self.onlyGamepass:
            tags.append("SoloGamePass")
        if self.tragaperras:
            tags.append("Tragaperras")
        if self.compras:
            tags.append("Compras")
        if self.bundle:
            tags.append("Bundle")
        if self.preorder:
            tags.append("PreOrder")
        for x in self.categories:
            if x in ('Other', 'Word', 'Tools'):
                continue
            if x == 'Multi-player Online Battle Arena':
                x = 'MOBA'
            if x == 'Action & adventure':
                x = 'Action'
            if x == 'Card & board':
                x = 'Cards'
            if x == 'Family & kids':
                x = 'Family'
            if x == 'Puzzle & trivia':
                x = 'Puzzle'
            tags.append(x)
        for x in self.attributes:
            if x.endswith("fps"):
                continue
            if x in ("Capability4k", 'CapabilityHDR', 'DolbyAtmos', 'SpatialSound', 'XblClubs', 'XblAchievements', 'XblPresence', 'XblCloudSaves', 'XboxLive', 'DTSX', 'RayTracing'):
                continue
            if x in ('XblCrossPlatformCoop', 'XblCrossPlatformMultiPlayer', 'XboxLiveCrossGenMP'):
                x = 'CrossPlatform'
            if x in ('XblOnlineMultiPlayer', 'XblOnlineCoop'):
                x = 'MultiPlayer'
            if x in ('XblLocalMultiPlayer', 'XblLocalCoop', 'SharedSplitScreen'):
                x = 'LocalMultiPlayer'
            # if x == 'SharedSplitScreen':
            #    x = 'SplitScreen'
            tags.append(x)
        if 'TopFree' in self.collections:
            tags.append("Free")
        if 'GamePass' in self.collections:
            tags.append("GamePass")
        elif 'EAPlay' in self.collections:
            tags.append("EAPlay")
        # if self.gamepass:
        #    tags.append("GamePass")
        if self.discount > 0:
            tags.append("Oferta")
        tags = sorted(set(tags), key=lambda x: tags.index(x))
        return tuple(tags)

    def to_dict(self) -> dict:
        dt = {}
        for k, v in inspect.getmembers(self):
            if k[0] != '_' and isinstance(v, (str, int, float, tuple)):
                dt[k] = v
        return dt

    def to_js(self) -> dict:
        ks = ('gamepass', 'id', 'price', 'rate',
              'reviews', 'tags', 'trial', 'discount')
        dt = {}
        for k, v in inspect.getmembers(self):
            if k in ks and isinstance(v, (str, int, float, tuple)):
                dt[k] = v
        return dt


@dataclass(frozen=True)
class GameList:
    items: tuple[Game]

    def __post_init__(self):
        if not isinstance(self.items, tuple):
            object.__setattr__(self, 'items', tuple(self.items))

    @cached_property
    def info(self):
        today = date.today()
        info = {}
        for i in sorted(self.items, key=lambda x: x.id):
            info[i.id] = dict(
                antiquity=(today - i.releaseDate).days,
                gamepass=i.gamepass,
                price=i.price,
                rate=i.rate,
                reviews=i.reviews,
                trial=i.trial,
                discount=i.discount,
                tags=i.tags
            )
        return info

    @cached_property
    def antiques(self):
        ants = set(x['antiquity'] for x in self.info.values())
        ants = tuple(sorted(ants))
        arr = set({
            ants[0],
            ants[-1],
            31,
            31*5,
            365
        })
        i = 1
        while i < len(ants):
            arr.add(ants[i])
            i = i * 2
        arr = sorted(arr)
        return tuple(arr)

    @cached_property
    def discounts(self):
        arr = set(floor(x['discount']) for x in self.info.values())
        arr = tuple(sorted(arr))
        return tuple(arr)

    @cached_property
    def tags(self):
        tags = set()
        for i in self.items:
            tags = tags.union(i.tags)
        tags = sorted(tags - set({'GamePass', 'Free'}))
        return tuple(tags)

    @cached_property
    def mx(self):
        return dict(
            precio=ceil(max([i.price for i in self.items])),
            reviews=ceil(max([i.reviews for i in self.items])),
            rate=ceil(max([i.rate for i in self.items])),
            discount=ceil(max([i.discount for i in self.items]))
        )

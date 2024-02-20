import re
from os.path import isfile
from functools import cached_property, cache
from typing import Union, Tuple, Dict, Set
from math import ceil
from dataclasses import dataclass
from datetime import date
import json
from math import floor
from .endpoint import EndPointProduct, EndPointProductPreloadState, EndPointActions, EndPointReviews
from .api import Api
from .util import dict_walk
import logging

logger = logging.getLogger(__name__)

YEAR = date.today().year+1
re_compras = re.compile(r"\bcompras\b", re.IGNORECASE)
re_date = re.compile(r"^\d{4}-\d{2}-\d{2}.*")
re_sp = re.compile(r"\s+")


def _trim(s: str):
    if s is None:
        return None
    s = s.strip()
    if len(s) == 0:
        return None
    return s

@cache
def collection():
    api = Api()
    data: Dict[str, Tuple[str]] = {}
    for id in api.get_ids():
        collections = set()
        for k, v in api.get_dict_catalog().items():
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
        self.extra_tags: Set[str] = set()
        self.demo_of = None

    @cached_property
    def collections(self):
        return collection().get(self.id, tuple())

    @cached_property
    def i(self):
        return EndPointProduct(self.id).json()

    @cached_property
    def productActions(self):
        return EndPointActions(self.id).json() or {"productActions": []}

    @cached_property
    def preload_state(self):
        return EndPointProductPreloadState(self.id).json()

    @cached_property
    def reviewsInfo(self):
        js = EndPointReviews(self.id).json()
        if js is None:
            return None
        if 'ratingsSummary' in js:
            return js['ratingsSummary']
        if js.get('totalReviews') == 0:
            return {
                "totalRatingsCount": 0
            }
        logger.critical(self.id+" revies bad format "+str(js))
        return None

    @cached_property
    def price(self) -> float:
        return self.i["DisplaySkuAvailabilities"][0]["Availabilities"][0]["OrderManagementData"]["Price"]["ListPrice"]

    @cached_property
    def int_price(self) -> int:
        if self.price > 0 and self.price <= 1:
            return 1
        if self.price < 0 and self.price >= -1:
            return -1
        return int(round(self.price))

    @cached_property
    def summary(self) -> dict:
        obj = dict_walk(self.preload_state, 'products/productSummaries/' + self.id)
        if not isinstance(obj, dict):
            return None
        return obj

    @cached_property
    def discount(self) -> float:
        obj = dict_walk(self.summary, 'specificPrices/purchaseable')
        if obj is None:
            return 0
        if not isinstance(obj, list) or len(obj) == 0 or not isinstance(obj[0], dict):
            return 0
        d = obj[0].get('discountPercentage') or 0
        return d

    @property
    def rate(self) -> float:
        averageRating = (self.reviewsInfo or {}).get('averageRating')
        if averageRating is None:
            averageRating = self.i["MarketProperties"][0]["UsageData"][-1]["AverageRating"]
        return averageRating

    @property
    def reviews(self) -> int:
        return self.reviewsInfo.get('totalRatingsCount')

    @cached_property
    def title(self) -> str:
        title: str = self.i["LocalizedProperties"][0]["ProductTitle"]
        title = re_sp.sub(" ", title).strip()
        title = title.replace("—", "-")
        title = title.replace(" ®", "®")
        return title

    @cached_property
    def relatedProducts(self):
        relatedProducts = self.i["LocalizedProperties"][0]["RelatedProducts"]
        return relatedProducts

    @cached_property
    def shortTitle(self) -> str:
        return _trim(self.i["LocalizedProperties"][0]["ShortTitle"])

    @cached_property
    def productDescription(self) -> str:
        return _trim(self.i["LocalizedProperties"][0]["ProductDescription"])

    @cached_property
    def url(self) -> str:
        return "https://www.xbox.com/es-es/games/store/a/"+self.id

    @cached_property
    def productType(self) -> str:
        return self.i["ProductType"]

    @cached_property
    def isGame(self) -> bool:
        if self.i is None:
            return False
        return self.productType == 'Game'

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
        obj = dict_walk(self.summary, 'legalNotices')
        if obj is None:
            return tuple()
        return tuple(obj)

    @property
    def interactiveDescriptions(self) -> tuple[str]:
        obj = dict_walk(self.summary, 'contentRating/interactiveDescriptions')
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
        return len(self.compras) > 0 and self.price == 0

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
    def spanish(self) -> tuple[str]:
        spa = {
            'audio': None,
            'subtitles': None,
        }
        obj = dict_walk(self.summary, 'languagesSupported')
        if not isinstance(obj, dict) or len(obj) == 0:
            return spa
        hasAudio = False
        hasSubti = False
        es = {}
        for k, v in obj.items():
            hasAudio = hasAudio or v['isAudioSupported']
            hasSubti = hasSubti or v['areSubtitlesSupported']
            if k.startswith("es-"):
                es = {**es, **{a: b for a, b in v.items() if b is True}}
        if hasAudio:
            spa['audio'] = es.get('isAudioSupported') is True
        if hasSubti:
            spa['subtitles'] = es.get('areSubtitlesSupported') is True
        return spa

    @cached_property
    def categories(self) -> tuple[str]:
        return tuple(self.i['Properties']['Categories'] or [])

    @property
    def gamepass(self) -> bool:
        for c in self.collections:
            if c in ('GamePass', 'EAPlay', 'Ubisoft', 'Bethesda'):
                return True
            if c.startswith("IncludedInSubscription"):
                return True
        return False

    @property
    def bundle(self) -> bool:
        return self.i["DisplaySkuAvailabilities"][0]["Sku"]['Properties']['IsBundle']

    @property
    def preorder(self) -> bool:
        if self.onlyGamepass:
            return False
        return self.i["DisplaySkuAvailabilities"][0]["Sku"]['Properties']['IsPreOrder']

    @property
    def demo(self) -> bool:
        if self.price == 0 and "Demo Version" in self.title:
            return True
        if self.demo_of is not None:
            return True
        return self.i['Properties'].get('IsDemo') is True

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

    @cached_property
    def availableOn(self):
        obj = dict_walk(self.summary, 'availableOn')
        if obj is None:
            return tuple()
        return tuple(obj)

    @cached_property
    def primary(self):
        obj = dict_walk(self.i, 'DisplaySkuAvailabilities/0/Sku/Properties/BundledSkus')
        if not isinstance(obj, list):
            return None
        for i in obj:
            if i.get('IsPrimary') is True:
                return i['BigId']

    @property
    def tags(self) -> tuple[str]:
        tags = set(self.extra_tags)
        isEs = (self.spanish['audio'], self.spanish['subtitles'])
        if self.spanish['audio'] is True:
            tags.add("Doblado")
        if self.spanish['subtitles'] is True:
            tags.add("Subtitulado")
        if False in isEs and True not in isEs:
            tags.add("FaltaEspañol")
        if self.spanish['audio'] is False:
            tags.add("FaltaDoblaje")
        if self.spanish['subtitles'] is False:
            tags.add("FaltanSubtitulos")
        if self.tragaperras:
            tags.add("Tragaperras")
        if self.compras:
            tags.add("Compras")
        if self.bundle:
            tags.add("Bundle")
        if self.preorder:
            tags.add("PreOrder")
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
            tags.add(x)
        for x in self.attributes:
            if x.endswith("fps"):
                continue
            if x in ("Capability4k", 'CapabilityHDR', 'DolbyAtmos', 'SpatialSound', 'XblClubs', 'XblAchievements', 'XblPresence', 'XblCloudSaves', 'XboxLive', 'DTSX', 'RayTracing'):
                continue
            if x in ('XblCrossPlatformCoop', 'XblCrossPlatformMultiPlayer', 'XboxLiveCrossGenMP'):
                x = 'CrossPlatform'
            if x in ('XblOnlineMultiPlayer', 'XblOnlineCoop'):
                x = 'OnlineMultiPlayer'
            if x in ('XblLocalMultiPlayer', 'XblLocalCoop', 'SharedSplitScreen'):
                x = 'LocalMultiPlayer'
            # if x == 'SharedSplitScreen':
            #    x = 'SplitScreen'
            tags.add(x)
        tags = sorted(tags)
        return tuple(tags)

    @cache
    def get_bundle(self) -> Tuple[str]:
        obj = dict_walk(self.preload_state, f'channels/channelsData/INTHISBUNDLE_{self.id}/data/products')
        if obj is None:
            return tuple()
        return tuple([i['productId'] for i in obj])


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
                price=i.int_price,
                rate=i.rate,
                reviews=i.reviews,
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

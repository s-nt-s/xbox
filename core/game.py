import re
from os.path import isfile
from functools import cached_property, cache
from typing import Union, Tuple, Dict, Set, NamedTuple, List
from math import ceil
from dataclasses import dataclass
from datetime import date
import json
from math import floor
from .endpoint import EndPointProduct, EndPointProductPreloadState, EndPointActions, EndPointReviews
from .api import Api
from .util import dict_walk, trim
import logging
from .cache import Cache
from .igdb import IGDB, IGDBMsgException

logger = logging.getLogger(__name__)

YEAR = date.today().year+1
re_compras = re.compile(r"\bcompras\b", re.IGNORECASE)
re_date = re.compile(r"^\d{4}-\d{2}-\d{2}.*")
re_sp = re.compile(r"\s+")


class GameBasic(NamedTuple):
    title: str
    price: float
    discount: float
    url: str
    img: str


class OverwriteWith(Cache):
    def __init__(self, file: str, *args, **kwargs):
        super().__init__(file, *args, kwself="slf", **kwargs)

    def parse_file_name(self, *args, slf: "Game" = None, **kargv):
        return self.file.format(id=slf.id)

    def save(self, *args, **kwargs):
        return None


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

    def __eq__(self, other):
        return isinstance(other, Game) and self.id == other.id

    def __hash__(self):
        return hash(self.id)

    @staticmethod
    @cache
    def get(id: str):
        return Game(id)

    @cached_property
    def collections(self):
        return collection().get(self.id, tuple())

    @cached_property
    def i(self):
        return EndPointProduct(self.id).json()

    @cached_property
    def productActions(self):
        obj = EndPointActions(self.id).json()
        if isinstance(obj, dict):
            return obj

    @cached_property
    def preload_state(self):
        obj = EndPointProductPreloadState(self.id).json()
        if isinstance(obj, dict):
            return obj

    @cached_property
    def reviewsInfo(self):
        obj = EndPointReviews(self.id).json()
        if not isinstance(obj, dict):
            logger.critical(self.id+" reviews empty "+str(obj))
            return None
        if 'ratingsSummary' in obj:
            return obj['ratingsSummary']
        rating: List[Union[int, float]] = []
        for r in (obj.get('reviews') or []):
            if isinstance(r, dict) and isinstance(r.get('rating'), (int, float)):
                rating.append(r.get('rating'))
        if len(rating):
            return {
                'averageRating': sum(rating)/len(rating),
                "totalRatingsCount": len(rating)
            }
        if obj.get('totalReviews') == 0:
            return {
                'averageRating': 0,
                "totalRatingsCount": 0
            }
        logger.critical(self.id+" reviews bad format "+str(obj))
        return None

    @cached_property
    def price(self) -> float:
        return dict_walk(
            self.i,
            'DisplaySkuAvailabilities/0/Availabilities/0/OrderManagementData/Price/ListPrice',
            instanceof=float
        )

    @cached_property
    def int_price(self) -> int:
        if self.price > 0 and self.price <= 1:
            return 1
        if self.price < 0 and self.price >= -1:
            return -1
        return int(round(self.price))

    @cached_property
    def summary(self) -> dict:
        return dict_walk(
            self.preload_state,
            'products/productSummaries/' + self.id
        )

    @cached_property
    def discount(self) -> float:
        obj = dict_walk(self.summary, 'specificPrices/purchaseable')
        if obj is None:
            return 0
        if not isinstance(obj, list) or len(obj) == 0 or not isinstance(obj[0], dict):
            return 0
        d = obj[0].get('discountPercentage') or 0
        return d

    @cached_property
    def usage_data(self):
        ud = self.i["MarketProperties"][0]["UsageData"][-1]
        for g in map(Game.get, self.decendents_id):
            if g.isGame and g.usage_data['RatingCount'] > ud["RatingCount"]:
                ud = g.usage_data
        ud['RatingCount'] = int(ud['RatingCount'])
        if int(ud['AverageRating']) == ud['AverageRating']:
            ud['AverageRating'] = int(ud['AverageRating'])
        return ud

    @cache
    def __rate__review(self):
        rAverageRating = self.reviewsInfo['averageRating']
        rTotalRatingsCount = self.reviewsInfo['totalRatingsCount']
        uAverageRating = self.usage_data["AverageRating"]
        uRatingCount = self.usage_data["RatingCount"]
        if uRatingCount == rTotalRatingsCount:
            return dict(
                rate=max(uAverageRating, rAverageRating),
                reviews=uRatingCount
            )
        if uRatingCount > rTotalRatingsCount:
            return dict(
                rate=uAverageRating,
                reviews=uRatingCount
            )
        logger.warning(f"{self.id} {rTotalRatingsCount} reviews vs {uRatingCount} reviews decendents_id={self.decendents_id}")
        return dict(
            rate=rAverageRating,
            reviews=rTotalRatingsCount
        )
        averageRating = (self.reviewsInfo or {}).get('averageRating')
        if averageRating is not None:
            return dict(rate=averageRating, reviews=self.reviewsInfo['totalRatingsCount'])
        usage = self.i["MarketProperties"][0]["UsageData"][-1]
        return dict(
            rate=usage["AverageRating"],
            reviews=usage["RatingCount"]
        )

    @cached_property
    def rate(self) -> float:
        return self.__rate__review()['rate']

    @cached_property
    def reviews(self) -> int:
        return self.__rate__review()['reviews']

    @cached_property
    def title(self) -> str:
        title: str = dict_walk(
            self.i,
            'LocalizedProperties/0/ProductTitle',
            instanceof=str
        )
        title = re.sub(r"—|–™", "-", title)
        title = re.sub(r"®|™", "", title)
        title = re_sp.sub(" ", title).strip()
        return title

    @cached_property
    def productGroup(self) -> str:
        return trim(dict_walk(self.i, 'Properties/ProductGroupName'))

    @cached_property
    def developer(self) -> str:
        return trim(dict_walk(self.i, 'LocalizedProperties/0/DeveloperName'))

    @cached_property
    def publisher(self) -> str:
        return trim(dict_walk(self.i, 'LocalizedProperties/0/PublisherName'))

    @cached_property
    def shortTitle(self) -> str:
        return trim(dict_walk(self.i, 'LocalizedProperties/0/ShortTitle'))

    @cached_property
    def productDescription(self) -> str:
        return trim(dict_walk(self.i, 'LocalizedProperties/0/ProductDescription'))

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
        if self.productType != 'Game':
            return False
        return True

    @cached_property
    def _isUseless(self) -> bool:
        if self.i is None:
            return True
        if self.productType in ("AvatarItem", "Application"):
            return True
        return False

    @cached_property
    def isUseless(self) -> bool:
        if self._isUseless:
            return True
        if self.summary is None:
            return True
        if self.productActions is None:
            return True
        if not self.isXboxSeries:
            return True
        return False

    @cached_property
    def isXboxSeries(self) -> bool:
        return 'XboxSeriesX' in self.availableOn

    @cached_property
    def isXboxGame(self) -> bool:
        return self.isGame and self.isXboxSeries

    @cached_property
    def media(self) -> tuple[Dict]:
        def _uri(i: Dict):
            i['Uri'] = "https:"+i['Uri']
            return i
        imgs = dict_walk(self.i, 'LocalizedProperties/0/Images')
        if not imgs:
            return tuple()
        return tuple(map(_uri, imgs))

    @cached_property
    def imgs(self) -> tuple[str]:
        return tuple([x["Uri"] for x in self.media])

    @cached_property
    def poster(self) -> str:
        if len(self.media) == 0:
            return None
        for i in self.media:
            if i['ImagePurpose'] == 'Poster':
                return i["Uri"]
        return self.media[0]["Uri"]

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

    @cached_property
    def actions(self) -> tuple[str]:
        act = set()
        for x in self.productActions["productActions"]:
            if x['productId'] != self.id:
                continue
            for a in x['productActions']:
                if a['actionArguments'].get('ProductId', self.id) != self.id:
                    continue
                act.add(a['actionType'])
            for aa in x['skuActionsBySkuId'].values():
                for a in aa:
                    if a['actionArguments'].get('ProductId', self.id) != self.id:
                        continue
                    act.add(a['actionType'])
        act = tuple(sorted(act))
        return act

    @cached_property
    def legalNotices(self) -> tuple[str]:
        obj = dict_walk(self.summary, 'legalNotices')
        if obj is None:
            return tuple()
        return tuple(obj)

    @cached_property
    def interactiveDescriptions(self) -> tuple[str]:
        obj = dict_walk(self.summary, 'contentRating/interactiveDescriptions')
        if obj is None:
            return tuple()
        return tuple(obj)

    @cached_property
    def compras(self) -> tuple[str]:
        cmp = set()
        for x in self.interactiveDescriptions:
            if re_compras.search(x):
                cmp.add(x)
        return tuple(sorted(cmp))

    @cached_property
    def isSlotMachine(self) -> bool:
        return len(self.compras) > 0 and self.price == 0

    @cached_property
    def requiresGame(self) -> bool:
        return 'DlcRequiresGame' in self.legalNotices

    @cached_property
    def notSoldSeparately(self) -> bool:
        return 'NotSoldSeparately' in self.actions

    @cached_property
    def notAvailable(self) -> bool:
        return 'Acquisition' not in self.actions

    @cached_property
    def onlyGamepass(self) -> bool:
        return self.isInGamepass and self.notSoldSeparately

    @cached_property
    @OverwriteWith("fix/spanish/{id}.json")
    def spanish(self) -> Dict[str, bool]:
        spa = self.__get_spanish()
        if spa is not None and (spa['interface'], spa['subtitles']) != (None, None):
            return spa
        try:
            spa2 = IGDB.get().get_spanish(self.id)
        except IGDBMsgException as e:
            logger.warning("IGDB: "+str(e))
            return None
        if None in (spa, spa2):
            return (spa or spa2)
        if spa['audio'] is not None:
            spa2['audio'] = spa['audio']
        return spa2

    def __get_spanish(self) -> tuple[str]:
        obj = dict_walk(self.summary, 'languagesSupported')
        if not isinstance(obj, dict) or len(obj) == 0:
            return self.__find_spanish()
        has = set()
        spa = set()
        for lang, v in obj.items():
            for field, value in v.items():
                if value is True:
                    has.add(field)
                    if lang.startswith("es-"):
                        spa.add(field)

        def isSpa(f: str):
            if f not in has:
                return None
            return f in spa

        return dict(
            audio=isSpa('isAudioSupported'),
            subtitles=isSpa('areSubtitlesSupported'),
            interface=isSpa('isInterfaceSupported')
        )

    def __find_spanish(self):
        if (self.developer or "").startswith("Rockstar"):
            return dict(
                audio=False,
                subtitles=True,
                interface=True
            )
        alt = {}
        for g in map(Game.get, self.bundle):
            if g.id != self.id and len(g.bundle) == 0 and g.isGame and g.spanish is not None:
                k = tuple(g.spanish.items())
                alt[k] = alt.get(k, 0) + 1
        if len(alt) == 0:
            return None

        def _key(kvc):
            (kv, c) = kvc
            arr = [-c]
            for k, v in kv:
                arr.append(k)
                if v is None:
                    arr.append(1)
                else:
                    arr.append(-int(v))
            return tuple(arr)
        alt = sorted(
            alt.items(),
            key=_key
        )
        spa = dict(alt[0][0])
        return spa

    @cached_property
    def categories(self) -> tuple[str]:
        return tuple(self.i['Properties']['Categories'] or [])

    @cached_property
    def isInGamepass(self) -> bool:
        for c in self.collections:
            if c in ('GamePass', 'EAPlay', 'Ubisoft', 'Bethesda'):
                return True
            if c.startswith("IncludedInSubscription"):
                return True
        return False

    @cached_property
    def isBundle(self) -> bool:
        return dict_walk(
            self.i,
            'DisplaySkuAvailabilities/0/Sku/Properties/IsBundle',
            instanceof=bool
        )

    @cached_property
    def isPreorder(self) -> bool:
        if self.onlyGamepass:
            return False
        if self.notSoldSeparately:
            return False
        return dict_walk(
            self.i,
            'DisplaySkuAvailabilities/0/Sku/Properties/IsPreOrder',
            instanceof=bool
        )

    @cached_property
    def isDemo(self) -> bool:
        if self.price == 0:
            if "Demo Version" in self.title:
                return True
            if "Free Trial" in self.title:
                return True
            if self.isPreview:
                return True
        if self.isPreview and self.isTrial:
            return True
        if self.demo_of is not None:
            return True
        return self.i['Properties'].get('IsDemo') is True

    @cached_property
    def isPreview(self) -> bool:
        for w in (
            "Este juego está en construcción",
            "Este juego es un trabajo en curso",
            "Puede o no, cambiar con el tiempo o lanzarse como producto final"
        ):
            if w in self.productDescription:
                return True

        for w in ("(Versión preliminar del juego)", "(Game Preview)"):
            if w in self.title:
                return True
        return False

    @cached_property
    def isTrial(self) -> bool:
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
    def tags(self) -> tuple[str]:
        no_heredar = ("Tragaperras", )
        tags = set()
        for g in map(Game.get, self.content_id):
            if g.id != self.id:
                tags = tags.union(g.tags).difference(no_heredar)
        tags = tags.union(self.extra_tags)
        if self.isSlotMachine:
            tags.add("Tragaperras")
        if self.compras:
            tags.add("Compras")
        if self.isBundle:
            tags.add("Bundle")
        if self.isPreorder:
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
            if x in ('XblCrossPlatformCoop', 'XblCrossPlatformMultiPlayer'):
                x = 'CrossPlatform'
            if x in ('XblOnlineMultiPlayer', 'XblOnlineCoop', 'XboxLiveCrossGenMP'):
                x = 'OnlineMultiPlayer'
            if x in ('XblLocalMultiPlayer', 'XblLocalCoop', 'SharedSplitScreen'):
                x = 'LocalMultiPlayer'
            # if x == 'SharedSplitScreen':
            #    x = 'SplitScreen'
            tags.add(x)
        return tuple(sorted(tags))

    @cached_property
    def full_tags(self):
        tags = list(self.tags)
        if self.audio_subtitles is not None:
            au_su = (self.audio_subtitles['subtitles'], self.audio_subtitles['audio'])
            if self.audio_subtitles['subtitles']:
                tags.insert(0, "Subtitulado")
            if self.audio_subtitles['audio']:
                tags.insert(0, "Doblado")
            if au_su == (None, None):
                tags.insert(0, "Mudo")
            elif True not in au_su:
                tags.insert(0, "SinTraducir")
        return tuple(tags)

    @cached_property
    def audio_subtitles(self):
        if self.spanish is None:
            return None
        spa = dict(self.spanish)
        if spa['subtitles'] is None:
            spa['subtitles'] = spa['interface']
        del spa['interface']
        return spa

    @cached_property
    def content_id(self):
        if self.isUseless:
            return tuple()
        if len(self.bundle) == 0:
            return (self.id, )
        ids = set()
        for i in map(Game.get, self.bundle):
            ids = ids.union(i.content_id)
        if self.id in ids:
            ids.remove(self.id)
        return tuple(sorted(ids))

    @cached_property
    def decendents_id(self):
        ids = list(self.content_id)
        if self.id in ids:
            ids.remove(self.id)
        return tuple(ids)

    @cached_property
    def bundle(self) -> Tuple[str]:
        obj = dict_walk(
            self.preload_state,
            f'channels/channelsData/INTHISBUNDLE_{self.id}/data/products'
        )
        if obj is None:
            return tuple()
        ids = set([i['productId'] for i in obj])
        ids = set(map(trim, ids))
        for i in (self.id, None):
            if i in ids:
                ids.remove(i)
        return tuple(sorted(ids))

    @cached_property
    def bundled_in(self) -> Tuple[str]:
        def _find(path: str):
            return dict_walk(self.preload_state, path) or []
        aux = set()
        for o in _find(f'channels/channelsData/BUNDLESBYSEED_{self.id}/data/products'):
            aux.add(o['productId'])
        for o in _find(f'channels/channelsData/COMPAREEDITIONS_{self.id}/data/products'):
            aux.add(o['productId'])
        for o in _find(f'products/productSummaries/{self.id}/bundlesBySeed'):
            aux.add(o)
        aux = set(map(trim, aux))
        for i in (self.id, None):
            if i in aux:
                aux.remove(i)
        ids = set()
        for i in map(Game.get, aux):
            if self.id in i.bundle:
                ids.add(i.id)
        return tuple(sorted(ids))


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
                tags=i.tags,
                spa=i.audio_subtitles
            )
        return info

    @cached_property
    def everything_has_subtitles(self):
        for i in self.items:
            if i.audio_subtitles is None:
                continue
            if i.audio_subtitles['subtitles'] is None:
                return False
        return True

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
        return tuple(sorted(tags))

    @cached_property
    def mx(self):
        return dict(
            price=ceil(max([i.price for i in self.items])),
            reviews=ceil(max([i.reviews for i in self.items])),
            rate=ceil(max([i.rate for i in self.items])),
            discount=ceil(max([i.discount for i in self.items]))
        )

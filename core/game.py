import inspect
import re
from os.path import isfile
from functools import cached_property
from typing import Union
from math import ceil
from dataclasses import dataclass
from datetime import date
import json
from .thumbnail import mk_thumbnail

MSCV = 'MS-CV=DGU1mcuYo0WMMp+F.1'
YEAR = date.today().year+1
re_compras = re.compile(r"\bcompras\b", re.IGNORECASE)
re_date = re.compile(r"^\d{4}-\d{2}-\d{2}.*")


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
    def __init__(self, i: Union[dict, str], collections: tuple[str]):
        if isinstance(i, str):
            i = read_json("rec/gm/"+i+".json")
        self.i = i
        self.collections = collections
        jfile = self.i['ProductId']+".json"
        self.productActions = read_json("rec/ac/"+jfile) or {"productActions": []}
        self.preload_state = read_json("rec/ps/"+jfile)
        self.reviewsInfo = read_json("rec/rw/"+jfile) or {}

    @cached_property
    def id(self):
        return self.i['ProductId']

    @cached_property
    def price(self):
        return self.i["DisplaySkuAvailabilities"][0]["Availabilities"][0]["OrderManagementData"]["Price"]["ListPrice"]

    @property
    def rate(self):
        averageRating = self.reviewsInfo.get('averageRating')
        if averageRating is not None:
            return averageRating
        AverageRating = self.i["MarketProperties"][0]["UsageData"][-1]["AverageRating"]
        return AverageRating

    @property
    def reviews(self):
        return self.reviewsInfo.get('totalRatingsCount')

    @cached_property
    def title(self):
        return self.i["LocalizedProperties"][0]["ProductTitle"]

    @cached_property
    def url(self):
        return "https://www.xbox.com/es-es/games/store/a/"+self.i['ProductId']

    @cached_property
    def js(self):
        return "https://displaycatalog.mp.microsoft.com/v7.0/products?"+MSCV+"&market=ES&languages=es-es&bigIds="+self.i['ProductId']

    @cached_property
    def imgs(self):
        return ["http:"+x["Uri"] for x in self.i["LocalizedProperties"][0]["Images"]]

    @cached_property
    def poster(self):
        for i in self.i["LocalizedProperties"][0]["Images"]:
            if i['ImagePurpose'] == 'Poster':
                return "http:"+i["Uri"]
        return self.imgs[0]

    @cached_property
    def thumbnail(self):
        out = "docs/img/"+self.id+".jpg"
        if not isfile(out):
            mk_thumbnail(self.poster, out)
        return out.split("/", 1)[-1]

    @cached_property
    def attributes(self):
        att = set()
        for a in (self.i['Properties']['Attributes'] or []):
            if 'Xbox' in (a['ApplicablePlatforms'] or []) or a['Name'].startswith("Xb"):
                att.add(a['Name'])
        return tuple(sorted(att))

    @property
    def actions(self):
        act = set()
        for x in self.productActions["productActions"]:
            for a in x['productActions']:
                act.add(a['actionType'])
        act = tuple(sorted(act))
        return act

    @property
    def legalNotices(self):
        if self.preload_state is None:
            return []
        obj = dict(self.preload_state)
        for k in ('core2', 'products', 'productSummaries' , self.id, 'legalNotices'):
            obj = obj.get(k)
            if obj is None:
                return []
        if obj is None:
            return []
        return obj

    @property
    def interactiveDescriptions(self):
        if self.preload_state is None:
            return []
        obj = dict(self.preload_state)
        for k in ('core2', 'products', 'productSummaries' , self.id, 'contentRating', 'interactiveDescriptions'):
            obj = obj.get(k)
            if obj is None:
                return []
        if obj is None:
            return []
        return obj

    @property
    def compras(self):
        cmp = set()
        for x in self.interactiveDescriptions:
            if re_compras.search(x):
                cmp.add(x)
        return tuple(sorted(cmp))

    @property
    def tragaperras(self):
        return len(self.compras)>0 and 'TopFree' in self.collections

    @property
    def requiresGame(self):
        return 'DlcRequiresGame' in self.legalNotices

    @property
    def notSoldSeparately(self):
        return 'NotSoldSeparately' in self.actions
    
    @property
    def onlyGamepass(self):
        return self.gamepass and self.notSoldSeparately

    @cached_property
    def langs(self):
        def find_lang(lng, arr):
            for l in arr:
                l = l.lower()
                if l == lng or l.startswith(lng+'-'):
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
    def categories(self):
        return (self.i['Properties']['Categories'] or [])

    @property
    def gamepass(self):
        return 'GamePass' in self.collections or 'EAPlay' in self.collections

    @property
    def trial(self):
        return 'Trial' in self.actions
    
    @cached_property
    def releaseDate(self):
        dts = set()
        for k, v in iter_kv(self.i):
            if "Date" in k and isinstance(v, str) and re_date.match(v):
                dts.add(tuple(map(int, v[:10].split("-"))))
        for dt in sorted(dts):
            dt = date(*dt)
            if dt.year > 1951 and dt.year < YEAR:
                return dt

    @property
    def tags(self):
        tags = []
        if self.onlyGamepass:
            tags.append("SoloGamePass")
        if self.tragaperras:
            tags.append("Tragaperras")
        if self.compras:
            tags.append("Compras")
        for x in self.categories:
            if x in ('Other', ):
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
            if x in ('Word', 'Tools'):
                continue
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
        tags = sorted(set(tags), key=lambda x:tags.index(x))
        return tuple(tags)

    def to_dict(self):
        dt = {}
        for k, v in inspect.getmembers(self):
            if k[0]!='_' and isinstance(v, (str, int, float, tuple)):
                dt[k]=v
        return dt

    def to_js(self):
        ks = ('gamepass', 'id', 'price', 'rate', 'reviews', 'tags', 'trial')
        dt = {}
        for k, v in inspect.getmembers(self):
            if k in ks and isinstance(v, (str, int, float, tuple)):
                dt[k]=v
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
                tags=i.tags
            )
        return info

    @cached_property
    def antiques(self):
        ants = set(x['antiquity'] for x in self.info.values())
        mn = min(ants)
        mx = max(ants)
        arr = []
        if mn < 2:
            arr.append(1)
        elif mn % 2 == 0:
            arr.append(mn)
        else:
            arr.append(mn-1)
        while arr[-1] < mx:
            arr.append(arr[-1]*2)
        arr[0] = mn
        arr[-1] = mx
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
            rate=ceil(max([i.rate for i in self.items]))
        )

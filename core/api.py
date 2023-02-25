from functools import lru_cache

import requests
from munch import Munch
from simplejson.errors import JSONDecodeError

from .decorators import Cache
from .filemanager import FM
from .web import get_session
import json
import inspect

'''
https://www.reddit.com/r/XboxGamePass/comments/jt214y/public_api_for_fetching_the_list_of_game_pass/

https://reco-public.rec.mp.microsoft.com/channels/Reco/v8.0/lists/collection/XboxIndieGames?itemTypes=Game&DeviceFamily=Windows.Xbox&market=es&count=200&skipItems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/TopFree?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/TopPaid?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/New?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/BestRated?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/ComingSoon?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/Deal?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/TopFree?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/MostPlayed?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000&skipitems=0
'''

MSCV = 'MS-CV=DGU1mcuYo0WMMp+F.1'

ss = None


def myex(e, msg):
    largs = list(e.args)
    if len(largs) == 1 and isinstance(largs, str):
        largs[0] = largs[0]+' '+msg
    else:
        largs.append(msg)
    e.args = tuple(largs)
    return e


def chunks(lst, n):
    arr = []
    for i in lst:
        arr.append(i)
        if len(arr) == n:
            yield arr
            arr = []
    if arr:
        yield arr


def get_js(url):
    global ss
    if ss is None:
        ss = get_session("https://www.xbox.com/es-ES/games/free-to-play")
    rq = ss._get(url)
    try:
        return rq.json()
    except JSONDecodeError as e:
        text = rq.text.strip()
        if len(text) == 0:
            raise myex(e, 'becouse request.get("%s") is empty' % (url))
        raise myex(e, 'in request.get("%s") = %s' % (url, rq.text))


class Api:
    COLS = ("XboxIndieGames", "TopFree", "TopPaid", "New",
            "BestRated", "ComingSoon", "Deal", "MostPlayed")

    def __init__(self):
        pass

    def get_list(self, url):
        js = get_js(url)
        rt = {i['Id']: i for i in js['Items']}
        tt = js['PagingInfo']['TotalItems']
        while len(rt) < tt:
            js = get_js(url+"&skipitems="+str(len(rt)))
            for i in js['Items']:
                rt[i['Id']] = i
        rt = sorted(rt.values(), key=lambda x: x['Id'])
        return rt

    @Cache("rec/{}.json")
    def get_collection(self, collection):
        if collection == "XboxIndieGames":
            return self.get_list("https://reco-public.rec.mp.microsoft.com/channels/Reco/v8.0/lists/collection/XboxIndieGames?itemTypes=Game&DeviceFamily=Windows.Xbox&market=es&count=200")
        return self.get_list("https://reco-public.rec.mp.microsoft.com/channels/Reco/V8.0/Lists/Computed/"+collection+"?Market=es&Language=es&ItemTypes=Game&deviceFamily=Windows.Xbox&count=2000")

    @Cache("rec/{}.json")
    def get_gamepass(self, id):
        return get_js("https://catalog.gamepass.com/sigls/v2?language=es-es&market=ES&id="+id)

    @lru_cache(maxsize=None)
    def get_catalog(self):
        def to_tup(id, gen):
            return tuple(sorted(set(i[id] for i in gen)))
        gamepass = self.get_gamepass("f6f1f99f-9b49-4ccd-b3bf-4d9767a77f5e")
        eaplay = self.get_gamepass("b8900d09-a491-44cc-916e-32b5acae621b")
        rt = Munch(
            GamePass=to_tup('id', gamepass[1:]),
            EAPlay=to_tup('id', eaplay[1:])
        )
        for c in Api.COLS:
            rt[c] = to_tup('Id', self.get_collection(c))
        return rt

    def get_all(self):
        rt = {}
        for col in Api.COLS:
            for i in self.get_collection(col):
                rt[i['Id']] = i
        rt = sorted(rt.values(), key=lambda x: x['Id'])
        return rt

    @Cache("rec/gm/{0}.json")
    def get_item(self, id, **kvargs):
        if "return_me" in kvargs:
            return kvargs['return_me']
        js = get_js("https://displaycatalog.mp.microsoft.com/v7.0/products?" +
                    MSCV+"&market=ES&languages=es-es&bigIds="+id)
        rt = js['Products']
        if len(rt) == 1:
            return rt[0]
        return None
    
    @Cache("rec/ps/{0}.json", maxOld=10)
    def get_preload_state(self, id, **kvargs):
        url = "https://www.xbox.com/es-es/games/store/a/"+id
        r = requests.get(url)
        for l in r.text.split("\n"):
            l = l.strip()
            if l.startswith("window.__PRELOADED_STATE__"):
                l = l.split("=", 1)[-1].strip().rstrip(";")
                j = json.loads(l)
                return j

    @Cache("rec/ac/{1}.json", maxOld=10)
    def get_actions(self, web, id, **kvargs):
        url = "https://www.xbox.com/es-es/games/store/a/"+id
        web.get(url)
        while True:
            if "Error response" in str(web.get_soup()):
                web.get(url)
            for r in web._driver.requests:
                if ("://emerald.xboxservices.com/xboxcomfd/productActions/"+id) not in r.path:
                    continue
                if r.response and r.response.body:
                    js = r.response.body
                    js = js.decode('utf-8')
                    js = js.strip()
                    js = json.loads(js)
                    return js
        return None

    def get_items(self, *ids):
        if len(ids)==0:
            ids = [i['Id'] for i in self.get_all()]
        ids = sorted(set(ids))
        rt = []
        for i, id in reversed(list(enumerate(ids))):
            item = self.get_item(id, return_me=None)
            if item is not None:
                rt.append(item)
                del ids[i]
        for cids in chunks(ids, 200):
            bigIds=",".join(cids)
            js = get_js("https://displaycatalog.mp.microsoft.com/v7.0/products?"+MSCV+"&market=ES&languages=es-es&bigIds="+bigIds)
            for i in js['Products']:
                self.get_item(i['ProductId'], return_me=i)
                rt.append(i)
        rt = sorted(rt, key=lambda x:x['ProductId'])
        gm = []
        for i in rt:
            i = Game(i)
            for k, v in self.get_catalog().items():
                if i.id in v:
                    i.collections.add(k)
            gm.append(i)
        return gm

class Game:
    def __init__(self, i):
        self.i = i
        self.collections = set()
        self.productActions = {"productActions":[]}
        self.preload_state = None

    @property
    def id(self):
        return self.i['ProductId']

    @property
    def price(self):
        return self.i["DisplaySkuAvailabilities"][0]["Availabilities"][0]["OrderManagementData"]["Price"]["ListPrice"]

    @property
    def rate(self):
        return self.i["MarketProperties"][0]["UsageData"][-1]["AverageRating"]

    @property
    def title(self):
        return self.i["LocalizedProperties"][0]["ProductTitle"]

    @property
    def url(self):
        return "https://www.xbox.com/es-es/games/store/a/"+self.i['ProductId']

    @property
    def js(self):
        return "https://displaycatalog.mp.microsoft.com/v7.0/products?"+MSCV+"&market=ES&languages=es-es&bigIds="+self.i['ProductId']

    @property
    def imgs(self):
        return ["http:"+x["Uri"] for x in self.i["LocalizedProperties"][0]["Images"]]

    @property
    def poster(self):
        for i in self.i["LocalizedProperties"][0]["Images"]:
            if i['ImagePurpose'] == 'Poster':
                return "http:"+i["Uri"]
        return self.imgs[0]

    @property
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
    def requiresGame(self):
        return 'DlcRequiresGame' in self.legalNotices

    @property
    def notSoldSeparately(self):
        return 'NotSoldSeparately' in self.actions
    
    @property
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

    @property
    def categories(self):
        return (self.i['Properties']['Categories'] or [])

    @property
    def gamepass(self):
        return 'GamePass' in self.collections or 'EAPlay' in self.collections

    @property
    def tags(self):
        tags = []
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

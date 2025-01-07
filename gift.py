from core.findwireresponse import FindWireResponse, WireResponse
from typing import Set
from core.filemanager import FM
from core.game import GameBasic
from core.api import Api
from core.game import Game
from core.web import Web, get_text
from core.util import dict_walk, trim
import re

MAX_PRICE = 1

games: Set[GameBasic] = set()


def to_num(s: str, default=None):
    if s is None:
        return default
    s = re.sub(r"[^\d\.\-\+,]", "", s).strip()
    if len(s) == 0:
        return default
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    f = float(s)
    i = int(f)
    if i == f:
        return i
    return f


w = Web()
r = w.json(f"https://catalog.gog.com/v1/catalog?limit=140&price=between%3A0%2C1{MAX_PRICE}&order=desc%3Atrending&discounted=eq%3Atrue&productType=in%3Agame%2Cpack&page=1&countryCode=ES&locale=en-US&currencyCode=EUR")
for i in dict_walk(r, 'products', instanceof=list):
    price = dict_walk(i, 'price/base', instanceof=str)
    discount = dict_walk(i, 'price/discount', instanceof=str)
    games.add(GameBasic(
        title=dict_walk(i, 'title', instanceof=str),
        price=to_num(price),
        discount=to_num(discount),
        url=dict_walk(i, 'storeLink', instanceof=str),
        img=dict_walk(i, 'coverVertical', instanceof=str)
    ))

w.get(f"https://store.steampowered.com/search/results?sort_by=Price_ASC&maxprice={MAX_PRICE}&category1=998&specials=1&ndl=1&snr=1_7_7_230_7")
for g in w.soup.select("#search_resultsRows > a"):
    games.add(GameBasic(
        title=get_text(g.select_one("span.title")),
        price=to_num(get_text(g.select_one("div.discount_original_price"))),
        discount=abs(to_num(get_text(g.select_one("div.discount_pct")), default=0)),
        url=g.attrs['href'].split("?")[0],
        img=g.select_one("img").attrs["src"]
    ))

r = FindWireResponse.find_response(
    "https://store.epicgames.com/es-ES/browse?sortBy=currentPrice&sortDir=ASC&priceTier=tierDiscouted&category=Game&count=40&start=0",
    path="https://store.epicgames.com/graphql?operationName=searchStoreQuery&variables=",
    browser="devchrome"
)


if isinstance(r, WireResponse):
    for e in dict_walk(r.body, 'data/Catalog/searchStore/elements', instanceof=list):
        originalPrice: int = dict_walk(e, 'price/totalPrice/originalPrice', instanceof=int)
        discountPrice: int = dict_walk(e, 'price/totalPrice/discountPrice', instanceof=int)
        decimals: int = dict_walk(e, 'price/totalPrice/currencyInfo/decimals', instanceof=int)
        price: float = originalPrice / pow(10, decimals)
        pageSlug: str = dict_walk(e, 'catalogNs/mappings/0/pageSlug', instanceof=str)
        imgs = {i['type']: i['url'] for i in e['keyImages']}
        games.add(GameBasic(
            title=dict_walk(e, 'title', instanceof=str),
            price=price,
            discount=0 if originalPrice == 0 else ((originalPrice-discountPrice)/originalPrice)*100,
            url="https://store.epicgames.com/es-ES/p/"+pageSlug,
            img=None if len(imgs) == 0 else (imgs.get('Thumbnail') or tuple(imgs.values())[0])
        ))

api = Api()
for i in list(map(Game.get, api.get_ids())):
    games.add(GameBasic(
        title=i.title,
        price=i.price,
        discount=i.discount,
        url=i.url,
        img=i.poster
    ))


def _asdict(g: GameBasic):
    if not isinstance(g.discount, (int, float)):
        return None
    if not isinstance(g.price, (int, float)):
        return None
    if g.price == 0:
        return None
    if g.discount != 100:
        return None
    d = g._asdict()
    for k, v in list(d.items()):
        if isinstance(v, str):
            d[k] = trim(v)
        elif isinstance(v, float):
            i = int(v)
            if i == v:
                d[k] = i
    return d


gift = [result for x in sorted(games) if (result := _asdict(x)) is not None]
FM.dump("out/gift.json", gift)

from core.findwireresponse import FindWireResponse, WireResponse
from typing import Set, Dict
from core.filemanager import FM
from core.game import GameBasic
from core.api import Api
from core.game import Game


games: Set[GameBasic] = set()


r = FindWireResponse.find_response(
    #"https://store.epicgames.com",
    "https://store.epicgames.com/es-ES/browse?sortBy=currentPrice&sortDir=ASC&priceTier=tierDiscouted&category=Game&count=40&start=0",
    path="https://store.epicgames.com/graphql?operationName=searchStoreQuery&variables=",
    browser="devchrome"
)


if isinstance(r, WireResponse):
    for e in r.body['data']['Catalog']['searchStore']['elements']:
        p: Dict = e['price']['totalPrice']
        originalPrice: int = p.get('originalPrice')
        discountPrice: int = p.get('discountPrice')
        if not isinstance(originalPrice, int) or not isinstance(discountPrice, int):
            continue
        if discountPrice != 0:
            continue
        if originalPrice == 0:
            continue
        price: float = p['originalPrice'] / pow(10, p['currencyInfo']['decimals'])
        pageSlug = e['catalogNs']['mappings'][0]['pageSlug']
        imgs = {i['type']: i['url'] for i in e['keyImages']}
        games.add(GameBasic(
            title=e['title'],
            price=price,
            discount=((originalPrice-discountPrice)/originalPrice)*100,
            url="https://store.epicgames.com/es-ES/p/"+pageSlug,
            img=None if len(imgs) == 0 else (imgs.get('Thumbnail') or tuple(imgs.values())[0])
        ))

api = Api()
for i in list(map(Game.get, api.get_ids())):
    if i.discount == 100:
        games.add(GameBasic(
            name=i.title,
            price=i.price,
            url=i.url,
            img=i.poster
        ))

FM.dump("out/gift.json", [g._asdict() for g in sorted(games)])

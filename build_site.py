#!/usr/bin/env python3

from core.api import Api
from core.j2 import Jnj2, to_value
from datetime import datetime
from core.game import Game, GameList
import filter.filter as gfilter
from core.search import URL_GAMES_BROWSER
from core.endpoint import EndPointCollection, EndPointProduct
from core.util import dict_add
from typing import List, Tuple, Dict, Set
from core.log import config_log

import argparse

parser = argparse.ArgumentParser(
    description='Lista juegos de xbox del gamepass o de menos de X€')
parser.add_argument("--precio", type=float, help='Precio máximo', default=9999)

args = parser.parse_args()

config_log("log/build_site.log")

api = Api()


def do_filter1(i: Game):
    if i.gamepass:
        return True
    if i.price <= args.precio:
        return True
    return False


def do_filter2(i: Game):
    if 'XboxSeriesX' not in i.availableOn:
        return False
    if not i.isGame:
        return False
    if i.notAvailable:
        return False
    if i.gamepass:
        return True
    if i.requiresGame:
        return False
    if i.notSoldSeparately:
        return False
    if i.preorder:
        return False
    # if 'Trial' in i.actions:
    #    return False
    return True


def get_games():
    ids = list(api.get_ids())
    games = list(map(Game, ids))
    for i in games:
        for b in i.get_bundle():
            if b not in ids:
                b = Game(b)
                if b.isGame:
                    games.append(b)
                    ids.append(b.id)
    return tuple(sorted(games, key=lambda g: g.id))


print("Obteniendo juegos", end="\r")
ALL_GAMES = {i.id: i for i in get_games()}
print("Obteniendo juegos:", len(ALL_GAMES))

print("Aplicando 1º filtro", end="\r")
items = list(filter(do_filter1, ALL_GAMES.values()))
print("Aplicando 1º filtro:", len(items))

print("Aplicando 2º filtro", end="\r")
items = list(filter(do_filter2, items))
print("Aplicando 2º filtro:", len(items))

print("Descartando complementos o bundle redundantes")

COMP: Dict[str, Set[str]] = {}
OLDR: Dict[str, Set[str]] = {}
items = {i.id: i for i in items}

for pid, cids in gfilter.is_chunk_of(items):
    cids = tuple([c for c in cids if c in items])
    if cids and pid in items:
        for cid in cids:
            gm = items[cid]
            if gm.price == 0:
                gm.demo_of = pid
            else:
                dict_add(COMP, pid, cid)
                del items[cid]

for pid, cids in gfilter.is_comp_of(items):
    cids = tuple([c for c in cids if c in items])
    if cids and pid in items:
        for cid in cids:
            dict_add(COMP, pid, cid)
            del items[cid]

for pid, cids in gfilter.is_older_version_of(items, all_games=ALL_GAMES.values()):
    cids = tuple([c for c in cids if c in items])
    if cids and pid in items:
        for cid in cids:
            dict_add(OLDR, pid, cid)
            del items[cid]

items = sorted(items.values(), key=lambda x: x.releaseDate, reverse=True)
print("Resultado final:", len(items))

print("Generando web")
glist = GameList(items)
now = datetime.now()


def game_info(gamelist: GameList):
    lst = dict(gamelist.info)
    for k, g in lst.items():
        g = dict(g)
        g['tags'] = tuple(map(to_value, g['tags']))
        lst[k] = g
    return lst


j = Jnj2("template/", "out/")
j.create_script(
    "info.js",
    ANTIQUITY=f"((new Date().setHours(0, 0, 0, 0))-(new Date({now.year}, {now.month-1}, {now.day}))) / (1000 * 60 * 60 * 24)",
    GAME=game_info(glist),
    DEMO=sorted((i.id for i in glist.items if i.demo)),
    TRIAL=sorted((i.id for i in glist.items if i.trial)),
    GAMEPASS=sorted((i.id for i in glist.items if i.gamepass)),
    replace=True,
)
j.save(
    "index.html",
    gl=glist,
    now=now
)
top_paid = EndPointCollection("TopPaid").json()[1]['Id']


def dict_to_game_list(obj: Dict[str, Set[str]]):
    arr: List[Tuple[Game, Tuple[Game]]] = []
    for pid, cids in obj.items():
        cids = sorted(cids)
        arr.append((ALL_GAMES[pid], tuple(map(lambda i: ALL_GAMES[i], cids))))
    return arr


j.save(
    "faq.html",
    destino="faq/index.html",
    browser=URL_GAMES_BROWSER,
    catalogs=api.get_catalog_list(),
    collections=api.get_collection_list(),
    product=EndPointProduct(top_paid),
    complements=dict_to_game_list(COMP),
    older=dict_to_game_list(OLDR),
    now=now
)
print("Fin")

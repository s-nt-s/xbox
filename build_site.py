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
import logging

import argparse

parser = argparse.ArgumentParser(
    description='Lista juegos de xbox del gamepass o de menos de X€')
parser.add_argument("--precio", type=float, help='Precio máximo', default=9999)

args = parser.parse_args()

config_log("log/build_site.log")
logger = logging.getLogger(__name__)

api = Api()


def do_filter1(i: Game):
    if i.isInGamepass:
        return True
    if i.price <= args.precio:
        return True
    logger.debug(i.id+f" por precio {i.price}")
    return False


def do_filter2(i: Game):
    if i.price > 0 and not i.isInGamepass and i.isPreview and not i.isTrial:
        logger.debug(i.id+" descartado por isPreview")
        return False
    if not i.isXboxSeries:
        logger.debug(i.id+" descartado por !isXboxSeries")
        return False
    if i.summary is None:
        logger.debug(i.id+" descartado por summary=None")
        return False
    #if not i.isGame:
    #    logger.debug(i.id+" descartado por !isGame")
    #    return False
    if i.notAvailable:
        logger.debug(i.id+" descartado por notAvailable")
        return False
    if i.isInGamepass:
        return True
    if i.requiresGame:
        logger.debug(i.id+" descartado por requiresGame")
        return False
    if i.notSoldSeparately:
        logger.debug(i.id+" descartado por notSoldSeparately")
        return False
    if i.isPreorder:
        logger.debug(i.id+" descartado por preorder")
        return False
    # if 'Trial' in i.actions:
    #    return False
    return True


def do_filter3(i: Game):
    bundle = tuple(map(Game.get, i.bundle))
    if len(bundle) == 0:
        return True
    isNotGame = 0
    isNotXbox = 0
    for g in bundle:
        if not g.isGame:
            isNotGame = isNotGame + 1
        if not g.isXboxSeries:
            isNotXbox = isNotXbox + 1
        if g.summary and g.isPreorder:
            logger.debug(i.id+" descartado por incluir preorder: "+g.id)
            return False
    if isNotGame == len(bundle):
        logger.debug(i.id+" descartado por no incluir juegos")
        return False
    if isNotXbox == len(bundle):
        logger.debug(i.id+" descartado por no incluir XboxSeriesX")
        return False
    return True


def get_games() -> Tuple[Game]:
    games: Set[Game] = set()
    for i in list(map(Game.get, api.get_ids())):
        if i.isUseless:
            logger.debug(i.id+" descartado por isUseless")
            continue
        games.add(i)
        for b in map(Game.get, i.content_id):
            games.add(b)
    games = tuple(sorted(games, key=lambda g: g.id))
    logger.debug(f"GAMES ({len(games)}) = " + " ".join(map(lambda g: g.id, games)))
    return games


print("Obteniendo juegos", end="\r")
ALL_GAMES = {i.id: i for i in get_games()}
print("Obteniendo juegos:", len(ALL_GAMES))

print("Aplicando 1º filtro", end="\r")
items = list(filter(do_filter1, ALL_GAMES.values()))
print("Aplicando 1º filtro:", len(items))

print("Aplicando 2º filtro", end="\r")
items = list(filter(do_filter2, items))
print("Aplicando 2º filtro:", len(items))

print("Aplicando 3º filtro", end="\r")
items = list(filter(do_filter3, items))
print("Aplicando 3º filtro:", len(items))

print("Descartando complementos o bundle redundantes")

COMP: Dict[str, Set[str]] = {}
OLDR: Dict[str, Set[str]] = {}
BADD: List[Game] = []
BETD: List[Game] = []
items = {i.id: i for i in items}

for pid, cids in gfilter.is_chunk_of(items):
    cids = tuple([c for c in cids if c in items])
    if cids and pid in items:
        for cid in cids:
            gm = items[cid]
            if gm.price == 0:
                gm.demo_of = pid
            else:
                logger.debug(cid+" descartado por incompleto")
                dict_add(COMP, pid, cid)
                del items[cid]

for pid, cids in gfilter.is_comp_of(items):
    cids = tuple([c for c in cids if c in items])
    if cids and pid in items:
        for cid in cids:
            logger.debug(cid+" descartado por ser complemento")
            dict_add(COMP, pid, cid)
            del items[cid]

for pid, cids in gfilter.is_older_version_of(items, all_games=ALL_GAMES.values()):
    cids = tuple([c for c in cids if c in items])
    if cids and pid in items:
        for cid in cids:
            logger.debug(cid+" descartado por ser versión antigua")
            dict_add(OLDR, pid, cid)
            del items[cid]

for g in gfilter.is_bad_deal(items):
    if len(set(g.bundle).difference(items.keys())) == 0:
        logger.debug(g.id+" descartado por ser mal negocio (más barato por separado 1/2)")
        BADD.append(g)
        del items[g.id]

for pid, cids in gfilter.is_in_better_deal(items):
    cids = tuple([c for c in cids if c in items])
    if len(cids) > 0:
        logger.debug(pid+" descartado por ser mal negocio (más barato en un bundle)")
        BETD.append(Game.get(pid))
        del items[pid]

for g in gfilter.is_bad_deal(items):
    bdl = tuple((i for i in map(Game.get, g.bundle) if not i.isUseless))
    bdlGame = set((i.id for i in bdl if i.isGame))
    bdlntSl = tuple((i.id for i in bdl if i.notSoldSeparately or i.notAvailable))
    if len(bdlntSl) == 0 and len(bdlGame.difference(items.keys())) == 0:
        logger.debug(g.id+" descartado por ser mal negocio (más barato por separado 2/2)")
        BADD.append(g)
        del items[g.id]

for best, worse in gfilter.is_useless_bundle(items):
    worse = tuple([w.id for w in worse if w.id in items])
    if best.id in items and len(worse):
        logger.debug(best.id+" descarta a los siguientes por ser mal negocio: " + " ".join(worse))
        for g in worse:
            BADD.append(Game.get(g))
            del items[g]

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
    DEMO=sorted((i.id for i in glist.items if i.isDemo)),
    PREVIEW=sorted((i.id for i in glist.items if i.isPreview)),
    TRIAL=sorted((i.id for i in glist.items if i.isTrial)),
    GAMEPASS=sorted((i.id for i in glist.items if i.isInGamepass)),
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
    bad_deal=BADD,
    better_deal=BETD,
    now=now
)
print("Fin")

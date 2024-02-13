#!/usr/bin/env python3

from core.api import Api
from core.j2 import Jnj2, to_value
from datetime import datetime
from core.game import Game, GameList

import argparse

parser = argparse.ArgumentParser(
    description='Lista juegos de xbox del gamepass o de menos de X€')
parser.add_argument("--precio", type=float, help='Precio máximo', default=9999)

args = parser.parse_args()

api = Api()


def do_filter1(i: Game):
    if i.gamepass:
        return True
    if (i.price <= args.precio):
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


def iter_progress(arr: list[Game]):
    total = len(arr)
    for i, a in enumerate(arr):
        i = i+1
        prc = (i/total)*100
        print("{0:3.0f}% [{1}/{2}]".format(prc, i, total), end="\r")
        yield a
    print("100% [{0}/{0}]".format(total))


def get_games():
    ids = list(api.get_ids())
    items = list(map(Game, ids))
    for i in items:
        for b in i.get_bundle():
            if b not in ids:
                b = Game(b)
                if b.isGame:
                    items.append(b)
                    ids.append(b.id)
    return tuple(sorted(items, key=lambda g: g.id))

print("Obteniendo juegos", end="\r")
items = get_games()
print("Obteniendo juegos:", len(items))

print("Aplicando 1º filtro", end="\r")
items = list(filter(do_filter1, items))
print("Aplicando 1º filtro:", len(items))

print("Aplicando 2º filtro", end="\r")
items = list(filter(do_filter2, items))
print("Aplicando 2º filtro:", len(items))

print("Generando web")
# (-x.reviews, -x.rate, x.title))
items = sorted(items, key=lambda x: x.releaseDate, reverse=True)

glist = GameList(items)
now = datetime.now()


def game_info():
    lst = dict(glist.info)
    for k, g in lst.items():
        g = dict(g)
        g['tags'] = tuple(map(to_value, g['tags']))
        lst[k] = g
    return lst


j = Jnj2("template/", "out/")
j.create_script(
    "info.js",
    ANTIQUITY=f"((new Date().setHours(0, 0, 0, 0))-(new Date({now.year}, {now.month-1}, {now.day}))) / (1000 * 60 * 60 * 24)",
    GAME=game_info(),
    replace=True
)
j.save(
    "index.html",
    gl=glist,
    now=now
)
print("Fin")

#!/usr/bin/env python3

from core.api import Api, ApiDriver
from core.j2 import Jnj2
from datetime import datetime
from core.game import Game, GameList

import argparse

parser = argparse.ArgumentParser(description='Lista juegos de xbox del gamepass o de menos de X€')
parser.add_argument("--precio", type=float, help='Precio máximo', default=9999)

args = parser.parse_args()

api = Api()


def do_filter1(i: Game):
    if i.gamepass:
        return True
    if (i.price is None or i.price <= args.precio):
        return True
    return 'TopFree' in i.collections
    # return 'TopFree' not in i.collections and i.price == 0


def do_filter2(i: Game):
    if i.gamepass:
        return True
    if i.requiresGame:
        return False
    if i.notSoldSeparately:
        return False
    if i.preorder:
        return False
    #if 'Trial' in i.actions:
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


print("Obteniendo juegos", end="\r")
items = api.get_items()
print("Obteniendo juegos:", len(items))
print("Aplicando 1º filtro", end="\r")
items = list(filter(do_filter1, items))
print("Aplicando 1º filtro:", len(items))

print("Aplicando 2º filtro", end="\r")
items = list(filter(do_filter2, items))
print("Aplicando 2º filtro:", len(items))

print("Aplicando 2º filtro", end="\r")
items = list(filter(do_filter2, items))
print("Aplicando 2º filtro:", len(items))

print("Generando thumbnail")
for i in iter_progress(items):
    _ = str(i.thumbnail)

print("Generando web")
items = sorted(items, key=lambda x: x.releaseDate, reverse=True)#(-x.reviews, -x.rate, x.title))

glist = GameList(items)
now = datetime.now()

j = Jnj2("template/", "out/")
j.create_script(
    "info.js",
    ANTIQUITY=f"((new Date().setHours(0, 0, 0, 0))-(new Date({now.year}, {now.month-1}, {now.day}))) / (1000 * 60 * 60 * 24)",
    GAME=glist.info,
    replace=True
)
j.save(
    "index.html",
    gl=glist,
    now=now
)
print("Fin")

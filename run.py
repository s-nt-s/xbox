#!/usr/bin/env python3

from munch import Munch

from core.api import Api, ApiDriver
from core.j2 import Jnj2
from datetime import datetime
from math import ceil

import argparse

parser = argparse.ArgumentParser(description='Lista juegos de xbox del gamepass o de menos de X€')
parser.add_argument("--precio", type=float, help='Precio máximo', default=9999)

args = parser.parse_args()

api = Api()


def do_filter1(i):
    if i.gamepass:
        return True
    if (i.price is None or i.price <= args.precio):
        return True
    return 'TopFree' in i.collections
    # return 'TopFree' not in i.collections and i.price == 0

def do_filter2(i):
    if i.gamepass:
        return True
    if i.requiresGame:
        return False
    if i.notSoldSeparately:
        return False
    #if 'Trial' in i.actions:
    #    return False
    return True

def iter_progress(arr):
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

print("Obteniendo preload state")
for i in iter_progress(items):
    i.preload_state = api.get_preload_state(i.id)

print("Aplicando 2º filtro", end="\r")
items = list(filter(do_filter2, items))
print("Aplicando 2º filtro:", len(items))

print("Obteniendo acciones y reviews")
with ApiDriver(browser="wirefirefox") as f:
    for i in iter_progress(items):
        i.productActions = api.get_actions(f, i.id)
        i.reviews = (api.get_reviews(f, i.id) or {}).get('totalRatingsCount')


print("Aplicando 2º filtro", end="\r")
items = list(filter(do_filter2, items))
print("Aplicando 2º filtro:", len(items))

print("Generando web")
items = sorted(items, key=lambda x: (-x.reviews, -x.rate, x.title))

info = map(lambda x:x.to_dict(), items)
info = sorted(info, key=lambda x:x["id"])
info = {
    i["id"]: i for i in info
}

tags = set()
for i in items:
    tags = tags.union(i.tags)
tags = sorted(tags - set({'GamePass', 'Free'}))

j = Jnj2("template/", "docs/")
j.create_script("info.js", GAME=info, replace=True)
j.save("index.html",
       juegos=items,
       tags=tags,
       mx=dict(
           precio=ceil(max([i.price for i in items])),
           reviews=ceil(max([i.reviews for i in items])),
           rate=ceil(max([i.rate for i in items]))
       ),
       now=datetime.now()
)
print("Fin")

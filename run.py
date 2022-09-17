#!/usr/bin/env python3

from munch import Munch

from core.api import Api
from core.j2 import Jnj2
from core.web import Driver, Web
import time

import argparse

parser = argparse.ArgumentParser(description='Lista juegos de xbox gratuitos')

args = parser.parse_args()

api = Api()


def do_filter1(i):
    if i.gamepass:
        return True
    if (i.price is None or i.price <= 0):
        return True
    return 'TopFree' in i.collections
    # return 'TopFree' not in i.collections and i.price == 0

def do_filter2(i):
    if i.gamepass:
        return True
    if i.notSoldSeparately:
        return False
    if 'Trial' in i.actions:
        return False
    return True

items = list(filter(do_filter1, api.get_items()))

with Driver(browser="wirefirefox") as f:
    for i in items:
        i.productActions = api.get_actions(f, i.id)

items = list(filter(do_filter2, items))
items = sorted(items, key=lambda x: (-x.rate, x.title))

info = sorted(list(map(lambda x:x.to_dict(), items)), key=lambda x:x["id"])
info = {
    i["id"]: i for i in info
}
tags = set()
for i in items:
    tags = tags.union(i.tags)
tags = sorted(tags - set({'GamePass', 'Free'}))

j = Jnj2("template/", "out/")
j.create_script("info.js", GAME=info)
j.save("index.html",
       juegos=items,
       tags=tags
)

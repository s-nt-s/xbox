from core.game import Game
from typing import Dict, List
from core.util import dict_add, dict_tuple
import re
from functools import cache

re_sp = re.compile(r"\s+")


def is_chunk_of(items: Dict[str, Game]):
    game_dem = dict()
    re_title = re.compile(
        r"Complete Season|Juego completo|Temporada completa|Complete Season")
    obj = {**{
        "9NB2KCX4G29S": "Capcom Arcade Stadium Bundle",
        "9NQMLX3Z30DR": "Capcom Arcade 2nd Stadium Bundle",
    }, **{i.id: i.title for i in items.values() if re_title.search(i.title)}}
    for gid in obj.keys():
        if gid in items:
            for bid in items[gid].get_bundle():
                if gid != bid and bid in items:
                    dict_add(game_dem, gid, bid)
    return dict_tuple(game_dem).items()


def is_comp_of(items: Dict[str, Game]):
    game_comp = dict()
    for gid in sorted({
        "C0FZNGPNQQRQ": "Crossout",
        "9PLTP0XJ75GS": "Pinball FX",
        "9PCKBVF3P67H": "Pinball FX3",
        "9NHKL695M9F2": "Enlisted",
        "9PF432CVQBXT": "Enlisted Xbox One",
        "C1ZT6N30L1WH": "World of Warships: Legends",
        "C20WW4W29FQ1": "Generation Zero",
        "C2MHS238PDNS": "SMITE",
        "9NRMXFFD3K13": "Century: Age of Ashes",
        "BT5P2X999VH2": "Fortnite",
        "BQF41W70ZLSV": "3on3 FreeStyle",
        "C1C4DZJPBC2V": "Overwatch 2",
        "C3NNLTHW9T9W": "CRSED: F.O.A.D.",
        "C35NTVN04WK5": "Realm Royale Reforged",
        "C4PZ0V39GXN2": "Paladins",
        "9P1RSQ5MGPCR": "Phantasy Star Online 2 New Genesis",
        "9P4S1BPJLPHZ": "Splitgate",
        "9N8KTVPKX66N": "Techwars Global Conflict",
        "BX1DTCBD1HXJ": "War Thunder",
        "BQL8L17RV09Z": "Vigor",
        "BPHSZ44NGDB2": "Rogue Company",
        "9NT1ZBBV6WH6": "eFootball",
        "BVM002M8HH0S": "Fishing Planet",
        "C59QBPB8P1XJ": "DC Universe Online"
    }.keys()):
        if gid in items:
            for g in list(items.values()):
                if g.id != gid and gid in g.get_bundle():
                    dict_add(game_comp, gid, g.id)
    return dict_tuple(game_comp).items()


def is_older_version_of(items: Dict[str, Game], all_games: List[Game]):
    def eq(a: str, b: str):
        if None in (a, b):
            return False
        return a == b

    def glines(txt: str):
        lns = set()
        for ln in txt.split("\n"):
            ln = re_sp.sub(" ", ln).strip()
            if len(ln) > 10:
                lns.add(ln)
        return lns

    @cache
    def trim(s: str):
        s = s.strip()
        if len(s) > 600 and s.count("\n") > 2 and s.index("\n") < 200:
            s = "\n".join(s.split("\n")[1:])
        s = re.sub(r"Xbox\s*(One|Series\s*X\|S)", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\(\)", "", s)
        s = re_sp.sub(" ", s)
        return s.strip()

    def trim_eq(a: str, b: str):
        if None in (a, b) or '' in (a, b):
            return False
        a = trim(a).lower()
        if len(a) == 0:
            return False
        return a == trim(b).lower()

    def common_lines(a: str, b: str):
        return len(glines(a).intersection(glines(b)))

    def is_common_developer(a: Game, b: Game):
        if (a.developer, b.developer) == (None, None):
            return eq(a.publisher, b.publisher)
        return eq(a.developer, b.developer)

    older_ver = dict()

    # Control
    dict_add(older_ver, "9P4D0K92BM7V", "BZ6W9LRPC26W")
    # Cities: Skylines
    dict_add(older_ver, "9MZ4GBWX9GND", "C4GH8N6ZXG5L")
    # MLB® The Show™ 21
    dict_add(older_ver, "9NC8F83CQB76", "9PNF5J31C36N")
    # Music Racer
    dict_add(older_ver, "9MT9CDBGNJXP", "9N713D9S9VMG")
    # GTAV
    new_gtav = "9NXMBTB02ZSF"
    old_gtav = "BPJ686W6S0NH"
    dict_add(older_ver, new_gtav, old_gtav)
    for g in items.values():
        gms = [i for i in map(Game.get, g.get_bundle()) if i.isXboxGame]
        if len(gms) == 1 and gms[0].id == old_gtav:
            dict_add(older_ver, new_gtav, g.id)

    xbox_series: List[Game] = []
    xbox_one: List[Game] = []

    ids_xbox_series = set(
        (i.id for i in all_games if i.availableOn and "XboxOne" not in i.availableOn and i.isXboxSeries))
    for i in list(items.values()):
        if i.id in ids_xbox_series or ids_xbox_series.intersection(i.get_bundle()):
            xbox_series.append(i)
        else:
            xbox_one.append(i)
    ids_xbox_series = set((i.id for i in xbox_series))
    xbox_one = [
        o for o in xbox_one if not ids_xbox_series.intersection(o.get_bundle())]

    for x in xbox_series:
        for o in xbox_one:
            if trim_eq(x.productDescription, o.productDescription) and trim_eq(x.title, o.title):
                dict_add(older_ver, x.id, o.id)
                continue
            if not is_common_developer(x, o):
                continue
            if trim_eq(x.productDescription, o.productDescription):
                dict_add(older_ver, x.id, o.id)
                continue
            if o.id in x.get_bundle() and trim_eq(x.shortTitle, o.shortTitle):
                dict_add(older_ver, x.id, o.id)
                continue
            if trim_eq(x.title, o.title):
                dict_add(older_ver, x.id, o.id)
                continue
            if not eq(o.productGroup, x.productGroup):
                continue
            if common_lines(x.productDescription, o.productDescription) > 5:
                dict_add(older_ver, x.id, o.id)
                continue
    return dict_tuple(older_ver).items()


def is_bad_deal(items: Dict[str, Game]):
    for g in list(items.values()):
        if not g.get_bundle():
            continue
        price = 0
        for b in map(Game.get, g.get_bundle()):
            price = price + b.price
        if price <= g.price:
            yield g


def is_in_better_deal(items: Dict[str, Game]):
    in_better = dict()
    for g in list(items.values()):
        for b in map(Game.get, g.get_partent_bundle()):
            if b.id == g.id:
                continue
            if (g.price > b.price) or (g.price == b.price and len(set(b.get_bundle()).difference((g.id,)))>0):
                dict_add(in_better, g.id, b.id)
    return dict_tuple(in_better).items()

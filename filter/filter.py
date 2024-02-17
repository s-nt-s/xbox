from core.game import Game
from typing import Dict, List, Tuple
from core.util import dict_add, dict_tuple
import re


def is_chunk_of(items: Dict[str, Game]):
    game_dem = dict()
    re_title = re.compile(r"Complete Season|Juego completo|Temporada completa|Complete Season")
    for gid in {**{
        "9NB2KCX4G29S": "Capcom Arcade Stadium Bundle",
        "9NQMLX3Z30DR": "Capcom Arcade 2nd Stadium Bundle",
    }, **{i.id: i.title for i in items.values() if re_title.search(i.title)}}.keys():
        if gid in items:
            for bid in items[gid].get_bundle():
                if gid != bid and bid in items:
                    dict_add(game_dem, gid, bid)
    return dict_tuple(game_dem)


def is_comp_of(items: Dict[str, Game]):
    game_comp = dict()
    for gid in {
        "C0FZNGPNQQRQ": "Crossout",
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
    }.keys():
        if gid in items:
            for g in list(items.values()):
                if g.id != gid and gid in g.get_bundle():
                    dict_add(game_comp, gid, g.id)
    return dict_tuple(game_comp)


def is_older_version_of(items: Dict[str, Game], all_games: List[Game]):
    older_ver = dict()
    xbox_series: List[Game] = []
    xbox_one: List[Game] = []

    ids_xbox_series = set((i.id for i in all_games if i.availableOn and "XboxOne" not in i.availableOn))
    for i in list(items.values()):
        if i.id in ids_xbox_series or ids_xbox_series.intersection(i.get_bundle()):
            xbox_series.append(i)
        else:
            xbox_one.append(i)
    ids_xbox_series = set((i.id for i in xbox_series))
    xbox_one = [o for o in xbox_one if not ids_xbox_series.intersection(o.get_bundle())]
    for x in xbox_series:
        for o in xbox_one:
            if len(x.productDescription) > 0 and x.productDescription == o.productDescription:
                dict_add(older_ver, x.id, o.id)
            elif len(x.shortTitle) > 0 and x.shortTitle == o.shortTitle and o.id in x.get_bundle():
                dict_add(older_ver, x.id, o.id)
    return dict_tuple(older_ver)

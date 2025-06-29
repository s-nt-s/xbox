from core.api import Api
from core.game import Game
from core.util import chunks
import argparse
from core.log import config_log
import logging
from core.bulkrequests import BulkRequests
from core.bulkapi import BulkRequestsGame, BulkRequestsPreloadState, BulkRequestsActions, BulkRequestsReviews
from os.path import isfile
from os import remove
from core.endpoint import EndPointProduct, AccessDenied
import time
from typing import Tuple, Union, Set
from core.findwireresponse import FindWireResponse

parser = argparse.ArgumentParser(
    description='Descarga ficheros para la cache',
)
parser.add_argument(
    '--tcp-limit', type=int, default=50
)
parser.add_argument(
    '--tolerance', type=int, default=0, help="Porcentaje de tolerancia"
)

parser.add_argument(
    '--browse', action='store_true', help="Recorre los resultados de www.xbox.com/es-ES/games/browse"
)
parser.add_argument(
    '--game', action='store_true', help="Descarga la ficha de los juegos"
)
parser.add_argument(
    '--action', action='store_true', help="Descarga las acciones de los juegos"
)
parser.add_argument(
    '--review', action='store_true', help="Descarga las review de los juegos"
)
parser.add_argument(
    '--preload-state', action='store_true', help="Descarga el preload state de los juegos"
)

config_log("log/dwn.log")


def get_games(ids: Union[Set[str], Tuple[str]]):
    return map(Game.get, list(ids))


def all_false_is_all_true(nm: argparse.Namespace):
    ks = []
    for k, v in vars(ARG).items():
        if isinstance(v, bool):
            if v is True:
                setattr(nm, 'all', False)
                return
            ks.append(k)
    for k in ks:
        setattr(nm, k, True)
    setattr(nm, 'all', True)


logger = logging.getLogger(__name__)
logger.info("START")

ARG = parser.parse_args()
all_false_is_all_true(ARG)
API = Api()
IDS = API.get_ids()


def dwn_game(tcp_limit: int = 10, tolerance: int = 0, tries=10, ids=None, overwrite=False):
    if ids is None:
        ids = IDS
    if overwrite:
        for i in ids:
            file = EndPointProduct(i).file
            if isfile(file):
                remove(file)
    else:
        ids = [i for i in ids if not isfile(EndPointProduct(i).file)]
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=tries,
        tolerance=tolerance
    ).run(*(
        BulkRequestsGame(tuple(c)) for c in chunks(ids, 100)
    ), label="x100 game")


def dwn_preload_state(tcp_limit: int = 10, tolerance: int = 0, tries=100, ids=None, overwrite=False):
    if ids is None:
        ids = IDS
    try:
        BulkRequests(
            tcp_limit=tcp_limit,
            tries=tries,
            tolerance=tolerance,
            sleep=100
        ).run(*map(BulkRequestsPreloadState, ids), label="preload_state", overwrite=overwrite)
    except AccessDenied:
        logger.critical("AccessDenied when dwn_preload_state")
        time.sleep(600)
        return dwn_preload_state(tcp_limit=tcp_limit, tolerance=tolerance, ids=ids)


def dwn_action(tcp_limit: int = 10, tolerance: int = 0, tries=10, ids=None, overwrite=False):
    if ids is None:
        ids = IDS
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=tries,
        tolerance=tolerance
    ).run(*map(BulkRequestsActions, ids), label="action", overwrite=overwrite)


def dwn_review(tcp_limit: int = 10, tolerance: int = 0, tries=10, ids=None, overwrite=False):
    if ids is None:
        ids = IDS
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=tries,
        tolerance=tolerance
    ).run(*map(BulkRequestsReviews, ids), label="review", overwrite=overwrite)


if ARG.browse:
    API.do_games_browse_search()

if ARG.game:
    dwn_game(tcp_limit=ARG.tcp_limit, tolerance=ARG.tolerance)

if ARG.action:
    dwn_action(tcp_limit=ARG.tcp_limit, tolerance=ARG.tolerance)

if ARG.review:
    dwn_review(tcp_limit=ARG.tcp_limit, tolerance=ARG.tolerance)

if ARG.preload_state:
    ids = IDS
    if ARG.all:
        ids = tuple(sorted(set((i.id for i in map(Game.get, ids) if not i._isUseless))))
    dwn_preload_state(tcp_limit=ARG.tcp_limit, tolerance=ARG.tolerance, ids=ids)


def is_missing_preload(g: Union[str, Game]):
    if isinstance(g, Game):
        if g._isUseless:
            return False
        if g.productActions is None:
            return False
        if g.summary is None:
            return True
        return False
    if is_missing_preload(Game.get(g)) is False:
        return False
    return is_missing_preload(Game(g))


def extra_dwn(ids: Tuple[str], tolerance, overwrite=False):
    logger.info(f"Extra dwn {len(ids)} ids")
    ids = tuple(sorted(ids))
    dwn_game(tcp_limit=ARG.tcp_limit, ids=ids, tolerance=tolerance, overwrite=overwrite)
    ids = tuple(sorted(set((i.id for i in get_games(ids) if not i._isUseless))))
    if len(ids):
        dwn_action(tcp_limit=ARG.tcp_limit, ids=ids, tolerance=tolerance, overwrite=overwrite)
        ids = tuple(sorted(set((i.id for i in get_games(ids) if i.productActions is not None))))
        dwn_review(tcp_limit=ARG.tcp_limit, ids=ids, tolerance=tolerance, overwrite=overwrite)
        dwn_preload_state(tcp_limit=ARG.tcp_limit, ids=ids, tolerance=tolerance, overwrite=overwrite)


if ARG.all:
    tries = set()
    done = set(IDS)
    logger.info("Obteniendo juegos extra de los bundle")
    print("")
    count = len(done)
    while True:
        ids = set()
        for g in get_games(done):
            count -= 1
            print(count, "     ", end="\r")
            for b in g.bundle:
                if b not in done:
                    ids.add(b)
                    done.add(b)
        if len(ids) > 0:
            extra_dwn(ids, ARG.tolerance, overwrite=False)
            continue
        ids = tuple(sorted((i for i in done if is_missing_preload(i))))
        if len(ids) == 0 or ids in tries:
            break
        tries.add(ids)
        logger.info("Revisando consistencia")
        FindWireResponse.WR.clear()
        Game.get.cache_clear()
        extra_dwn(ids, len(ids), overwrite=True)

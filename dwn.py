from core.api import Api
from core.game import Game
from core.util import chunks
import argparse
import logging
from core.bulkrequests import BulkRequests
from core.bulkapi import BulkRequestsGame, BulkRequestsPreloadState, BulkRequestsActions, BulkRequestsReviews
from os.path import isfile
from core.endpoint import EndPointProduct

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
    '--preload-state', action='store_true', help="Descarga el preload state de los juegos"
)
parser.add_argument(
    '--action', action='store_true', help="Descarga las acciones de los juegos"
)
parser.add_argument(
    '--review', action='store_true', help="Descarga las review de los juegos"
)


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


open("dwn.log", "w").close()
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(name)s - %(levelname)s - %(message)s',
    datefmt='%d-%m-%Y %H:%M:%S',
    handlers=[
        logging.FileHandler("dwn.log"),
        logging.StreamHandler()
    ]
)
for name in ('seleniumwire.proxy.handler', 'seleniumwire.proxy.client'):
    logging.getLogger(name).setLevel(logging.CRITICAL)

logger = logging.getLogger(__name__)

ARG = parser.parse_args()
all_false_is_all_true(ARG)
API = Api()
IDS = API.get_ids()


def dwn_game(tcp_limit: int = 10, tolerance: int = 0, ids=None):
    if ids is None:
        ids = IDS
    ids = [i for i in ids if not isfile(EndPointProduct(i).file)]
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=10,
        tolerance=tolerance
    ).run(*(
        BulkRequestsGame(tuple(c)) for c in chunks(ids, 100)
    ), label="x100 game")


def dwn_preload_state(tcp_limit: int = 10, tolerance: int = 0, ids=None):
    if ids is None:
        ids = IDS
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=100,
        tolerance=tolerance,
        sleep=60
    ).run(*map(BulkRequestsPreloadState, ids), label="preload_state")


def dwn_action(tcp_limit: int = 10, tolerance: int = 0, ids=None):
    if ids is None:
        ids = IDS
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=10,
        tolerance=tolerance
    ).run(*map(BulkRequestsActions, ids), label="action")


def dwn_review(tcp_limit: int = 10, tolerance: int = 0, ids=None):
    if ids is None:
        ids = IDS
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=10,
        tolerance=tolerance
    ).run(*map(BulkRequestsReviews, ids), label="review")


if ARG.browse:
    API.do_games_browse_search()

if ARG.game:
    dwn_game(tcp_limit=ARG.tcp_limit, tolerance=ARG.tolerance)

if ARG.preload_state:
    dwn_preload_state(tcp_limit=ARG.tcp_limit, tolerance=ARG.tolerance)

if ARG.action:
    dwn_action(tcp_limit=ARG.tcp_limit, tolerance=ARG.tolerance)

if ARG.review:
    dwn_review(tcp_limit=ARG.tcp_limit, tolerance=ARG.tolerance)

if ARG.all:
    logger.info("Obteniendo juegos extra de los bundle")
    ids = set()
    for g in map(Game, IDS):
        for b in g.get_bundle():
            if b not in IDS:
                ids.add(b)
    ids = tuple(sorted(ids))
    dwn_game(tcp_limit=ARG.tcp_limit, ids=ids, tolerance=ARG.tolerance)
    ids = tuple(sorted(set((i.id for i in map(Game, ids) if i.isGame))))
    logger.info(f"Obtenido {len(ids)} juegos extra de los bundle")
    if len(ids):
        dwn_preload_state(tcp_limit=ARG.tcp_limit, ids=ids, tolerance=ARG.tolerance)
        dwn_action(tcp_limit=ARG.tcp_limit, ids=ids, tolerance=ARG.tolerance)
        dwn_review(tcp_limit=ARG.tcp_limit, ids=ids, tolerance=ARG.tolerance)

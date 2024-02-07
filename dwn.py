from core.api import Api, chunks
import argparse
import logging
from core.bulkrequests import BulkRequests
from core.bulkapi import BulkRequestsGame, BulkRequestsPreloadState, BulkRequestsActions, BulkRequestsReviews

parser = argparse.ArgumentParser(
    description='Descarga ficheros para la cache',
)
parser.add_argument(
    '--tcp-limit', type=int, default=50
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
                return
            ks.append(k)
    for k in ks:
        setattr(nm, k, True)


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

ARG = parser.parse_args()
all_false_is_all_true(ARG)
API = Api()


def dwn_game(tcp_limit: int = 10):
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=10
    ).run(*(
        BulkRequestsGame(tuple(c)) for c in chunks(API.get_ids(), 100)
    ), label="x100 game")


def dwn_preload_state(tcp_limit: int = 10):
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=10
    ).run(*map(BulkRequestsPreloadState, API.get_ids()), label="preload_state")


def dwn_action(tcp_limit: int = 10):
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=10
    ).run(*map(BulkRequestsActions, API.get_ids()), label="action")


def dwn_review(tcp_limit: int = 10):
    BulkRequests(
        tcp_limit=tcp_limit,
        tries=10
    ).run(*map(BulkRequestsReviews, API.get_ids()), label="review")


if ARG.game:
    dwn_game(tcp_limit=ARG.tcp_limit)

if ARG.preload_state:
    dwn_preload_state(tcp_limit=ARG.tcp_limit)

if ARG.action:
    dwn_action(tcp_limit=ARG.tcp_limit)

if ARG.review:
    dwn_review(tcp_limit=ARG.tcp_limit)

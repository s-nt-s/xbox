import logging
from os import makedirs
from os.path import dirname


def config_log(file: str):
    d = dirname(file)
    if d:
        makedirs(d, exist_ok=True)
    open(file, "w").close()
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(name)s - %(levelname)s - %(message)s',
        datefmt='%d-%m-%Y %H:%M:%S',
        handlers=[
            logging.FileHandler(file),
            logging.StreamHandler()
        ]
    )
    for name in ('seleniumwire.proxy.handler', 'seleniumwire.proxy.client'):
        logging.getLogger(name).setLevel(logging.CRITICAL)

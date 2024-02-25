import logging
from os import makedirs, environ
from os.path import dirname


def config_log(file: str):
    d = dirname(file)
    if d:
        makedirs(d, exist_ok=True)
    open(file, "w").close()
    logging.basicConfig(
        level=int(environ.get('LOG_LEVEL', logging.INFO)),
        format=environ.get('LOG_FORMAT', '%(asctime)s %(name)s - %(levelname)s - %(message)s'),
        datefmt='%d-%m-%Y %H:%M:%S',
        handlers=[
            logging.FileHandler(file),
            logging.StreamHandler()
        ]
    )
    for name in ('seleniumwire.proxy.handler', 'seleniumwire.proxy.client', 'urllib3.connectionpool', 'seleniumwire.proxy.storage', 'selenium.webdriver.remote.remote_connection'):
        logging.getLogger(name).setLevel(logging.CRITICAL)

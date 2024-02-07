import asyncio
from aiohttp import TCPConnector, ClientSession
import logging
from os.path import isfile
from os import remove
from abc import ABC, abstractproperty, abstractmethod
from aiohttp.client_exceptions import ClientError
from asyncio.exceptions import TimeoutError
import time

logger = logging.getLogger(__name__)


class BulkException(Exception):
    pass


class MissingBulkException(BulkException):
    def __init__(self, ko: int):
        super().__init__(f"{ko} missing")
        self.ko = ko


class BulkRequestsJob(ABC):

    @abstractproperty
    def url(self) -> str:
        pass

    @abstractmethod
    def done(self) -> bool:
        pass

    @abstractmethod
    def undo(self):
        pass

    @abstractmethod
    async def do(self, session: ClientSession) -> bool:
        pass

    @property
    def countdown(self) -> int:
        return getattr(self, '__countdown', None)

    @countdown.setter
    def countdown(self, x: int):
        setattr(self, '__countdown', x)

    @property
    def step(self) -> int:
        return getattr(self, '__step', None)

    @step.setter
    def step(self, x: int):
        setattr(self, '__step', x)


class BulkRequestsFileJob(BulkRequestsJob):
    @abstractproperty
    def file(self) -> str:
        pass

    def done(self) -> bool:
        return isfile(self.file)

    def undo(self):
        if self.done():
            remove(self.file)

    async def do(self, session: ClientSession) -> bool:
        async with session.get(self.url) as response:
            content = await response.text()
            with open(self.file, "w") as f:
                f.write(content)
            return True


class BulkRequests:
    def __init__(
            self,
            tcp_limit: int = 10,
            tries: int = 4,
            sleep: int = 10,
            tolerance: int = 0
    ):
        self.tcp_limit = tcp_limit
        self.tries = tries
        self.sleep = sleep
        self.tolerance = tolerance

    async def __requests(self, session: ClientSession, job: BulkRequestsJob):
        try:
            return await job.do(session)
        except (ClientError, TimeoutError):
            raise
        except Exception as e:
            logger.critical(str(e), exc_info=e)

    async def __requests_all(self, *job: BulkRequestsJob):
        my_conn = TCPConnector(limit=self.tcp_limit)
        async with ClientSession(connector=my_conn) as session:
            tasks = []
            for u in job:
                task = asyncio.ensure_future(
                    self.__requests(session=session, job=u)
                )
                tasks.append(task)
            rt = await asyncio.gather(*tasks, return_exceptions=True)
        return rt

    def run(self, *job: BulkRequestsJob, overwrite=False, label="items"):
        if overwrite:
            for u in job:
                u.undo()
        self.__run(*job, label=label)

    def __run(self, *job: BulkRequestsJob, label="items"):
        ko = 0
        tries = max(self.tries, 1) - 1
        rjust = len(str(len(job)))
        for i in reversed(range(tries+1)):
            job = tuple(u for u in job if not u.done())
            if len(job) == 0:
                return
            for u in job:
                u.step = tries - i
                u.countdown = i
            pre = "" if i == tries else "└─ "
            ljb = str(len(job)).rjust(rjust)
            logger.info(
                pre + 'BulkRequests' +
                f'(tcp_limit={self.tcp_limit}).run({ljb} {label})'
            )
            if i != tries:
                time.sleep(self.sleep)
            rt = asyncio.run(self.__requests_all(*job))
            ko = len([i for i in rt if i is not True])
            if ko == 0:
                return
        e = MissingBulkException(ko)
        if ko > self.tolerance:
            raise e
        logger.warning(str(e))

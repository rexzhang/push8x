from loguru import logger
from rich import inspect
from rich.pretty import pprint

from ..worker import worker_guardian
from .common import SenderAbc


class SenderBlackhole(SenderAbc):
    @worker_guardian()
    async def worker(self):
        while True:
            msg = await self.q.get()
            logger.info("sender.blackhole got msg:")
            pprint(msg)
            inspect(msg.receiver_smtpd_session)

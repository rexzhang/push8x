from logging import getLogger

from ..worker import worker_guardian
from .common import SenderAbc

logger = getLogger(__name__)


class SenderWebhook(SenderAbc):

    @worker_guardian()
    async def worker(self):
        while True:
            await self.q.get()
            raise

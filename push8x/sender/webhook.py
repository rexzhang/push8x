from ..worker import worker_guardian
from .common import SenderAbc


class SenderWebhook(SenderAbc):

    @worker_guardian()
    async def worker(self):
        while True:
            await self.q.get()
            raise

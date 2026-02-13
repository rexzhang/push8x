from logging import getLogger

from .common import SenderAbc

logger = getLogger(__name__)


class SenderBlackhold(SenderAbc):

    async def worker(self):
        pass

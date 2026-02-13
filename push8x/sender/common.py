from logging import getLogger

from ..constans import MsgQueue

logger = getLogger(__name__)


class SenderAbc:
    q: MsgQueue

    def __init__(self, sender_q: MsgQueue) -> None:
        self.q = sender_q

    async def worker(self):
        raise NotImplementedError

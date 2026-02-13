from typing import TypeAlias

from ..constans import MsgQueue

SenderQueueMapping: TypeAlias = dict[str, MsgQueue]


class SenderAbc:
    q: MsgQueue

    def __init__(self, sender_q: MsgQueue) -> None:
        self.q = sender_q

    async def worker(self):
        raise NotImplementedError

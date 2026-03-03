from ..config import Config
from ..constans import MsgQueue, ReceiverType


class ReceiverAbc:
    config: Config
    ruler_q: MsgQueue

    @property
    def type(self) -> ReceiverType:
        raise NotImplementedError

    @property
    def worker_name(self) -> str:
        return f"receiver:{self.type.value}"

    def __init__(self, config: Config, ruler_q: MsgQueue) -> None:
        self.config = config
        self.ruler_q = ruler_q

    async def worker_listen(self):
        raise NotImplementedError

    async def worker_processer(self):
        raise NotImplementedError

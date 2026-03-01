from logging import getLogger

from ..config import SenderConfig
from ..constans import MsgQueue, SenderType

logger = getLogger(__name__)


class SenderAbc:
    sender_config: SenderConfig
    q: MsgQueue

    @property
    def type(self) -> SenderType:
        raise NotImplementedError

    @property
    def worker_name(self) -> str:
        return f"sender:{self.sender_config.name}"

    def __init__(self, sender_config: SenderConfig, sender_q: MsgQueue) -> None:
        self.sender_config = sender_config
        self.q = sender_q

    async def worker(self):
        raise NotImplementedError

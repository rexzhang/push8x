from logging import getLogger

from ..config import Config
from ..constans import MsgQueue, ReceiverType

logger = getLogger(__name__)


class ReceiverAbc:
    config: Config
    rule_matcher_q: MsgQueue

    @property
    def type(self) -> ReceiverType:
        raise NotImplementedError

    @property
    def worker_name(self) -> str:
        return f"receiver:{self.type.value}"

    def __init__(self, config: Config, rule_matcher_q: MsgQueue) -> None:
        self.config = config
        self.rule_matcher_q = rule_matcher_q

    async def worker_listen(self):
        raise NotImplementedError

    async def worker_processer(self):
        raise NotImplementedError

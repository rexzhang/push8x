from logging import getLogger

from ..config import Config
from ..constans import MsgQueue, ReceiverType

logger = getLogger(__name__)


class ReceiverAbc:
    type: ReceiverType  # TODO: name?
    rule_matcher_q: MsgQueue

    def __init__(self, config: Config, rule_matcher_q: MsgQueue) -> None:
        self.config = config
        self.rule_matcher_q = rule_matcher_q

    async def worker_recevier(self):
        raise NotImplementedError

    async def worker_processer(self):
        raise NotImplementedError

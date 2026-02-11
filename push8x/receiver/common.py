from logging import getLogger

from ..config import Config
from ..constans import ReceiverType
from ..task import TaskQueue

logger = getLogger(__name__)


class ReceiverAbc:
    type: ReceiverType  # TODO: name?
    rule_matcher_q: TaskQueue

    def __init__(self, config: Config, rule_matcher_q: TaskQueue) -> None:
        self.config = config
        self.rule_matcher_q = rule_matcher_q

    async def worker(self):
        raise NotImplementedError

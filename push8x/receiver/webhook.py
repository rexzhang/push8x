from logging import getLogger

from ..auth import AuthAbc
from ..config import Config
from ..constans import MsgQueue, ReceiverType
from ..worker import worker_guardian
from .common import ReceiverAbc

logger = getLogger(__name__)


class ReceiverWebhookAuth(AuthAbc):
    @property
    def username_key(self) -> str:
        return "name"

    @property
    def password_key(self) -> str:
        return "token"


class ReceiverWebhook(ReceiverAbc):
    @property
    def type(self) -> ReceiverType:
        return ReceiverType.WEBHOOK

    def __init__(self, config: Config, q: MsgQueue, rule_matcher_q: MsgQueue) -> None:
        super().__init__(config, rule_matcher_q)
        self.q = q

    @worker_guardian()
    async def worker_processer(self):
        while True:
            msg = await self.q.get()
            # TODO: parse webhook payload
            await self.rule_matcher_q.put(msg)

from ..auth import AuthAbc
from ..config import Config
from ..constans import MsgQueue, ReceiverType
from ..worker import worker_guardian
from .common import ReceiverAbc


class ReceiverWebhookAuth(AuthAbc):
    receiver_type = ReceiverType.WEBHOOK

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

    def __init__(self, config: Config, q: MsgQueue, ruler_q: MsgQueue) -> None:
        super().__init__(config, ruler_q)
        self.q = q

    @worker_guardian()
    async def worker_processer(self):
        while True:
            msg = await self.q.get()
            # TODO: parse webhook payload
            await self.ruler_q.put(msg)

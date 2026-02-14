from logging import getLogger

import uvicorn

from ..config import Config
from ..constans import Msg, MsgContentType, MsgQueue, ReceiverType
from ..worker import worker_guardian
from .common import ReceiverAbc

logger = getLogger(__name__)

_rule_matcher_q: MsgQueue


async def simple_asgi_app(scope, receive, send):
    if scope["type"] != "http":
        return

    msg = Msg(
        f_name="",
        f_value="aaaa",
        t_name="",
        t_value="*@example.com",
        title="title",
        content="content",
        content_format=MsgContentType.PLAIN,
        ext=dict(),
        receiver=ReceiverType.WEBHOOK,
    )

    await _rule_matcher_q.put(msg)

    await send(
        {
            "type": "http.response.start",
            "status": 200,
            "headers": [[b"content-type", b"text/plain"]],
        }
    )

    await send(
        {
            "type": "http.response.body",
            "body": b"Hello from Native ASGI! SMTP is also running.",
        }
    )


class ReceiverWebhook(ReceiverAbc):

    @property
    def type(self) -> ReceiverType:
        return ReceiverType.WEBHOOK

    def __init__(self, config: Config, rule_matcher_q: MsgQueue) -> None:
        super().__init__(config, rule_matcher_q)

        global _rule_matcher_q
        _rule_matcher_q = rule_matcher_q

    @worker_guardian()
    async def worker_recevier(self):
        server = uvicorn.Server(
            uvicorn.Config(
                app=simple_asgi_app,
                host=self.config.receiver.webhook.host,
                port=self.config.receiver.webhook.port,
                log_level="warning",
                access_log=False,
            )
        )
        logger.info(
            f"Starting {self.type} server on {self.config.receiver.webhook.host}:{self.config.receiver.webhook.port}"
        )
        await server.serve()

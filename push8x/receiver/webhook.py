from logging import getLogger

import uvicorn

from ..config import Config
from ..constans import ReceiverType
from ..task import MessageContentType, Task, TaskQueue
from .common import ReceiverAbc

logger = getLogger(__name__)

_rule_matcher_q: TaskQueue


async def simple_asgi_app(scope, receive, send):
    if scope["type"] != "http":
        return

    task = task = Task(
        f="aaaa",
        t="*@example.com",
        title="title",
        content="content",
        content_format=MessageContentType.PLAIN,
        ext=dict(),
        receiver=ReceiverType.WEBHOOK,
    )

    await _rule_matcher_q.put(task)

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
    def __init__(self, config: Config, rule_matcher_q: TaskQueue) -> None:
        super().__init__(config, rule_matcher_q)

        global _rule_matcher_q
        _rule_matcher_q = rule_matcher_q

        self.type = ReceiverType.WEBHOOK

    async def worker(self):
        server = uvicorn.Server(
            uvicorn.Config(
                app=simple_asgi_app,
                host=self.config.server_http.host,
                port=self.config.server_http.port,
                log_level="warning",
                access_log=False,
            )
        )
        await server.serve()

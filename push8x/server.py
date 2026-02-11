import asyncio
import logging
import sys
from collections.abc import Coroutine
from logging import getLogger

import uvicorn

from .config import Config
from .constans import SenderType
from .receiver.smtp import receiver_smtp_worker
from .rule import RuleMatcher
from .sender.apprise import SenderApprise
from .sender.common import SenderQueueMapping
from .task import TaskQueue

logger = getLogger(__file__)


async def simple_asgi_app(scope, receive, send):
    if scope["type"] != "http":
        return

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


async def receiver_webhook_worker():
    config = uvicorn.Config(app=simple_asgi_app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()


async def server(config: Config):
    # workers: list[Coroutine] = list()

    # init senders
    sender_list = list()
    sender_q_mapping: SenderQueueMapping = dict()
    sender_worker_list: list[Coroutine] = list()
    for sender in config.senders:
        sender_q = TaskQueue()

        match sender.type:
            case SenderType.APPRISE:
                sender_obj = SenderApprise(sender_q=sender_q)

            case _:
                raise

        sender_list.append(sender_obj)
        sender_worker_list.append(sender_obj.worker())
        sender_q_mapping[sender.name] = sender_q

    # init rule matcher
    rule_matcher_q = TaskQueue()
    rule_matcher = RuleMatcher(
        config=config, q=rule_matcher_q, sender_q_mapping=sender_q_mapping
    )

    print(
        f"正在启动服务 (HTTP: {config.server_http.host}:{config.server_http.port}, SMTP: {config.server_smtp.host}:{config.server_smtp.port}..."
    )
    await asyncio.gather(
        # receiver_webhook_worker(),
        receiver_smtp_worker(config, rule_matcher_q),
        rule_matcher.worker(),
        *sender_worker_list,
    )


def main(config: Config):
    if config.common.debug:
        logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)
    else:
        logging.basicConfig(stream=sys.stdout, level=logging.INFO)

    if config.common.sentry_dsn:
        try:
            import sentry_sdk  # type: ignore
            from sentry_sdk.integrations.asyncio import AsyncioIntegration

            sentry_sdk.init(
                dsn=config.common.sentry_dsn,
                send_default_pii=True,
                integrations=[
                    AsyncioIntegration(),
                ],
            )

        except ImportError as e:
            logger.warning(e)

    try:
        import uvloop

        with asyncio.Runner(loop_factory=uvloop.new_event_loop) as runner:
            runner.run(server(config))

    except ImportError:
        asyncio.run(server(config))

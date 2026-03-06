import asyncio
import logging
import sys
from collections.abc import Coroutine

from loguru import logger

from .config import Config
from .constans import MsgQueue
from .http_server import HttpServer
from .receiver.smtpd import ReceiverSmtpd
from .receiver.webhook import ReceiverWebhook
from .ruler import Ruler
from .sender import get_sender_mapping
from .worker import worker_supervisor


async def server(config: Config):
    workers: list[Coroutine] = list()

    sender_mapping = get_sender_mapping(config=config, workers=workers)

    # init ruler
    ruler_q = MsgQueue()
    ruler = Ruler(config=config, q=ruler_q, sender_mapping=sender_mapping)
    workers.append(ruler.worker())

    # init receivers
    receiver_smtpd = ReceiverSmtpd(config=config, ruler_q=ruler_q)
    workers.append(receiver_smtpd.worker_listen())
    workers.append(receiver_smtpd.worker_processer())

    receiver_webhook_q = MsgQueue()
    receiver_webhook = ReceiverWebhook(
        config=config, q=receiver_webhook_q, ruler_q=ruler_q
    )
    workers.append(receiver_webhook.worker_processer())

    # init http server
    http_server = HttpServer(config=config, webhook_q=receiver_webhook_q)
    workers.append(http_server.worker())

    # go start
    await worker_supervisor(workers)


def main(config: Config):
    # loguru
    if config.common.debug:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO
    logger.remove()
    logger.add(sys.stdout, level=logging_level)

    # logging
    # standard lib ---
    logging.getLogger("mail").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    # 3rd lib ---
    # --- receiver
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("aiosmtpd").setLevel(logging.WARNING)
    logging.getLogger("mailparser").setLevel(logging.WARNING)
    # --- sender
    logging.getLogger("apprise").setLevel(logging.WARNING)

    if config.common.sentry_dsn:
        try:
            import sentry_sdk
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

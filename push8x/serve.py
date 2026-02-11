import asyncio
import logging
import logging.config
import sys
from collections.abc import Coroutine
from logging import getLogger

from .config import Config
from .constans import SenderType
from .receiver.smtpd import ReceiverSmtpd
from .receiver.webhook import ReceiverWebhook
from .rule import RuleMatcher
from .sender.apprise import SenderApprise
from .sender.common import SenderQueueMapping
from .task import TaskQueue

logger = getLogger(__name__)


async def server(config: Config):
    workers: list[Coroutine] = list()

    # init senders
    sender_q_mapping: SenderQueueMapping = dict()
    sender_list = list()
    for sender in config.senders:
        sender_q = TaskQueue()

        match sender.type:
            case SenderType.APPRISE:
                sender_obj = SenderApprise(sender_q=sender_q)

            case _:
                raise

        sender_list.append(sender_obj)
        workers.append(sender_obj.worker())
        sender_q_mapping[sender.name] = sender_q

    # init rule matcher
    rule_matcher_q = TaskQueue()
    rule_matcher = RuleMatcher(
        config=config, q=rule_matcher_q, sender_q_mapping=sender_q_mapping
    )
    workers.append(rule_matcher.worker())

    # init receivers
    receiver_smtpd = ReceiverSmtpd(config=config, rule_matcher_q=rule_matcher_q)
    workers.append(receiver_smtpd.worker())

    receiver_webhook = ReceiverWebhook(config=config, rule_matcher_q=rule_matcher_q)
    workers.append(receiver_webhook.worker())

    print(
        f"正在启动服务 (HTTP: {config.server_http.host}:{config.server_http.port}, SMTP: {config.server_smtp.host}:{config.server_smtp.port}..."
    )
    await asyncio.gather(*workers)


def main(config: Config):
    if config.common.debug:
        logging_level = logging.DEBUG
    else:
        logging_level = logging.INFO

    logging.basicConfig(stream=sys.stdout, level=logging_level)
    logging.config.dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "loggers": {
                # standard lib
                "mail": {
                    "level": "WARNING",
                },
                "urllib3": {
                    "level": "WARNING",
                },
                # 3rd lib ---
                # --- receiver
                "uvicorn": {
                    "level": "WARNING",
                },
                "aiosmtpd": {
                    "level": "WARNING",
                },
                "mailparser": {
                    "level": "WARNING",
                },
                # --- sender
                "apprise": {
                    "level": "WARNING",
                },
            },
        }
    )

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

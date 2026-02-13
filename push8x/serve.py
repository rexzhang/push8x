import asyncio
import logging
import logging.config
import sys
from collections.abc import Coroutine
from logging import getLogger

from .config import Config
from .constans import MsgQueue, SenderType
from .receiver.smtpd import ReceiverSmtpd
from .receiver.webhook import ReceiverWebhook
from .rule import RuleMatcher
from .sender.apprise import SenderApprise
from .sender.balckhole import SenderBlackhold
from .sender.common import SenderQueueMapping

logger = getLogger(__name__)


async def supervisor(workers: list[Coroutine]):
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(worker) for worker in workers]

            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            first_task = done.pop()
            try:
                res = first_task.result()
                print(f"📢 [观测点] 第一个任务正常结束: {res}")
            except Exception as e:
                print(f"🚨 [观测点] 第一个任务异常结束: {e}")

            print("🛑 正在通知所有其他 Worker 退出...")
            for p in pending:
                p.cancel()

    except* Exception as eg:
        for e in eg.exceptions:
            if not isinstance(e, asyncio.CancelledError):
                print(f"⚠️ 捕获到子任务异常: {e}")

    print("\n[系统状态] 所有任务已清理。")


async def server(config: Config):
    workers: list[Coroutine] = list()

    # init senders
    sender_q_mapping: SenderQueueMapping = dict()
    sender_list = list()
    for sender in config.senders:
        sender_q = MsgQueue()

        match sender.type:
            case SenderType.BALCKHOLE:
                sender_obj = SenderBlackhold(sender_q=sender_q)
            case SenderType.APPRISE:
                sender_obj = SenderApprise(sender_q=sender_q)

            case _:
                raise

        sender_list.append(sender_obj)
        workers.append(sender_obj.worker())
        sender_q_mapping[sender.name] = sender_q

    # init rule matcher
    rule_matcher_q = MsgQueue()
    rule_matcher = RuleMatcher(
        config=config, q=rule_matcher_q, sender_q_mapping=sender_q_mapping
    )
    workers.append(rule_matcher.worker())

    # init receivers
    receiver_smtpd = ReceiverSmtpd(config=config, rule_matcher_q=rule_matcher_q)
    workers.append(receiver_smtpd.worker_recevier())
    workers.append(receiver_smtpd.worker_processer())

    receiver_webhook = ReceiverWebhook(config=config, rule_matcher_q=rule_matcher_q)
    workers.append(receiver_webhook.worker_recevier())

    print(
        f"正在启动服务 (HTTP: {config.server_http.host}:{config.server_http.port}, SMTP: {config.server_smtp.host}:{config.server_smtp.port}..."
    )

    await supervisor(workers)


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

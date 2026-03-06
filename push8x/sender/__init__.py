from collections.abc import Coroutine
from typing import TypeAlias

from ..config import Config
from ..constans import MsgQueue, SenderType
from .apprise import SenderApprise
from .balckhole import SenderBlackhole
from .smtp import SenderSmtp
from .webhook import SenderWebhook

Sender: TypeAlias = SenderBlackhole | SenderWebhook | SenderSmtp | SenderApprise
SenderMapping: TypeAlias = dict[str, Sender]


def get_sender_mapping(config: Config, workers: list[Coroutine]) -> SenderMapping:
    sender_mapping: SenderMapping = dict()
    for sender_config in config.senders:
        sender_q = MsgQueue()

        match sender_config.type:
            case SenderType.BALCKHOLE:
                sender_obj = SenderBlackhole(
                    sender_config=sender_config, sender_q=sender_q
                )
            case SenderType.WEBHOOK:
                sender_obj = SenderWebhook(
                    sender_config=sender_config, sender_q=sender_q
                )
            case SenderType.SMTP:
                sender_obj = SenderSmtp(sender_config=sender_config, sender_q=sender_q)
            case SenderType.APPRISE:
                sender_obj = SenderApprise(
                    sender_config=sender_config, sender_q=sender_q
                )

            case _:
                raise Exception("Codebase error: unknown sender type")

        sender_mapping[sender_config.name] = sender_obj
        workers.append(sender_obj.worker())

    return sender_mapping

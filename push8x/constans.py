from __future__ import annotations

from asyncio import Queue
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias

DEFAULT_CONFIG_FILENAME = "/etc/push8x.toml"
DEFAULT_WEBHOOK_HOST = "0.0.0.0"
DEFAULT_WEBHOOK_PORT = 8000
DEFAULT_SMTPD_HOST = "0.0.0.0"
DEFAULT_SMTPD_PORT = 8025


class ReceiverType(Enum):
    WEBHOOK = "webhook"
    SMTPD = "smtpd"


class SenderType(Enum):
    BALCKHOLE = "balckhole"
    WEBHOOK = "webhook"
    SMTP = "smtp"
    APPRISE = "apprise"


class MsgFromToType(Enum):
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"
    APPRISE = "APPRISE"


class MsgFromTo:
    type: MsgFromToType

    name: str
    value: str


class MsgContentType(Enum):
    PLAIN = "plain"
    HTML = "html"
    MARKDOWN = "markdown"


@dataclass(slots=True)
class Msg:
    # notification/message info
    from_name: str
    from_value: str
    to_name: str
    to_value: str

    title: str
    content: str
    content_format: MsgContentType

    ext: dict[str, Any]

    # control info
    receiver: ReceiverType
    # rule_id: int = field(init=False)


MsgQueue: TypeAlias = Queue[Msg]
SenderQueueMapping: TypeAlias = dict[str, MsgQueue]

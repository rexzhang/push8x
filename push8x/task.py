from asyncio import Queue
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeAlias

from .constans import ReceiverType


class FromToType(Enum):
    EMAIL = "EMAIL"
    WEBHOOK = "WEBHOOK"
    APPRISE = "APPRISE"


class FromTo:
    type: FromToType

    name: str
    email: str
    uri: str


class MessageContentType(Enum):
    PLAIN = "PLAIN"
    HTML = "HTML"
    MARKDOWN = "MARKDOWN"


@dataclass(slots=True)
class Task:
    # notification/message info
    f: str  # from
    t: str  # to

    title: str
    content: str
    content_format: MessageContentType

    ext: dict[str, Any]

    # control info
    receiver: ReceiverType
    # rule_id: int = field(init=False)


TaskQueue: TypeAlias = Queue[Task]

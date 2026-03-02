from __future__ import annotations

from asyncio import Queue
from dataclasses import dataclass, field
from enum import Enum
from http import HTTPStatus
from typing import Any, TypeAlias

DEFAULT_CONFIG_FILENAME = "/etc/push8x.toml"
DEFAULT_HTTP_BIND_HOST = "localhost"
DEFAULT_HTTP_BIND_PORT = 8000
DEFAULT_SMTPD_BIND_HOST = "localhost"
DEFAULT_SMTPD_BIND_PORT = 8025

HttpHeaders: TypeAlias = dict[str, str]  # key 小写化了的


@dataclass
class HttpServerResponse:
    status: HTTPStatus
    headers: list[bytes] = field(default_factory=lambda: [b"Content-Type: text/plain"])
    body: bytes = b""

    @property
    def bytes(self) -> bytes:
        status_line = f"HTTP/1.1 {self.status.value} {self.status.name}".encode()

        headers = [
            b"Content-Length: " + str(len(self.body)).encode(),
            b"Connection: close",
        ]
        headers.extend(self.headers)
        return b"\r\n".join([status_line] + headers) + b"\r\n\r\n" + self.body


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
    # control info
    receiver: ReceiverType
    mark: str

    # message(notification) info
    from_name: str
    from_value: str
    to_name: str
    to_value: str

    title: str
    content: str
    content_format: MsgContentType

    # ext info
    ext: dict[str, Any]


MsgQueue: TypeAlias = Queue[Msg]
SenderQueueMapping: TypeAlias = dict[str, MsgQueue]

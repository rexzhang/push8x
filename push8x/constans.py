from __future__ import annotations

from asyncio import Queue
from dataclasses import dataclass, field, fields
from enum import Enum
from http import HTTPStatus
from typing import Any, TypeAlias

from aiosmtpd.smtp import Session as AiosmtpdSession

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
    BALCKHOLE = "blackhole"
    WEBHOOK = "webhook"
    SMTP = "smtp"
    APPRISE = "apprise"


# rules ---


@dataclass
class Rule:
    sender_name: str

    enable: bool = True
    name: str = ""

    # special logic - check before other condition
    ignore_if_matched_other_rule: bool = False

    # skip_* logic ---
    # - None is mean ignore
    # - match ANYONE mean skip all
    skip_receiver: ReceiverType | None = None
    skip_receiver_mark: str | None = None

    skip_from_name: str | None = None
    skip_from_value: str | None = None
    skip_to_name: str | None = None
    skip_from_value: str | None = None
    skip_to_value: str | None = None
    skip_title: str | None = None

    # match_* logic ---
    # - None is mean ignore/ANY
    # - ONLY match ALL mean match
    match_receiver: ReceiverType | None = None
    match_receiver_mark: str | None = None

    match_from_name: str | None = None
    match_from_value: str | None = None
    match_to_name: str | None = None
    match_to_value: str | None = None
    match_title: str | None = None

    # special logic - only for matched msg
    ignore_other_rule_if_matched: bool = False

    # new_*(render) logic ---
    # for output new Msg, replace/template
    new_from_name: str | None = None
    new_from_value: str | None = None
    new_to_name: str | None = None
    new_to_value: str | None = None
    new_title: str | None = None
    new_content: str | None = None


RULS_SKIP_KEYS = (
    "receiver_mark",
    "from_name",
    "from_value",
    "to_name",
    "to_value",
    "title",
)
RULE_MATCH_KEYS = (
    "receiver_mark",
    "from_name",
    "from_value",
    "to_name",
    "to_value",
    "title",
)
RULE_NEW_KEYS = ("from_name", "from_value", "to_name", "to_value", "title", "content")


# Msg ---


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
class MsgBaseInfo:
    # message base info
    from_name: str
    from_value: str
    to_name: str
    to_value: str

    title: str
    content: str
    content_format: MsgContentType
    attachments: list[dict[str, Any]]

    # message ext info
    ext: dict[str, Any]


MSG_BASE_INFO_KEYS = [f.name for f in fields(MsgBaseInfo)]


@dataclass(slots=True)
class Msg(MsgBaseInfo):
    # receiver
    receiver: ReceiverType
    receiver_smtpd_session: AiosmtpdSession | None
    receiver_mark: str

    # ruler
    ruler_matched_rules: list[Rule]

    # sender
    # - ruler_matched_rules's Rule include sender_name


MsgQueue: TypeAlias = Queue[Msg]
SenderQueueMapping: TypeAlias = dict[str, MsgQueue]

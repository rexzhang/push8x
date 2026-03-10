import json
import re
from http import HTTPStatus
from typing import Any

from ..auth import AuthAbc
from ..config import Config
from ..constans import (
    HTTP_HEADER_KEY_AUTH_NAME,
    HTTP_HEADER_KEY_AUTH_TOKEN,
    MSG_BASE_INFO_KEYS,
    MSG_BASE_INFO_KEYS_NO_IN_WEBHOOK_REQUEST,
    MSG_BASE_INFO_KEYS_WEBHOOK_REQUIRED,
    HttpHeaders,
    HttpServerResponse,
    Msg,
    MsgContentFormat,
    MsgQueue,
    ReceiverType,
)
from ..worker import worker_guardian
from .common import ReceiverAbc


class ReceiverWebhookAuth(AuthAbc):
    receiver_type = ReceiverType.WEBHOOK

    @property
    def username_key(self) -> str:
        return "name"

    @property
    def password_key(self) -> str:
        return "token"

    def auth_http_header_or_path(
        self, headers: HttpHeaders, paths: list[bytes]
    ) -> tuple[bool, dict[str, Any]]:
        username = self._get_username(headers, paths)
        password = self._get_password(headers, paths)
        if username and password:
            return self.auth_str(username=username, password=password)

        return False, {}

    @staticmethod
    def _get_username(headers: HttpHeaders, paths: list[bytes]) -> str | None:
        try:
            name = paths[0].decode()
            return name
        except IndexError:
            pass

        name = headers.get(HTTP_HEADER_KEY_AUTH_NAME)
        if name:
            return name

        return None

    @staticmethod
    def _get_password(headers: HttpHeaders, paths: list[bytes]) -> str | None:
        try:
            token = paths[1].decode()
            return token
        except IndexError:
            pass

        match = re.search(
            r"^Bearer\s+(\S+)", headers.get("authorization", ""), re.IGNORECASE
        )
        if match:
            token = match.group(1)
            return token

        return None


def parse_webhook_request_body(
    body: bytearray, headers: HttpHeaders, auth_ext: dict[str, Any]
) -> tuple[Msg | None, HttpServerResponse]:
    try:
        data: dict[str, Any] = json.loads(body)
    except json.JSONDecodeError:
        return None, HttpServerResponse(
            HTTPStatus.BAD_REQUEST, body=b"invalid request body"
        )

    msg_base_info = dict()
    for k in MSG_BASE_INFO_KEYS:
        if k in MSG_BASE_INFO_KEYS_NO_IN_WEBHOOK_REQUEST:
            continue

        try:
            v = data.pop(k)
            msg_base_info[k] = v
        except KeyError:
            if k in MSG_BASE_INFO_KEYS_WEBHOOK_REQUIRED:
                return None, HttpServerResponse(
                    HTTPStatus.BAD_REQUEST, body=f"missing required field: {k}".encode()
                )

            msg_base_info[k] = ""

    content_format = msg_base_info.pop("content_format")
    if not isinstance(content_format, str):
        return None, HttpServerResponse(
            HTTPStatus.BAD_REQUEST, body=b"invalid content_format value"
        )
    else:
        content_format = content_format.upper()
    content_format = getattr(MsgContentFormat, content_format, MsgContentFormat.PLAIN)

    if HTTP_HEADER_KEY_AUTH_TOKEN in headers:
        headers[HTTP_HEADER_KEY_AUTH_TOKEN] = "***"

    try:
        msg = Msg(
            # msg
            **msg_base_info,
            content_format=content_format,
            attachments=list(),
            ext=data,
            # receiver
            receiver=ReceiverType.WEBHOOK,
            receiver_smtpd_session=None,
            receiver_webhook_headers=headers,
            receiver_ext=auth_ext,
            # ruler
            ruler_matched_rules=list(),
        )
    except TypeError as e:
        return None, HttpServerResponse(
            HTTPStatus.BAD_REQUEST, body=f"invalid msg: {e}".encode()
        )

    return msg, HttpServerResponse(HTTPStatus.OK)


class ReceiverWebhook(ReceiverAbc):
    @property
    def type(self) -> ReceiverType:
        return ReceiverType.WEBHOOK

    def __init__(self, config: Config, q: MsgQueue, ruler_q: MsgQueue) -> None:
        super().__init__(config, ruler_q)
        self.q = q

    @worker_guardian()
    async def worker_processer(self):
        while True:
            msg = await self.q.get()

            await self.ruler_q.put(msg)

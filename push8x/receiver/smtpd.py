import asyncio
import json
import re
from asyncio import Queue
from http import HTTPStatus
from logging import getLogger
from typing import Any, TypedDict

import mailparser
from aiosmtpd.proxy_protocol import ProxyData
from aiosmtpd.smtp import SMTP as SMTPAbc
from aiosmtpd.smtp import Envelope, Session
from rich import inspect

from ..auth import AuthAbc
from ..config import Config
from ..constans import (
    HttpHeaders,
    HttpServerResponse,
    Msg,
    MsgContentType,
    MsgQueue,
    ReceiverType,
)
from ..worker import worker_guardian
from .common import ReceiverAbc

logger = getLogger(__name__)


class ExtXclient(TypedDict):
    ADDR: str
    LOGIN: str
    NAME: str


class SMTP(SMTPAbc):

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("proxy_protocol_timeout", 3.0)  # for handle_PROXY

        super().__init__(*args, **kwargs)

    async def smtp_XCLIENT(self, arg):
        # "ADDR=1.2.3.4 LOGIN=user@me.com"
        ext_xclient: ExtXclient = dict(
            item.split("=", 1) for item in arg.split() if "=" in item
        )  # type: ignore

        setattr(self.session, "ext_xclient", ext_xclient)
        await self.push("250 OK")


class ReceiverSmtpdAuth(AuthAbc):
    """for http api"""

    def __init__(
        self, config: Config, accounts: list[Any], smtpd_host: str, smtpd_port: int
    ) -> None:
        super().__init__(accounts)
        self.config_receiver_smtpd = config.receiver.smtpd

        self.response_success_headers = [
            b"Auth-Status: OK",
            f"Auth-Server: {smtpd_host}".encode(),
            f"Auth-Port: {smtpd_port}".encode(),
        ]

        self.response_ip_blocked = HttpServerResponse(
            HTTPStatus.OK,
            [b"Auth-Status: Your IP address not in whitelist", b"Auth-Wait: 3"],
        )
        self.response_failed = HttpServerResponse(
            HTTPStatus.OK,
            [b"Auth-Status: Invalid login or password", b"Auth-Wait: 3"],
        )

    def check_headers(self, headers: HttpHeaders) -> HttpServerResponse:
        """https://nginx.org/en/docs/mail/ngx_mail_auth_http_module.html"""

        inspect(headers)

        # check sender_ip_whitelist
        if self.config_receiver_smtpd.sender_ip_whitelist and (
            headers.get("client-ip")
            not in self.config_receiver_smtpd.sender_ip_whitelist
        ):
            return self.response_ip_blocked

        # check username/password
        auth_user = headers.get("auth-user")
        auth_pass = headers.get("auth-pass")
        if auth_user is None or auth_pass is None:
            return self.response_failed

        auth_checked, auth_ext = self.check_str(username=auth_user, password=auth_pass)
        if auth_checked:
            return HttpServerResponse(
                HTTPStatus.OK,
                self.response_success_headers
                + [
                    f"Auth-User: {json.dumps(auth_ext, separators=(',', ':'))}".encode()
                ],
            )

        else:
            return self.response_failed


class SmtpdHandler:
    sender_name: str
    q: Queue[Msg]

    def __init__(self, config: Config, process_q: Queue) -> None:
        self.config_receiver_smtpd = config.receiver.smtpd
        self.q = process_q

    async def handle_PROXY(
        self,
        server: SMTP,
        session: Session,
        envelope: Envelope,
        ext_proxy_data: ProxyData,
    ):
        setattr(session, "ext_proxy_data", ext_proxy_data)
        return "250 OK"

    async def handle_DATA(self, server: SMTP, session: Session, envelope: Envelope):
        inspect(server)
        inspect(session)
        inspect(envelope)

        # parse mail
        mail: mailparser.MailParser = mailparser.parse_from_bytes(
            envelope.original_content
        )

        if not isinstance(mail.from_, list):
            raise Exception(mail.from_)
        from_name = mail.from_[0][0]
        from_value = mail.from_[0][1]

        if not isinstance(mail.to, list):
            raise Exception(mail.to)
        to_name = mail.to[0][0]
        to_value = mail.to[0][1]

        if not isinstance(mail.subject, str):
            raise Exception(mail.subject)
        title = mail.subject

        if len(mail.text_html) > 0:
            content = "".join(mail.text_html)
            content_format = MsgContentType.HTML
        else:
            content = "\n".join(mail.text_plain)
            content_format = MsgContentType.PLAIN

        # check some value
        ext_xclient: ExtXclient = getattr(session, "ext_xclient", None)  # type: ignore
        if ext_xclient is None:
            return "550 failed to get XCLIENT"  # TODO, support without nginx
        else:
            login_str = ext_xclient.get("LOGIN", None)
            if login_str is None:
                raise
            login_info: dict[str, Any] = json.loads(login_str)
            account_from_value = login_info.get("from_value")
            if account_from_value and account_from_value != from_value:
                return f"550 account from_value: {account_from_value} is not equal email from: {from_value}"

        if self.config_receiver_smtpd.from_value_regex:
            if (
                re.match(self.config_receiver_smtpd.from_value_regex, from_value)
                is None
            ):
                return f"550 email from: {from_value} not allowed"
        if self.config_receiver_smtpd.to_value_regex:
            if re.match(self.config_receiver_smtpd.to_value_regex, from_value) is None:
                return f"550 email to: {to_value} not allowed"

        logger.debug(f"Receiver smtpd: {from_value} => {to_value}")
        msg = Msg(
            from_name=from_name,
            from_value=from_value,
            to_name=to_name,
            to_value=to_value,
            title=title,
            content=content,
            content_format=content_format,
            ext=dict(),
            receiver=ReceiverType.SMTPD,
        )

        await self.q.put(msg)
        return "250 OK"


class ReceiverSmtpd(ReceiverAbc):
    q: Queue[Msg]

    @property
    def type(self) -> ReceiverType:
        return ReceiverType.SMTPD

    def __init__(self, config: Config, rule_matcher_q: MsgQueue) -> None:
        super().__init__(config, rule_matcher_q)

        self.q = Queue()

    @worker_guardian()
    async def worker_recevier(self):
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: SMTP(
                SmtpdHandler(config=self.config, process_q=self.q), enable_SMTPUTF8=True
            ),
            host=self.config.receiver.smtpd.bind.host,
            port=self.config.receiver.smtpd.bind.port,
        )
        async with server:
            logger.info(
                f"Starting {self.type} server on {self.config.receiver.smtpd.bind.host}:{self.config.receiver.smtpd.bind.port}"
            )
            await server.serve_forever()

    @worker_guardian()
    async def worker_processer(self):
        while True:
            msg = await self.q.get()

            await self.rule_matcher_q.put(msg)

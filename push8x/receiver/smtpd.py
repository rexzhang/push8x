import asyncio
import json
import re
import ssl
from asyncio import Queue
from http import HTTPStatus
from typing import Any, TypedDict

import mailparser
from aiosmtpd.proxy_protocol import ProxyData
from aiosmtpd.smtp import SMTP, AuthResult, Envelope, LoginPassword, Session
from loguru import logger
from rich import inspect
from rich.pretty import pprint

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

# ext_* are used to store additional data related to the SMTPd server

# SMTPd's auth function for behind proxy's HTTP auth ---


class ReceiverSmtpdHttpAuth(AuthAbc):
    receiver_type = ReceiverType.SMTPD

    def __init__(self, config: Config, smtpd_host: str, smtpd_port: int) -> None:
        super().__init__(config.receiver.smtpd.accounts)
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

        # inspect(headers, all=True)
        pprint(headers)

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


# SMTPd's auth function for direct SMTP AUTH


class ReceiverSmtpdAuthenticator:
    """Authenticator for aiosmtpd SMTP AUTH."""

    def __init__(self, accounts: list[Any]):
        self.auth = AuthAbc(accounts)

    def __call__(
        self, server, session, envelope, mechanism: str, auth_data
    ) -> AuthResult:
        fail_nothandled = AuthResult(success=False, handled=False)
        if mechanism not in ("LOGIN", "PLAIN"):
            return fail_nothandled
        if not isinstance(auth_data, LoginPassword):
            return fail_nothandled

        success, ext = self.auth.check(auth_data.login, auth_data.password)
        if success:
            # Store auth info in session for later use
            setattr(
                session,
                "ext_auth_data",
                {
                    **ext,
                    "username": auth_data.login.decode(),
                },
            )
            return AuthResult(success=True, handled=True)

        return AuthResult(success=False, handled=True)


# SMTPd service ---


class ExtXclient(TypedDict):
    ADDR: str
    LOGIN: str
    NAME: str


class ReceiverSmtpdSMTP(SMTP):

    def __init__(self, behind_proxy: bool, *args, **kwargs):
        if behind_proxy:
            # behind proxy, enable proxy protocol support
            logger.info("receiver.smtpd: `proxy protocol support` has been enabled")
            kwargs.setdefault("proxy_protocol_timeout", 3.0)

        super().__init__(*args, **kwargs)

    async def smtp_XCLIENT(self, arg):
        # "ADDR=1.2.3.4 LOGIN=user@me.com"
        ext_xclient: ExtXclient = dict(
            item.split("=", 1) for item in arg.split() if "=" in item
        )  # type: ignore

        setattr(self.session, "ext_xclient", ext_xclient)
        await self.push("250 OK")


class ReceiverSmtpdHandler:
    sender_name: str
    q: Queue[Msg]

    def __init__(self, config: Config, process_q: Queue) -> None:
        self.config_receiver_smtpd = config.receiver.smtpd
        self.q = process_q

    async def handle_PROXY(
        self,
        server: ReceiverSmtpdSMTP,
        session: Session,
        envelope: Envelope,
        ext_proxy_data: ProxyData,
    ):
        setattr(session, "ext_proxy_data", ext_proxy_data)
        return "250 OK"

    async def handle_DATA(
        self, server: ReceiverSmtpdSMTP, session: Session, envelope: Envelope
    ):
        inspect(session)

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

        attachments = []
        if mail.attachments:
            for attachment in mail.attachments:
                attachments.append(
                    {
                        "filename": attachment.get("filename"),
                        "content_type": attachment.get("mail_content_type"),
                        "content_transfer_encoding": attachment.get(
                            "content_transfer_encoding"
                        ),
                        "payload": attachment.get("payload"),
                    }
                )

        if self.config_receiver_smtpd.behind_proxy:
            # behind proxy
            ext_xclient: ExtXclient = getattr(session, "ext_xclient", None)  # type: ignore
            if ext_xclient is None:
                return "550 failed to get XCLIENT"

            else:
                login_str = ext_xclient.get("LOGIN", None)
                if login_str is None:
                    raise Exception("Codebase error: no LOGIN in ext_xclient")

                login_info: dict[str, Any] = json.loads(login_str)
                receiver_from_value = login_info.get("from_value")
                if receiver_from_value and receiver_from_value != from_value:
                    return f"550 receiver.smtpd.accounts from_value: {receiver_from_value} is not equal email from: {from_value}"

                receiver_mark = login_info.get("receiver_mark", "")

        else:
            # direct connection
            ext_auth_data: dict[str, Any] | None = getattr(
                session, "ext_auth_data", None
            )

            if ext_auth_data is None:
                # No authentication
                receiver_mark = ""

            else:
                # Authenticated via SMTP AUTH
                receiver_from_value = ext_auth_data.get("from_value")
                if receiver_from_value and receiver_from_value != from_value:
                    return f"550 receiver.smtpd.accounts from_value: {receiver_from_value} is not equal email from: {from_value}"
                receiver_mark = ext_auth_data.get("receiver_mark", "")

        # check from_value/to_value
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
            receiver=ReceiverType.SMTPD,
            receiver_smtpd_session=session,
            ruler_matched_rules=list(),
            from_name=from_name,
            from_value=from_value,
            to_name=to_name,
            to_value=to_value,
            title=title,
            content=content,
            content_format=content_format,
            attachments=attachments,
            ext=dict(),
            receiver_mark=receiver_mark,
        )

        await self.q.put(msg)
        return "250 OK"


class ReceiverSmtpd(ReceiverAbc):
    q: Queue[Msg]

    @property
    def type(self) -> ReceiverType:
        return ReceiverType.SMTPD

    def __init__(self, config: Config, ruler_q: MsgQueue) -> None:
        super().__init__(config, ruler_q)

        self.q = Queue()

        if config.receiver.smtpd.behind_proxy:
            self.authenticator = None
            self.tls_context = None

        else:
            # Create authenticator if accounts are configured
            accounts = self.config.receiver.smtpd.accounts
            self.authenticator = (
                ReceiverSmtpdAuthenticator(accounts) if accounts else None
            )

            # Create TLS context if cert/key are configured
            self.tls_context: ssl.SSLContext | None = None
            certfile = self.config.receiver.smtpd.starttls_certfile
            keyfile = self.config.receiver.smtpd.starttls_keyfile
            if certfile and keyfile:
                self.tls_context = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
                self.tls_context.load_cert_chain(certfile, keyfile)
                logger.info(f"receiver.smtpd: STARTTLS enabled with cert={certfile}")

    @worker_guardian(name="recevier:smtdp:listen")
    async def worker_listen(self):
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: ReceiverSmtpdSMTP(
                behind_proxy=self.config.receiver.smtpd.behind_proxy,
                # from orginal aiosmtpd.smtp.SMTP ---
                handler=ReceiverSmtpdHandler(config=self.config, process_q=self.q),
                enable_SMTPUTF8=True,
                tls_context=self.tls_context,
                auth_require_tls=self.tls_context is not None,
                auth_required=self.authenticator is not None,
                authenticator=self.authenticator,
            ),
            host=self.config.receiver.smtpd.bind.host,
            port=self.config.receiver.smtpd.bind.port,
        )
        async with server:
            behind_proxy = (
                "behind PROXY"
                if self.config.receiver.smtpd.behind_proxy
                else "not behind PROXY"
            )
            auth_info = "with AUTH" if self.authenticator else "without AUTH"
            tls_info = "with STARTTLS" if self.tls_context else "without STARTTLS"
            logger.info(
                f"{self.type} listen on {self.config.receiver.smtpd.bind.host}:{self.config.receiver.smtpd.bind.port} ({behind_proxy}, {auth_info}, {tls_info})"
            )
            await server.serve_forever()

    @worker_guardian(name="recevier:smtdp:processer")
    async def worker_processer(self):
        while True:
            msg = await self.q.get()

            await self.ruler_q.put(msg)

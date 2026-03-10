import asyncio
from http import HTTPMethod, HTTPStatus

from httptools import HttpParserError, HttpRequestParser, parse_url
from loguru import logger

from .config import Config
from .constans import HttpServerResponse, MsgQueue
from .receiver.smtpd import ReceiverSmtpdHttpAuth
from .receiver.webhook import ReceiverWebhookAuth, parse_webhook_request_body
from .worker import worker_guardian


class HttpServerProtocol(asyncio.Protocol):
    url: bytes
    headers: dict[str, str]
    body: bytearray

    def __init__(
        self,
        webhook_auth: ReceiverWebhookAuth,
        webhook_q: MsgQueue,
        smtpd_http_auth: ReceiverSmtpdHttpAuth,
    ):
        self.webhook_auth = webhook_auth
        self.webhook_q = webhook_q
        self.smtpd_http_auth = smtpd_http_auth

        self.parser = HttpRequestParser(self)

        self.url = b""
        self.headers = dict()
        self.body = bytearray(b"")

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        # put bytes stream into parser
        try:
            self.parser.feed_data(data)
        except HttpParserError:
            self.transport.close()

    def on_url(self, url: bytes):
        self.url = url

    def on_header(self, name: bytes, value: bytes):
        self.headers[name.decode().lower()] = value.decode()

    def on_body(self, body: bytes):
        self.body.extend(body)

    def on_message_complete(self):
        asyncio.create_task(self.handle_request())

    # http server process func ---
    async def handle_request(self):
        method = HTTPMethod(self.parser.get_method().decode())
        paths: list[bytes] = parse_url(self.url).path.strip(b"/").split(b"/")

        match method, paths:
            case HTTPMethod.GET, [b"api"]:
                response = HttpServerResponse(HTTPStatus.OK)

            case HTTPMethod.GET, [b"api", b"smtpd", b"auth"]:
                response = self._api_smtpd_auth()

            case HTTPMethod.GET, [b"api", b"webhooks", *rest]:
                response = HttpServerResponse(
                    HTTPStatus.METHOD_NOT_ALLOWED,
                    [b"Allow: POST", b"Content-Type: application/json"],
                )
            case HTTPMethod.POST, [b"api", b"webhooks", *rest]:
                response = await self._api_webhooks(paths=rest)

            case _:
                response = HttpServerResponse(HTTPStatus.NOT_FOUND)

        self.transport.write(response.bytes)  # type: ignore
        self.transport.close()

    def _api_smtpd_auth(self) -> HttpServerResponse:
        return self.smtpd_http_auth.auth_nginx_mail_auth_http(headers=self.headers)

    async def _api_webhooks(self, paths: list[bytes]) -> HttpServerResponse:
        # auth
        auth_success, auth_ext = self.webhook_auth.auth_http_header_or_path(
            headers=self.headers, paths=paths
        )
        if not auth_success:
            return HttpServerResponse(HTTPStatus.UNAUTHORIZED)

        # parse payload
        msg, response = parse_webhook_request_body(self.body, self.headers, auth_ext)
        if msg:
            await self.webhook_q.put(msg)

        return response


class HttpServer:
    config: Config
    webhook_auth: ReceiverWebhookAuth
    smtpd_http_auth: ReceiverSmtpdHttpAuth

    def __init__(self, config: Config, webhook_q: MsgQueue):
        self.config = config

        self.webhook_auth = ReceiverWebhookAuth(config.receiver.webhook.accounts)
        self.webhook_q = webhook_q

        self.smtpd_http_auth = ReceiverSmtpdHttpAuth(
            config=self.config,
            smtpd_host=config.receiver.smtpd.host,
            smtpd_port=config.receiver.smtpd.port,
        )

    @worker_guardian(name="server:httpd")
    async def worker(self):
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: HttpServerProtocol(
                self.webhook_auth, self.webhook_q, self.smtpd_http_auth
            ),
            self.config.http_server.bind.host,
            self.config.http_server.bind.port,
        )
        if self.webhook_auth.accounts:
            logger.info(
                f"{self.webhook_auth.receiver_type} enabled at: http://{self.config.http_server.bind.host}:{self.config.http_server.bind.port}/api/webhooks, accounts: {len(self.webhook_auth.accounts)}"
            )
        if self.smtpd_http_auth.accounts:
            logger.info(
                f"{self.smtpd_http_auth.receiver_type} HTTP Auth enabled at: http://{self.config.http_server.bind.host}:{self.config.http_server.bind.port}/api/smtpd/auth, accounts: {len(self.smtpd_http_auth.accounts)}"
            )
        async with server:
            await server.serve_forever()

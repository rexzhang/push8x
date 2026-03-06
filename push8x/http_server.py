import asyncio
from http import HTTPStatus  # HTTPMethod

from httptools import HttpParserError, HttpRequestParser, parse_url
from loguru import logger

from .config import Config
from .constans import HttpServerResponse, Msg, MsgContentType, MsgQueue, ReceiverType
from .receiver.smtpd import ReceiverSmtpdHttpAuth
from .receiver.webhook import ReceiverWebhookAuth
from .worker import worker_guardian


class HttpServerProtocol(asyncio.Protocol):
    # request info
    url: bytes
    headers: dict[str, str]
    body: bytearray

    def __init__(
        self,
        webhook_auth: ReceiverWebhookAuth,
        webhook_q: MsgQueue,
        smtpd_auth: ReceiverSmtpdHttpAuth,
    ):
        self.webhook_auth = webhook_auth
        self.webhook_q = webhook_q
        self.smtpd_auth = smtpd_auth

        self.parser = HttpRequestParser(self)
        # self.url = None
        self.headers = {}

    def connection_made(self, transport):
        self.transport = transport

    def data_received(self, data):
        # 将字节流喂给解析器
        try:
            self.parser.feed_data(data)
        except HttpParserError:
            self.transport.close()

    # --- httptools 回调函数 ---
    def on_url(self, url: bytes):
        self.url = url

    def on_header(self, name: bytes, value: bytes):
        self.headers[name.decode().lower()] = value.decode()

    def on_body(self, body: bytes):
        # 关键：body 可能会分多次到达，必须用 append/extend
        self.body.extend(body)

    def on_message_complete(self):
        # Protocol 是同步的，这里需要创建异步任务
        asyncio.create_task(self.handle_request())

    async def handle_request(self):
        paths: list[bytes] = parse_url(self.url).path.strip(b"/").split(b"/")

        match paths:
            case [b"api"]:
                response = HttpServerResponse(HTTPStatus.OK)

            case [b"api", b"smtpd", b"auth"]:
                response = self._api_smtpd_account_check()

            case [b"api", b"webhooks", *rest]:
                response = await self._api_webhooks(
                    method=self.parser.get_method(), paths=rest  # paths[2:]
                )

            case _:
                response = HttpServerResponse(HTTPStatus.NOT_FOUND)

        self.transport.write(response.bytes)  # type: ignore
        self.transport.close()

    def _api_smtpd_account_check(self) -> HttpServerResponse:
        return self.smtpd_auth.check_headers(headers=self.headers)

    async def _api_webhooks(
        self, method: bytes, paths: list[bytes]
    ) -> HttpServerResponse:
        if method != b"POST":
            return HttpServerResponse(
                HTTPStatus.METHOD_NOT_ALLOWED,
                [b"Allow: POST", b"Content-Type: application/json"],
            )

        auth_checked, auth_ext = self.webhook_auth.check(paths[0], paths[1])
        if not auth_checked:
            return HttpServerResponse(HTTPStatus.UNAUTHORIZED)

        await self.webhook_q.put(
            Msg(
                receiver=ReceiverType.WEBHOOK,
                receiver_smtpd_session=None,
                ruler_matched_rules=list(),
                from_name="",
                from_value="aaaa",
                to_name="",
                to_value="*@example.com",
                title="title",
                content="content",
                content_format=MsgContentType.PLAIN,
                attachments=list(),
                ext=dict(),
                receiver_mark="",
            )
        )
        return HttpServerResponse(HTTPStatus.OK)


class HttpServer:
    config: Config
    webhook_auth: ReceiverWebhookAuth
    smtpd_auth: ReceiverSmtpdHttpAuth

    def __init__(self, config: Config, webhook_q: MsgQueue):
        self.config = config

        self.webhook_auth = ReceiverWebhookAuth(config.receiver.webhook.endpoints)
        self.webhook_q = webhook_q

        self.smtpd_account = ReceiverSmtpdHttpAuth(
            config=self.config,
            accounts=config.receiver.smtpd.accounts,
            smtpd_host=config.receiver.smtpd.host,
            smtpd_port=config.receiver.smtpd.port,
        )

    @worker_guardian(name="server:http")
    async def worker(self):
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: HttpServerProtocol(
                self.webhook_auth, self.webhook_q, self.smtpd_account
            ),
            self.config.http_server.bind.host,
            self.config.http_server.bind.port,
        )
        logger.info(
            f"HTTP Server started at http://{self.config.http_server.bind.host}:{self.config.http_server.bind.port}"
        )
        async with server:
            await server.serve_forever()

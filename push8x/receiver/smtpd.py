import asyncio
from asyncio import Queue
from logging import getLogger

import mailparser
from aiosmtpd.smtp import SMTP, Envelope, Session

from ..config import Config
from ..constans import Msg, MsgContentType, MsgQueue, ReceiverType
from ..worker import worker_guardian
from .common import ReceiverAbc

logger = getLogger(__name__)


class SmtpdHandler:
    sender_name: str
    q: Queue[mailparser.MailParser]

    def __init__(self, process_q: Queue) -> None:
        self.q = process_q

    async def handle_DATA(self, server: SMTP, session: Session, envelope: Envelope):
        # TODO: 鉴权

        mail: mailparser.MailParser = mailparser.parse_from_bytes(
            envelope.original_content
        )

        await self.q.put(mail)
        return "250 OK"


class ReceiverSmtpd(ReceiverAbc):
    q: Queue[mailparser.MailParser]

    def __init__(self, config: Config, rule_matcher_q: MsgQueue) -> None:
        super().__init__(config, rule_matcher_q)

        self.type = ReceiverType.SMTPD
        self.q = Queue()

    @worker_guardian()
    async def worker_recevier(self):
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: SMTP(SmtpdHandler(self.q), enable_SMTPUTF8=True),
            host=self.config.server_smtp.host,
            port=self.config.server_smtp.port,
        )
        async with server:
            await server.serve_forever()

    @worker_guardian()
    async def worker_processer(self):
        while True:
            mail = await self.q.get()

            if not isinstance(mail.from_, list):
                raise Exception(mail.from_)
            f_name = mail.from_[0][0]
            f_value = mail.from_[0][1]

            if not isinstance(mail.to, list):
                raise Exception(mail.to)
            t_name = mail.to[0][0]
            t_value = mail.to[0][1]

            if not isinstance(mail.subject, str):
                raise Exception(mail.subject)
            title = mail.subject

            if len(mail.text_html) > 0:
                content = "".join(mail.text_html)
                content_format = MsgContentType.HTML
            else:
                content = "\n".join(mail.text_plain)
                content_format = MsgContentType.PLAIN

            logger.debug(f"Receiver smtpd: {f_value} => {t_value}")
            msg = Msg(
                f_name=f_name,
                f_value=f_value,
                t_name=t_name,
                t_value=t_value,
                title=title,
                content=content,
                content_format=content_format,
                ext=dict(),
                receiver=ReceiverType.SMTPD,
            )
            await self.rule_matcher_q.put(msg)

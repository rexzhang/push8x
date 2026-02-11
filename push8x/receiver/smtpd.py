import asyncio
from logging import getLogger

import mailparser
from aiosmtpd.smtp import SMTP, Envelope, Session

from ..config import Config
from ..constans import ReceiverType
from ..task import MessageContentType, Task, TaskQueue
from .common import ReceiverAbc

logger = getLogger(__name__)


# --- 2. SMTP 处理器 ---
class MailHandler:
    sender_name: str
    rule_matcher_q: TaskQueue

    def __init__(self, rule_matcher_q: TaskQueue) -> None:
        self.rule_matcher_q = rule_matcher_q

    async def handle_DATA(self, server: SMTP, session: Session, envelope: Envelope):
        mail: mailparser.MailParser = mailparser.parse_from_bytes(
            envelope.original_content
        )

        if not isinstance(mail.from_, list):
            raise Exception(mail.from_)
        f = mail.from_[0][1]

        if not isinstance(mail.to, list):
            raise Exception(mail.to)
        t = mail.to[0][1]

        if not isinstance(mail.subject, str):
            raise Exception(mail.subject)
        title = mail.subject

        logger.debug(f"Receiver smtpd: {f} => {t}")
        task = Task(
            f=f,
            t=t,
            title=title,
            content=str(mail.text_plain),
            content_format=MessageContentType.PLAIN,
            ext=dict(),
            receiver=ReceiverType.SMTPD,
        )
        await self.rule_matcher_q.put(task)
        return "250 OK"


class ReceiverSmtpd(ReceiverAbc):
    def __init__(self, config: Config, rule_matcher_q: TaskQueue) -> None:
        super().__init__(config, rule_matcher_q)

        self.type = ReceiverType.SMTPD

    async def worker(self):
        loop = asyncio.get_running_loop()
        server = await loop.create_server(
            lambda: SMTP(MailHandler(self.rule_matcher_q), enable_SMTPUTF8=True),
            host=self.config.server_smtp.host,
            port=self.config.server_smtp.port,
        )
        async with server:
            await server.serve_forever()

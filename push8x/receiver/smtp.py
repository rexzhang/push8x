import asyncio
from logging import getLogger

import mailparser

# from aiosmtpd.smtp import SMTP, Envelope, Session
from aiosmtpd import smtp

from ..config import Config
from ..constans import ReceiverType
from ..task import MessageContentType, Task, TaskQueue

logger = getLogger(__file__)


# --- 2. SMTP 处理器 ---
class MailHandler:
    sender_name: str
    rule_matcher_q: TaskQueue

    def __init__(self, rule_matcher_q: TaskQueue) -> None:
        self.rule_matcher_q = rule_matcher_q

    async def handle_DATA(
        self, server: smtp.SMTP, session: smtp.Session, envelope: smtp.Envelope
    ):
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
            receiver=ReceiverType.SMTP,
        )
        await self.rule_matcher_q.put(task)
        return "250 OK"


async def receiver_smtp_worker(config: Config, rule_matcher_q: TaskQueue):
    loop = asyncio.get_running_loop()
    # 使用底层的 create_server 避开 Controller 的线程开销
    server = await loop.create_server(
        lambda: smtp.SMTP(MailHandler(rule_matcher_q), enable_SMTPUTF8=True),
        host=config.server_smtp.host,
        port=config.server_smtp.port,
    )
    async with server:
        await server.serve_forever()

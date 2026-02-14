from email.message import EmailMessage
from logging import getLogger

import aiosmtplib

from ..config import SenderSmtp as SenderSmtpConfig
from ..constans import Msg, SenderType
from ..worker import worker_guardian
from .common import SenderAbc

logger = getLogger(__name__)


def get_email_from(msg: Msg) -> str:
    if msg.f_name and msg.f_value:
        return f"{msg.f_name} <{msg.f_value}>"
    elif msg.f_value:
        return msg.f_value
    else:
        return ""


def get_email_to(msg: Msg) -> str:
    if msg.t_name and msg.t_value:
        return f"{msg.t_name} <{msg.t_value}>"
    elif msg.t_value:
        return msg.t_value
    else:
        return ""


class SenderSmtp(SenderAbc):
    sender_config: SenderSmtpConfig  # type: ignore

    @property
    def type(self) -> SenderType:
        return SenderType.SMTP

    @worker_guardian()
    async def worker(self):
        while True:
            msg = await self.q.get()
            message = EmailMessage()
            message.set_content(msg.content)
            message["From"] = get_email_from(msg)
            message["To"] = get_email_to(msg)
            message["Subject"] = msg.title
            message.set_content(msg.content)

            await aiosmtplib.send(
                message,
                hostname=self.sender_config.host,
                port=self.sender_config.port,
                username=self.sender_config.username,
                password=self.sender_config.password,
                use_tls=self.sender_config.use_tls,
                start_tls=self.sender_config.start_tls,
            )

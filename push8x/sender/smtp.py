from email.message import EmailMessage

import aiosmtplib

from ..config import SenderSmtp as SenderSmtpConfig
from ..constans import Msg, SenderType
from ..worker import worker_guardian
from .common import SenderAbc


def get_email_from(msg: Msg) -> str:
    if msg.from_name and msg.from_value:
        return f"{msg.from_name} <{msg.from_value}>"
    elif msg.from_value:
        return msg.from_value
    else:
        return ""


def get_email_to(msg: Msg) -> str:
    if msg.to_name and msg.to_value:
        return f"{msg.to_name} <{msg.to_value}>"
    elif msg.to_value:
        return msg.to_value
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

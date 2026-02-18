import asyncio
import email.message
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any, overload

from aiosmtplib import SMTP
from dotenv import dotenv_values

_MISSING = object()


class EnvValue:
    data: dict[str, str]

    def __init__(self, env_path: str = ".env") -> None:
        base_env = os.environ.copy()
        file_env = dotenv_values(env_path)
        self.data = {k: v for k, v in {**base_env, **file_env}.items() if v is not None}

    @overload
    def get(self, k: str) -> str | None: ...

    @overload
    def get(self, k: str, default: str) -> str: ...

    def get(self, k: str, default: Any = _MISSING) -> str | None:
        value = self.data.get(k)
        if value is not None:
            return value

        if default is _MISSING:
            return None

        if default is None:
            raise ValueError(f"The default value for key '{k}' cannot be None.")

        return default

    def __repr__(self) -> str:
        import json

        return json.dumps(self.data, indent=2)


EV = EnvValue()


async def send_async_email(message: email.message.EmailMessage | email.message.Message):
    smtp_client = SMTP(
        hostname=EV.get("PUSH8X_SMTPD_HOST", "localhost"),
        port=int(EV.get("PUSH8X_SMTPD_PORT", "465")),
        use_tls=True,
    )

    async with smtp_client:
        await smtp_client.login(
            EV.get("PUSH8X_SMTPD_USER", "username"),
            EV.get("PUSH8X_SMTPD_PASS", "password"),
        )
        await smtp_client.send_message(message)
        print("邮件已异步发送成功！")


async def send_mails():
    message = MIMEMultipart()
    message["From"] = "Push8X Tester <noreply@h.rexzhang.com>"
    message["To"] = "rex.zhang@gmail.com"
    message["Subject"] = "Test SMTPd SSL"
    html_content = "<h1>你好！</h1><p>这是一封异步发送的 HTML 邮件。</p>"
    message.attach(MIMEText(html_content, "html", "utf-8"))
    await send_async_email(message)


if __name__ == "__main__":
    asyncio.run(send_mails())

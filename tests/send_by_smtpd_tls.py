import asyncio
import email.message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from os import getenv

from aiosmtplib import SMTP
from dotenv import load_dotenv


async def send_async_email(message: email.message.EmailMessage | email.message.Message):
    smtp_client = SMTP(
        hostname=getenv("PUSH8X_SMTPD_HOST", "localhost"),
        port=int(getenv("PUSH8X_SMTPD_PORT", 465)),
        use_tls=True,
    )

    async with smtp_client:
        await smtp_client.login(
            getenv("PUSH8X_SMTPD_USER", "username"),
            getenv("PUSH8X_SMTPD_PASS", "password"),
        )
        await smtp_client.send_message(message)
        print("邮件已异步发送成功！")


async def send_mails():
    message = MIMEMultipart()
    message["From"] = "Push8X Tester <sender@example.com>"
    message["To"] = "rex.zhang@gmail.com"
    message["Subject"] = "Test SMTPD SSL"
    html_content = "<h1>你好！</h1><p>这是一封异步发送的 HTML 邮件。</p>"
    message.attach(MIMEText(html_content, "html", "utf-8"))
    await send_async_email(message)


if __name__ == "__main__":
    load_dotenv()
    asyncio.run(send_mails())

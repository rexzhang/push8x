import asyncio
import email.message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from aiosmtplib import SMTP


async def send_async_email(message: email.message.EmailMessage | email.message.Message):
    # smtp_client = SMTP(hostname="smtp.example.com", port=465, use_tls=True)
    smtp_client = SMTP(hostname="127.0.01", port=8025, use_tls=False)

    async with smtp_client:
        # await smtp_client.login("sender@example.com", "your_auth_token")
        await smtp_client.send_message(message)
        print("邮件已异步发送成功！")


async def send_mails():
    # message = MIMEText("测试内容1")
    # message["Subject"] = "测试主题"
    # message["From"] = "Example Hu <sender@example.com>"
    # message["To"] = "receiver@example.com"
    # await send_async_email(message)

    # message = MIMEText("测试内容2")
    # message["Subject"] = "测试主题"
    # message["From"] = "<sender@example.com>"
    # message["To"] = "receiver@example.com"
    # await send_async_email(message)

    # message = MIMEText("测试内容3")
    # message["Subject"] = "测试主题"
    # message["From"] = "tester"
    # message["To"] = "receiver@example.com"
    # await send_async_email(message)

    # message = MIMEMultipart()
    # message["From"] = "sender@example.com"
    # message["To"] = "receiver@example.com"
    # message["Subject"] = "来自 Asyncio 的异步邮件"
    # html_content = "<h1>你好！</h1><p>这是一封异步发送的 HTML 邮件。</p>"
    # message.attach(MIMEText(html_content, "html", "utf-8"))
    # await send_async_email(message)

    message = MIMEMultipart()
    message["From"] = "Push8X Tester <sender@example.com>"
    message["To"] = "rex.zhang@gmail.com"
    message["Subject"] = "来自 Asyncio 的异步邮件"
    html_content = "<h1>你好！</h1><p>这是一封异步发送的 HTML 邮件。</p>"
    message.attach(MIMEText(html_content, "html", "utf-8"))
    await send_async_email(message)


# 运行异步任务
if __name__ == "__main__":
    asyncio.run(send_mails())

import smtplib
from email.mime.text import MIMEText

with smtplib.SMTP("127.0.0.1", 8025) as server:
    msg = MIMEText("测试内容")
    msg["Subject"] = "测试主题"
    msg["From"] = "Example Hu <sender@example.com>"
    msg["To"] = "recipient@example.com"
    # server.login("user", "pass") # 如果需要
    server.send_message(msg)

# with smtplib.SMTP("127.0.0.1", 8025) as server:
#     msg = MIMEText("测试内容")
#     msg["Subject"] = "测试主题"
#     msg["From"] = "<sender@example.com>"
#     msg["To"] = "recipient@example.com"
#     # server.login("user", "pass") # 如果需要
#     server.send_message(msg)

# with smtplib.SMTP("127.0.0.1", 8025) as server:
#     msg = MIMEText("测试内容")
#     msg["Subject"] = "测试主题"
#     msg["From"] = "tester"
#     msg["To"] = "recipient@example.com"
#     # server.login("user", "pass") # 如果需要
#     server.send_message(msg)

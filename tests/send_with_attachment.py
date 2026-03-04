import asyncio
import io
from email.message import EmailMessage

import aiosmtplib
from PIL import Image, ImageDraw, ImageFont


# --- 1. 定义一个生成图片二进制流的函数 ---
def create_image_in_memory():
    """使用 Pillow 生成图片并返回其二进制数据 (BytesIO)"""
    width, height = 400, 200
    # 生成一张带渐变色的背景 (简单的从左到右)
    image = Image.new("RGB", (width, height))
    draw = ImageDraw.Draw(image)

    for x in range(width):
        # 简单的算法生成蓝色到紫色的渐变
        r = int(x / width * 100)
        g = 50
        b = int(x / width * 255)
        draw.line((x, 0, x, height), fill=(r, g, b))

    # 添加一些文字，比如当前时间
    from datetime import datetime

    time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # 这里为了代码通用，使用默认字体 (实际建议加载 ttf)
    font = ImageFont.load_default()
    draw.text((10, 80), f"Generated at:\n{time_str}", fill="white", font=font)
    draw.text((10, 150), "Sent via aiosmtplib + Pillow", fill="lightgray", font=font)

    # --- 关键步骤：不保存到文件，而是保存到内存中 ---
    img_byte_arr = io.BytesIO()
    # 将图片对象以 PNG 格式保存到 BytesIO 对象中
    image.save(img_byte_arr, format="PNG")

    # 将指针移回流的开头，以便读取
    img_byte_arr.seek(0)

    # 返回原始二进制数据
    return img_byte_arr.read()


# --- 2. 定义异步发送邮件的函数 ---
async def send_dynamic_image_email():
    # A. 生成图片数据 (在内存中完成)
    print("正在生成动态图片...")
    image_data = create_image_in_memory()

    # B. 构建邮件
    message = EmailMessage()
    message["From"] = "system@example.com"
    message["To"] = "admin@example.com"
    message["Subject"] = "每日系统监控报告 (动态图片附件)"

    # 邮件正文
    message.set_content("您好，这是系统自动生成的即时状态图片，请查收附件。")

    # C. 添加图片附件 (核心部分)
    # 我们知道它是 PNG，所以 maintype='image', subtype='png'
    # filename 可以随便起，接收方会看到这个名字
    message.add_attachment(
        image_data, maintype="image", subtype="png", filename="status_report.png"
    )

    # D. 异步发送
    # 这里假设你的本地 SMTP 服务在 localhost:1025 (例如使用 MailHog)
    HOST = "127.0.0.1"
    PORT = 8025

    print(f"正在尝试连接 SMTP 服务器 {HOST}:{PORT} 发送邮件...")
    try:
        await aiosmtplib.send(
            message, hostname=HOST, port=PORT, use_tls=False  # 本地测试通常不用 TLS
        )
        print("邮件发送成功！(含内存生成的图片附件)")
    except Exception as e:
        print(f"邮件发送失败: {e}")


if __name__ == "__main__":
    # 在 Windows 上使用 aiohttp/aiosmtplib 建议使用此策略防止 Proactor 事件循环问题
    # import sys
    # if sys.platform == 'win32':
    #     asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    asyncio.run(send_dynamic_image_email())

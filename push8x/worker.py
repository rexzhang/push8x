import asyncio
import functools
import time
from logging import getLogger

logger = getLogger(__name__)


def worker_guardian(
    name: str | None = None,
    max_retries: int = 0,  # -1 表示无限重试
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            worker_name = name or getattr(self, "name", func.__name__)
            retries = 0
            start_time = time.time()

            while True:
                try:
                    logger.info(f"🚀 Worker [{worker_name}] 启动中...")
                    return await func(self, *args, **kwargs)

                except asyncio.CancelledError:
                    uptime = time.time() - start_time
                    logger.info(
                        f"🛑 Worker [{worker_name}] 已取消 (运行耗时: {uptime:.2f}s)"
                    )
                    raise  # 必须抛出以响应 asyncio 管理

                except Exception:
                    retries += 1
                    uptime = time.time() - start_time

                    # 关键点：使用 exception 记录完整堆栈
                    logger.exception(
                        f"💥 Worker [{worker_name}] 崩溃! "
                        f"已运行: {uptime:.2f}s, 重试次数: {retries}"
                    )

                    if max_retries != -1 and retries > max_retries:
                        logger.critical(
                            f"❌ Worker [{worker_name}] 达到最大重试限制，放弃运行。"
                        )
                        break

                    # 指数退避算法计算等待时间
                    delay = min(initial_delay * (2 ** (retries - 1)), max_delay)
                    logger.warning(
                        f"⏳ Worker [{worker_name}] 将在 {delay}s 后尝试重启..."
                    )
                    await asyncio.sleep(delay)

        return wrapper

    return decorator

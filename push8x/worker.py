import asyncio
import functools
import time
from collections.abc import Coroutine
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
            worker_name = name or getattr(self, "worker_name", func.__name__)
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


async def worker_supervisor(workers: list[Coroutine]):
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = [tg.create_task(worker) for worker in workers]

            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            first_task = done.pop()
            try:
                res = first_task.result()
                print(f"📢 [观测点] 第一个任务正常结束: {res}")
            except Exception as e:
                print(f"🚨 [观测点] 第一个任务异常结束: {e}")

            print("🛑 正在通知所有其他 Worker 退出...")
            for p in pending:
                p.cancel()

    except* Exception as eg:
        for e in eg.exceptions:
            if not isinstance(e, asyncio.CancelledError):
                print(f"⚠️ 捕获到子任务异常: {e}")

    print("\n[系统状态] 所有任务已清理。")

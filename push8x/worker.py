import asyncio
import functools
from collections.abc import Callable, Coroutine
from typing import Any

from loguru import logger


def worker_guardian(
    name: str | None = None,
    max_retries: int = 0,  # -1 means infinite retries
    initial_delay: float = 1.0,
    max_delay: float = 10.0,
):
    def decorator(func):
        @functools.wraps(func)
        async def wrapper(self, *args, **kwargs):
            worker_name = name or getattr(self, "worker_name", func.__name__)
            retries = 0

            while True:
                try:
                    logger.info(f"Worker [{worker_name}] starting...")
                    return await func(self, *args, **kwargs)

                except asyncio.CancelledError:
                    logger.info(f"Worker [{worker_name}] cancelled")
                    raise  # Must re-raise to respond to asyncio management

                except Exception:
                    retries += 1

                    # Key point: use exception to log full stack trace
                    logger.exception(
                        f"Worker [{worker_name}] crashed! retries: {retries}"
                    )

                    if max_retries != -1 and retries > max_retries:
                        logger.critical(
                            f"Worker [{worker_name}] reached max({max_retries}) retries, giving up."
                        )
                        break

                    # Exponential backoff algorithm to calculate wait time
                    delay = min(initial_delay * (2 ** (retries - 1)), max_delay)
                    logger.warning(f"Worker [{worker_name}] restarting in {delay}s...")
                    await asyncio.sleep(delay)

        wrapper.worker_name = name  # type: ignore
        return wrapper

    return decorator


async def worker_supervisor(workers: list[Callable[[], Coroutine[Any, Any, Any]]]):
    try:
        async with asyncio.TaskGroup() as tg:
            tasks = []
            for worker in workers:
                worker_name = getattr(worker, "worker_name", None)
                task = tg.create_task(worker(), name=worker_name)
                tasks.append(task)

            done, pending = await asyncio.wait(
                tasks, return_when=asyncio.FIRST_COMPLETED
            )

            first_task = done.pop()
            task_name = first_task.get_name()
            try:
                res = first_task.result()
                logger.error(
                    f"Worker Supervisor: worker [{task_name}] completed normally: {res}"
                )
            except Exception as e:
                logger.error(
                    f"Worker Supervisor: worker [{task_name}] ended with exception: {e}"
                )

            logger.warning("Worker Supervisor: notifying all other workers to exit...")
            for p in pending:
                p.cancel()

    except* Exception as eg:
        for e in eg.exceptions:
            if not isinstance(e, asyncio.CancelledError):
                logger.error(f"Worker Supervisor: Caught worker exception: {e}")

    logger.info("Worker Supervisor exiting.")

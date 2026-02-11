from logging import getLogger

import apprise

from ..task import Task, TaskQueue
from .common import SenderAbc

logger = getLogger(__name__)


class SenderApprise(SenderAbc):
    def __init__(self, sender_q: TaskQueue) -> None:
        super().__init__(sender_q=sender_q)

    def _do_task(self, task: Task):
        ap = apprise.Apprise()
        ap.add(task.t)
        ap.notify(body=task.content, title=task.title)

    async def worker(self):
        while True:
            task = await self.q.get()
            logger.debug(f"got task: {task}")
            self._do_task(task)

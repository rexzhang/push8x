import apprise

from push8x.sender.common import SenderAbc

from ..task import Task, TaskQueue


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
            self._do_task(task)

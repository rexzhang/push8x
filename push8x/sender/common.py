from typing import TypeAlias

from ..task import TaskQueue

SenderQueueMapping: TypeAlias = dict[str, TaskQueue]


class SenderAbc:
    q: TaskQueue

    def __init__(self, sender_q: TaskQueue) -> None:
        self.q = sender_q

    async def worker(self):
        raise NotImplementedError

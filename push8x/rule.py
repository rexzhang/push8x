import fnmatch
from logging import getLogger

from .config import Config, Rule
from .sender.common import SenderQueueMapping
from .task import Task, TaskQueue

logger = getLogger(__name__)


def match_sender_apply_rule_to_task(rules: list[Rule], task: Task):
    for rule in rules:
        # check match rule
        if rule.match_f is not None and not fnmatch.fnmatch(task.f, rule.match_f):
            continue

        if rule.match_t is not None and not fnmatch.fnmatch(task.t, rule.match_t):
            continue

        if rule.match_title is not None and not fnmatch.fnmatch(
            task.title, rule.match_title
        ):
            continue

        # convert task context
        if rule.new_f is not None:
            task.f = rule.new_f

        if rule.new_t is not None:
            task.t = rule.new_t

        # TODO:!!!
        # task.rule_id = 1

        # return
        yield rule.sender_name, task


class RuleMatcher:
    config: Config
    q: TaskQueue
    sender_q_mapping: SenderQueueMapping

    def __init__(
        self, config: Config, q: TaskQueue, sender_q_mapping: SenderQueueMapping
    ) -> None:
        self.config = config
        self.q = q
        self.sender_q_mapping = sender_q_mapping

    async def worker(self):
        # TODO: 3.13+ 使用 QueueShutDown
        while True:
            task = await self.q.get()
            logger.debug(f"got task: {task}")

            for sender_name, new_task in match_sender_apply_rule_to_task(
                self.config.rules, task
            ):
                sender_q = self.sender_q_mapping.get(sender_name)
                if sender_q is None:
                    raise

                await sender_q.put(new_task)

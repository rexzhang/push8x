import fnmatch
from logging import getLogger

from rich.pretty import pprint

from .config import Config, Rule
from .constans import Msg, MsgQueue
from .sender.common import SenderQueueMapping

logger = getLogger(__name__)


class RuleMatchAsyncProcessor:

    def __init__(self, rules: list[Rule], msg: Msg) -> None:
        self.rules = iter(rules)
        self.msg = msg

    def __aiter__(self):
        return self

    async def __anext__(self):
        rule_id = 0
        try:
            while True:
                rule_id += 1
                rule = next(self.rules)
                if not self._msg_match_receiver(rule):
                    continue

                if not self._msg_match_rule(rule):
                    continue

                return rule_id, rule, self._convert_msg_context(rule)

        except StopIteration:
            raise StopAsyncIteration

    def _msg_match_receiver(self, rule: Rule) -> bool:
        if rule.receiver is None:
            return True

        if self.msg.receiver == rule.receiver:
            return True

        return False

    def _msg_match_rule(self, rule) -> bool:
        if rule.match_f_value is not None and not fnmatch.fnmatch(
            self.msg.f_value, rule.match_f_value
        ):
            return False

        if rule.match_t_value is not None and not fnmatch.fnmatch(
            self.msg.t_value, rule.match_t_value
        ):
            return False

        if rule.match_title is not None and not fnmatch.fnmatch(
            self.msg.title, rule.match_title
        ):
            return False

        return True

    def _convert_msg_context(self, rule) -> Msg:
        if rule.new_f_value is not None:
            self.msg.f_value = rule.new_f_value

        if rule.new_t_value is not None:
            self.msg.t_value = rule.new_t_value

        # TODO:!!!
        # task.rule_id = 1
        return self.msg


class FallbackRuleMatchAsyncProcessor(RuleMatchAsyncProcessor):

    def _msg_match_rule(self, rule) -> bool:
        return True


class RuleMatcher:
    config: Config
    q: MsgQueue
    sender_q_mapping: SenderQueueMapping

    def __init__(
        self, config: Config, q: MsgQueue, sender_q_mapping: SenderQueueMapping
    ) -> None:
        self.config = config
        self.q = q
        self.sender_q_mapping = sender_q_mapping

    async def worker(self):
        # TODO: 3.13+ 使用 QueueShutDown
        while True:
            msg = await self.q.get()
            logger.debug(f"got Msg: {msg}")

            matched = False

            async for rule_id, rule, new_msg in RuleMatchAsyncProcessor(
                rules=self.config.rules, msg=msg
            ):
                sender_q = self.sender_q_mapping.get(rule.sender_name)
                if sender_q is None:
                    raise

                await sender_q.put(new_msg)

            if matched:
                continue

            async for rule_id, rule, new_msg in FallbackRuleMatchAsyncProcessor(
                rules=self.config.fallback_rules, msg=msg
            ):
                sender_q = self.sender_q_mapping.get(rule.sender_name)
                if sender_q is None:
                    raise

                await sender_q.put(new_msg)


async def rule_tester(config: Config, msg: Msg) -> None:
    matched = False

    print("Input Msg: ", end="")
    pprint(msg)

    async for rule_id, rule, new_msg in RuleMatchAsyncProcessor(
        rules=config.rules, msg=msg
    ):
        matched = True
        print("Matche Rule ---")
        print(f"#{rule_id}: ", end="")
        pprint(rule)
        print("Ouput Msg: ", end="")
        pprint(new_msg)

    if matched:
        return

    async for rule_id, rule, new_msg in FallbackRuleMatchAsyncProcessor(
        rules=config.fallback_rules, msg=msg
    ):
        print("Matche Fallback Rule ---")
        print(f"#{rule_id}: ", end="")
        pprint(rule)
        print("Ouput Msg: ", end="")
        pprint(new_msg)

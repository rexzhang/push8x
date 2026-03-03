import fnmatch

from loguru import logger
from rich.pretty import pprint

from .config import Config
from .constans import (
    RULE_MATCH_KEYS,
    RULE_NEW_KEYS,
    RULS_SKIP_KEYS,
    Msg,
    MsgQueue,
    Rule,
    SenderQueueMapping,
)
from .template import MsgTemplate
from .worker import worker_guardian


class RulerAsyncProcessor:
    msg_template = MsgTemplate()

    def __init__(self, rules: list[Rule], msg: Msg) -> None:
        self.rules = iter(rules)
        self.matched_rules: list[Rule] = list()
        self.msg = msg  # readonly
        self.done = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            while True:
                if self.done:
                    break

                rule = next(self.rules)
                if rule.enable is False:
                    continue

                if rule.ignore_if_matched_other_rule and self.matched_rules:
                    continue

                if self._skip_logic(rule):
                    continue

                if not self._match_logic(rule):
                    continue

                self.matched_rules.append(rule)
                new_msg = self._convert_msg_context(rule)
                new_msg.matched_rules = self.matched_rules

                if rule.ignore_other_rule_if_matched:
                    self.done = True

                print(1111)
                logger.info(
                    f"Ruler: msg:{self.msg}, match rule:{rule}, new msg:{new_msg}"
                )
                return new_msg

        except StopIteration:
            pass

        raise StopAsyncIteration

    def _skip_logic(self, rule: Rule) -> bool:
        if rule.skip_receiver is not None or rule.skip_receiver == self.msg.receiver:
            return True

        for k in RULS_SKIP_KEYS:
            msg_x = getattr(self.msg, k)
            rule_skip_x = getattr(rule, f"skip_{k}")
            if rule_skip_x is not None and fnmatch.fnmatch(msg_x, rule_skip_x):
                return True

        return False

    def _match_logic(self, rule: Rule) -> bool:
        if rule.match_receiver is not None and rule.match_receiver != self.msg.receiver:
            return False

        for k in RULE_MATCH_KEYS:
            msg_x = getattr(self.msg, k)
            rule_match_x = getattr(rule, f"match_{k}")
            if rule_match_x is not None and not fnmatch.fnmatch(msg_x, rule_match_x):
                return False

        return True

    def _convert_msg_context(self, rule: Rule) -> Msg:
        new_msg = self.msg  # TODO: deepcopy?

        for k in RULE_NEW_KEYS:
            new_x = getattr(rule, f"new_{k}")
            if new_x is not None:
                setattr(new_msg, k, self.msg_template.render(new_x, {"msg": self.msg}))

        return new_msg


class Ruler:
    config: Config
    q: MsgQueue
    sender_q_mapping: SenderQueueMapping

    def __init__(
        self, config: Config, q: MsgQueue, sender_q_mapping: SenderQueueMapping
    ) -> None:
        self.config = config
        self.q = q
        self.sender_q_mapping = sender_q_mapping

    @worker_guardian(name="ruler")
    async def worker(self):
        # TODO: 3.13+ 使用 QueueShutDown
        while True:
            msg = await self.q.get()
            logger.debug(f"got Msg: {msg}")

            async for new_msg in RulerAsyncProcessor(rules=self.config.rules, msg=msg):
                rule = new_msg.matched_rules[-1]
                sender_q = self.sender_q_mapping.get(rule.sender_name)
                if sender_q is None:
                    raise

                await sender_q.put(new_msg)


async def rule_tester(config: Config, msg: Msg) -> None:
    print("Input Msg: ", end="")
    pprint(msg)

    async for new_msg in RulerAsyncProcessor(rules=config.rules, msg=msg):
        rule = new_msg.matched_rules[-1]
        print("Matche Rule ---")
        print(f"RuleID:#{rule.name}, ", end="")
        pprint(rule)
        print("Ouput Msg: ", end="")
        pprint(new_msg)

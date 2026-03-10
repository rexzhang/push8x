import fnmatch
from copy import copy, deepcopy

from loguru import logger

from .config import Config
from .constans import (
    MSG_BASE_INFO_KEYS,
    RULE_MATCH_KEYS_MSG,
    RULE_MATCH_KEYS_RECEIVER,
    RULE_NEW_KEYS,
    RULS_SKIP_KEYS_MSG,
    RULS_SKIP_KEYS_RECEIVER,
    Msg,
    MsgQueue,
    Rule,
)
from .sender import Sender, SenderMapping
from .template import MsgTemplate
from .worker import worker_guardian


class RulerAsyncMatcher:

    def __init__(self, config: Config, msg: Msg, sender_mapping: SenderMapping) -> None:
        self.config_logging = config.logging
        self.rules = iter(config.rules)

        self.msg = msg
        self.msg_template = MsgTemplate()

        self.sender_mapping = sender_mapping

        self.matched_rules: list[Rule] = list()
        self.done = False

    def __aiter__(self):
        return self

    async def __anext__(self) -> tuple[Msg, Sender | None]:
        try:
            while True:
                if self.done:
                    break

                rule = next(self.rules)
                if rule.enable is False:
                    continue

                if rule.ignore_if_matched_other_rule and self.matched_rules:
                    continue

                # skip logic
                if (
                    rule.skip_receiver is not None
                    or rule.skip_receiver == self.msg.receiver
                ):
                    continue
                if self._skip_logic(rule, RULS_SKIP_KEYS_MSG):
                    continue
                if self._skip_logic(rule, RULS_SKIP_KEYS_RECEIVER, msg_base=False):
                    continue

                # match logic
                if (
                    rule.match_receiver is not None
                    and rule.match_receiver != self.msg.receiver
                ):
                    continue
                if not self._match_logic(rule, RULE_MATCH_KEYS_MSG):
                    continue
                if not self._match_logic(
                    rule, RULE_MATCH_KEYS_RECEIVER, msg_base=False
                ):
                    continue

                # make new_msg
                self.matched_rules.append(rule)
                new_msg = self._convert_msg_context(rule)
                new_msg.ruler_matched_rules = deepcopy(self.matched_rules)
                # get sender
                sender = self.sender_mapping.get(rule.sender_name)

                if rule.ignore_other_rule_if_matched:
                    self.done = True

                if self.config_logging.log_ruler_matched_msg:
                    logger.info(
                        f"Ruler: msg:{self.msg}, match rule:{rule}, new msg:{new_msg}"
                    )
                return new_msg, sender

        except StopIteration:
            pass

        raise StopAsyncIteration

    def _skip_logic(self, rule: Rule, keys: list[str], msg_base: bool = True) -> bool:
        for k in keys:
            if msg_base:
                msg_x = getattr(self.msg, k)
                rule_skip_x = getattr(rule, f"skip_{k}")
            else:
                msg_x = self.msg.receiver_ext.get(k, "")
                rule_skip_x = getattr(rule, f"skip_receiver_{k}")

            if rule_skip_x is not None and fnmatch.fnmatch(msg_x, rule_skip_x):
                return True

        return False

    def _match_logic(self, rule: Rule, keys: list[str], msg_base: bool = True) -> bool:
        for k in keys:
            if msg_base:
                msg_x = getattr(self.msg, k)
                rule_match_x = getattr(rule, f"match_{k}")
            else:
                msg_x = self.msg.receiver_ext.get(k, "")
                rule_match_x = getattr(rule, f"match_receiver_{k}")

            if rule_match_x is not None and not fnmatch.fnmatch(msg_x, rule_match_x):
                return False

        return True

    def _convert_msg_context(self, rule: Rule) -> Msg:
        # copy Msg object
        new_msg = copy(self.msg)
        for k in MSG_BASE_INFO_KEYS:
            setattr(new_msg, k, deepcopy(getattr(self.msg, k)))

        # render new_msg
        for k in RULE_NEW_KEYS:
            new_x = getattr(rule, f"new_{k}")
            if new_x is not None:
                setattr(new_msg, k, self.msg_template.render(new_x, {"msg": self.msg}))

        return new_msg


class Ruler:
    def __init__(
        self, config: Config, q: MsgQueue, sender_mapping: SenderMapping
    ) -> None:
        self.config = config
        self.q = q
        self.sender_mapping = sender_mapping

    @worker_guardian(name="ruler")
    async def worker(self):
        # TODO: 3.13+ 使用 QueueShutDown
        while True:
            msg = await self.q.get()
            logger.debug(f"got Msg: {msg}")

            matched = False
            async for new_msg, sender in RulerAsyncMatcher(
                config=self.config, msg=msg, sender_mapping=self.sender_mapping
            ):
                if sender is None:
                    raise Exception("Codebase error: sender_q is None")

                await sender.q.put(new_msg)
                matched = True

            if not matched and self.config.logging.log_ruler_droped_msg:
                logger.info(f"msg:{msg} dropped, no matched rule")


async def check_rules(config: Config, msg: Msg) -> list[tuple[Msg, Sender | None]]:
    result = list()
    async for new_msg, sender in RulerAsyncMatcher(
        config=config, msg=msg, sender_mapping=dict()
    ):
        result.append((new_msg, sender))

    return result

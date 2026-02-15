from __future__ import annotations

import tomllib
from dataclasses import KW_ONLY, dataclass, field
from logging import getLogger
from pathlib import Path
from typing import Any, TypeAlias

from dataclass_wizard import JSONPyWizard

from .constans import (
    DEFAULT_HTTP_HOST,
    DEFAULT_HTTP_PORT,
    DEFAULT_SMTPD_HOST,
    DEFAULT_SMTPD_PORT,
    ReceiverType,
    SenderType,
)

logger = getLogger(__name__)

# common ---


@dataclass
class Common:
    # dev
    debug: bool = False
    sentry_dsn: str = ""


@dataclass
class HttpServer:
    host: str = DEFAULT_HTTP_HOST
    port: int = DEFAULT_HTTP_PORT


# provider ---


@dataclass
class ProviderAbc:
    enable: bool = True
    name: str = field(init=False)

    def __post_init__(self):
        if not hasattr(self, "name"):
            self.name = self.type.value  # type: ignore


# --- receiver


@dataclass
class ReceiverAbc(ProviderAbc):
    pass


@dataclass
class ReceiverWebhookEndpoint:
    name: str  # 只能包含字母数字
    token: str


@dataclass
class ReceiverWebhook(ReceiverAbc):

    @property
    def type(self) -> ReceiverType:
        return ReceiverType.WEBHOOK

    base_path: str = "/webhooks"

    endpoints: list[ReceiverWebhookEndpoint] = field(default_factory=list)


@dataclass
class ReceiverSmtpdAccount:
    username: str
    password: str


@dataclass
class ReceiverSmtpd(ReceiverAbc):

    @property
    def type(self) -> ReceiverType:
        return ReceiverType.SMTPD

    host: str = DEFAULT_SMTPD_HOST
    port: int = DEFAULT_SMTPD_PORT

    accounts: list[ReceiverSmtpdAccount] = field(default_factory=list)


@dataclass
class ReceiverContainer:
    webhook: ReceiverWebhook = field(default_factory=ReceiverWebhook)
    smtpd: ReceiverSmtpd = field(default_factory=ReceiverSmtpd)


# senders ---


@dataclass
class SenderBlackhole(ProviderAbc, JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = SenderType.BALCKHOLE.value

    type: SenderType = SenderType.BALCKHOLE


@dataclass
class SenderWebhook(ProviderAbc, JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = SenderType.WEBHOOK.value

    type: SenderType = SenderType.WEBHOOK


@dataclass
class SenderSmtp(ProviderAbc, JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = SenderType.SMTP.value

    type: SenderType = SenderType.SMTP

    _: KW_ONLY
    host: str
    port: int
    username: str | None = None
    password: str | None = None
    use_tls: bool = False
    start_tls: bool | None = None

    default_email: str = "noreply@example.com"


@dataclass
class SenderApprise(ProviderAbc, JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = SenderType.APPRISE.value

    type: SenderType = SenderType.APPRISE


SenderConfig: TypeAlias = SenderBlackhole | SenderWebhook | SenderSmtp | SenderApprise

# rules/fallback_rules ---

RULE_NEW_KEYS = ("from_name", "from_value", "to_name", "to_value", "title", "content")


@dataclass
class Rule:
    sender_name: str

    # for match, None is mean ANY
    receiver: ReceiverType | None = None

    match_from_value: str | None = None
    match_to_value: str | None = None
    match_title: str | None = None

    # for output new Msg, replace/template
    new_from_name: str | None = None
    new_from_value: str | None = None
    new_to_name: str | None = None
    new_to_value: str | None = None

    new_title: str | None = None
    new_content: str | None = None


# config ---


@dataclass
class Config(JSONPyWizard):
    class Meta(JSONPyWizard.Meta):
        tag_key = "type"
        auto_assign_tags = False

    common: Common = field(default_factory=Common)
    http_server: HttpServer = field(default_factory=HttpServer)

    receiver: ReceiverContainer = field(default_factory=ReceiverContainer)

    senders: list[SenderBlackhole | SenderWebhook | SenderSmtp | SenderApprise] = field(
        default_factory=list
    )

    rules: list[Rule] = field(default_factory=list)
    fallback_rules: list[Rule] = field(default_factory=list)

    def _complete_config(self) -> None:
        # check senders ---
        has_sender_blackhole = False
        has_sender_apprise = False

        sender_names = set()
        for sender in self.senders:
            # --- check sender name
            if sender.name in sender_names:
                raise ValueError(f"sender name {sender.name} is duplicated")
            sender_names.add(sender.name)

            if isinstance(sender, SenderBlackhole):
                has_sender_blackhole = True
            elif isinstance(sender, SenderApprise):
                has_sender_apprise = True

        # --- add default senders
        if not has_sender_blackhole:
            self.senders.append(SenderBlackhole(type=SenderType.BALCKHOLE))
        if not has_sender_apprise:
            self.senders.append(SenderApprise(type=SenderType.APPRISE))


def generate_config_from_dict(
    data: dict[str, Any], complete_config: bool = True
) -> Config:
    config = Config.from_dict(data)
    if complete_config:
        config._complete_config()

    return config


def generate_config_from_file(
    filename: Path | str, complete_config: bool = True
) -> Config | None:
    try:
        with open(filename, "rb") as f:
            data = tomllib.load(f)

    except FileNotFoundError as e:
        logger.error(f"Can not open config file[{filename}]!, {e}")
        return None

    except tomllib.TOMLDecodeError as e:
        message = f"Load config from file[{filename}] failed!"
        logger.error(message)
        logger.error(e)
        return None

    config = generate_config_from_dict(data, complete_config)
    logger.info(f"Load config from file: [{filename}] success!")
    return config


_config_filename: Path | str | None = None
_config: Config


def reinit_config(
    filename: Path | str | None = None, complete_config: bool = True
) -> Config:
    global _config_filename
    global _config

    if filename is None:
        if _config_filename is None:
            raise
        else:
            filename = _config_filename
    else:
        _config_filename = filename

    data = generate_config_from_file(filename, complete_config)
    if data is None:
        data = Config()
    _config = data

    return _config


def __getattr__(name):
    if name == "config":
        global _config
        if _config_filename is None:
            _config = reinit_config()

        return _config

    raise AttributeError(f"module {__name__} has no attribute {name}")

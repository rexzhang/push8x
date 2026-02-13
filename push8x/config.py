from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from logging import getLogger
from pathlib import Path
from typing import Any

from dataclass_wizard import JSONPyWizard

from .constans import ReceiverType, SenderType

logger = getLogger(__name__)


@dataclass
class Common:
    debug: bool = False
    sentry_dsn: str = ""


@dataclass
class ServerSmtp:
    host: str = "127.0.0.1"
    port: int = 8025


@dataclass
class ServerHttp:
    host: str = "127.0.0.1"
    port: int = 8000
    base_path: str = "/webhhok"


@dataclass
class ReceiverSmtp(JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = ReceiverType.SMTPD.value

    enable: bool = True

    @property
    def name(self) -> str:
        return ReceiverType.SMTPD.value


@dataclass
class ReceiverWebhook(JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = ReceiverType.WEBHOOK.value

    name: str  # => /webhook/<name>, maybe call it: path
    token: str

    enable: bool = True


@dataclass
class SenderAbc:
    type: SenderType
    name: str = field(init=False)

    def __post_init__(self):
        if not hasattr(self, "name"):
            self.name = self.type.value


@dataclass
class SenderBlackhole(SenderAbc, JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = SenderType.BALCKHOLE.value

    enable: bool = True


@dataclass
class SenderWebhook(SenderAbc, JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = SenderType.WEBHOOK.value

    enable: bool = True


@dataclass
class SenderSmtp(SenderAbc, JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = SenderType.SMTP.value

    enable: bool = True
    default_email: str = "noreply@example.com"


@dataclass
class SenderApprise(SenderAbc, JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = SenderType.APPRISE.value

    enable: bool = True


@dataclass
class Rule:
    sender_name: str

    receiver: ReceiverType | None = None  # None is mean ANY

    match_f_value: str | None = None
    match_t_value: str | None = None
    match_title: str | None = None

    new_f_value: str | None = None
    new_t_value: str | None = None


@dataclass
class Config(JSONPyWizard):
    class Meta(JSONPyWizard.Meta):
        tag_key = "type"
        auto_assign_tags = False

    common: Common = field(default_factory=Common)

    server_smtp: ServerSmtp = field(default_factory=ServerSmtp)
    server_http: ServerHttp = field(default_factory=ServerHttp)

    receiver: list[ReceiverSmtp | ReceiverWebhook] = field(default_factory=list)

    senders: list[SenderBlackhole | SenderWebhook | SenderSmtp | SenderApprise] = field(
        default_factory=list
    )

    rules: list[Rule] = field(default_factory=list)
    fallback_rules: list[Rule] = field(default_factory=list)

    def _complete_config(self) -> None:
        # add default senders
        has_sender_blackhole = False
        has_sender_apprise = False
        for sender in self.senders:
            if isinstance(sender, SenderBlackhole):
                has_sender_blackhole = True
            elif isinstance(sender, SenderApprise):
                has_sender_apprise = True

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

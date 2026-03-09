from __future__ import annotations

import tomllib
from dataclasses import KW_ONLY, dataclass, field
from pathlib import Path
from typing import Any, TypeAlias

from dataclass_wizard import JSONPyWizard
from loguru import logger

from push8x.constans import Rule

from .constans import (
    DEFAULT_HTTP_BIND_HOST,
    DEFAULT_HTTP_BIND_PORT,
    DEFAULT_SMTPD_BIND_HOST,
    DEFAULT_SMTPD_BIND_PORT,
    ReceiverType,
    SenderType,
)

# common ---


@dataclass
class Common:
    # dev
    debug: bool = False
    sentry_dsn: str = ""


@dataclass
class Logging:
    log_ruler_matched_msg: bool = True
    log_ruler_droped_msg: bool = False


@dataclass
class Bind:
    host: str = DEFAULT_HTTP_BIND_HOST
    port: int = DEFAULT_HTTP_BIND_PORT


@dataclass
class HttpServer:
    bind: Bind = field(default_factory=Bind)


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

    endpoints: list[ReceiverWebhookEndpoint] = field(default_factory=list)


@dataclass
class ReceiverSmtpdAccount:
    username: str  # can be a email address or just a string
    password: str

    from_value: str | None = (
        None  # if is not None, will check email's from. TODO: support regex
    )
    mark: str = ""  # for ruler, if empty mean no mark


@dataclass
class ReceiverSmtpd(ReceiverAbc):

    @property
    def type(self) -> ReceiverType:
        return ReceiverType.SMTPD

    # deploy ---
    bind: Bind = field(
        default_factory=lambda: Bind(DEFAULT_SMTPD_BIND_HOST, DEFAULT_SMTPD_BIND_PORT)
    )
    # --- proxy protocol support
    behind_proxy: bool = False
    # announcement TODO: rename => report?
    host: str = DEFAULT_SMTPD_BIND_HOST
    port: int = DEFAULT_SMTPD_BIND_PORT

    # --- STARTTLS support
    starttls_certfile: str | None = None  # path to cert file
    starttls_keyfile: str | None = None  # path to key file

    # sender control ---
    # --- accounts
    accounts: list[ReceiverSmtpdAccount] = field(default_factory=list)

    # --- sender control
    sender_ip_whitelist: set[str] = field(default_factory=set)  # TODO
    from_value_regex: str | None = None
    to_value_regex: str | None = None


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

    default_email: str = "noreply@example.com"  # TODO:?


@dataclass
class SenderApprise(ProviderAbc, JSONPyWizard):
    class _(JSONPyWizard.Meta):
        tag = SenderType.APPRISE.value

    type: SenderType = SenderType.APPRISE


SenderConfig: TypeAlias = SenderBlackhole | SenderWebhook | SenderSmtp | SenderApprise

# config ---


@dataclass
class Config(JSONPyWizard):
    class Meta(JSONPyWizard.Meta):
        tag_key = "type"
        auto_assign_tags = False

    common: Common = field(default_factory=Common)
    logging: Logging = field(default_factory=Logging)

    http_server: HttpServer = field(default_factory=HttpServer)

    receiver: ReceiverContainer = field(default_factory=ReceiverContainer)

    senders: list[SenderBlackhole | SenderWebhook | SenderSmtp | SenderApprise] = field(
        default_factory=list
    )

    rules: list[Rule] = field(default_factory=list)

    def _complete_config(self) -> None:
        # senders ---
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

        # rules ---
        for index in range(len(self.rules)):
            # generate rule name if not set
            if self.rules[index].name == "":
                self.rules[index].name = f"R{index+1:03d}"


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

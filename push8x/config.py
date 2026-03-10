from __future__ import annotations

import tomllib
from dataclasses import KW_ONLY, dataclass, field
from pathlib import Path
from typing import Any, TypeAlias

from dataclass_wizard import JSONPyWizard
from loguru import logger

from push8x.constans import Rule

from .constans import (
    DEFAULT_HTTP_LISTEN_HOST,
    DEFAULT_HTTP_LISTEN_PORT,
    DEFAULT_SMTPD_LISTEN_HOST,
    DEFAULT_SMTPD_LISTEN_PORT,
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
class Listen:
    host: str = DEFAULT_HTTP_LISTEN_HOST
    port: int = DEFAULT_HTTP_LISTEN_PORT


@dataclass
class HttpServer:
    listen: Listen = field(default_factory=Listen)


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
class ReceiverWebhookAccount:
    # base info
    name: str  # 只能包含字母数字 TODO:内容检查
    token: str

    # ext info
    mark: str = ""  # for ruler, if empty mean no mark


@dataclass
class ReceiverWebhook(ReceiverAbc):

    @property
    def type(self) -> ReceiverType:
        return ReceiverType.WEBHOOK

    accounts: list[ReceiverWebhookAccount] = field(default_factory=list)


@dataclass
class ReceiverSmtpdAccount:
    # base info
    username: str  # can be a email address or just a string
    password: str

    # ext info
    mark: str = ""  # for ruler, if empty mean no mark

    # filter
    # if is not None, will check email's from. TODO: support regex
    from_value: str | None = None


@dataclass
class ReceiverSmtpd(ReceiverAbc):

    @property
    def type(self) -> ReceiverType:
        return ReceiverType.SMTPD

    # deploy ---
    listen: Listen = field(
        default_factory=lambda: Listen(
            DEFAULT_SMTPD_LISTEN_HOST, DEFAULT_SMTPD_LISTEN_PORT
        )
    )
    # --- proxy protocol support
    behind_proxy: bool = False
    listen_announce: Listen = field(
        default_factory=lambda: Listen(
            DEFAULT_SMTPD_LISTEN_HOST, DEFAULT_SMTPD_LISTEN_PORT
        )
    )

    # --- STARTTLS support
    starttls_certfile: str | None = None  # path to cert file
    starttls_keyfile: str | None = None  # path to key file

    # sender control ---
    # --- accounts
    accounts: list[ReceiverSmtpdAccount] = field(default_factory=list)

    # --- filter
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

    def _validate_config(self) -> list[str]:
        """Validate config logic and return list of warning messages.

        Returns:
            list[str]: List of warning messages (empty if no warnings)
        """
        warnings: list[str] = []

        # validate common ---
        if self.common.debug:
            warnings.append(
                "Debug mode is enabled, this should not be used in production"
            )

        # validate http_server ---
        if self.http_server.listen.port < 1 or self.http_server.listen.port > 65535:
            warnings.append(
                f"http_server port {self.http_server.listen.port} is out of valid range (1-65535)"
            )

        # validate receiver.smtpd ---
        smtpd = self.receiver.smtpd
        if smtpd.enable:
            # check listen port
            if smtpd.listen.port < 1 or smtpd.listen.port > 65535:
                warnings.append(
                    f"smtpd listen port {smtpd.listen.port} is out of valid range (1-65535)"
                )

            # check announce port
            if smtpd.listen_announce.port < 1 or smtpd.listen_announce.port > 65535:
                warnings.append(
                    f"smtpd announce port {smtpd.listen_announce.port} is out of valid range (1-65535)"
                )

            # check STARTTLS config
            has_starttls_cert = smtpd.starttls_certfile is not None
            has_starttls_key = smtpd.starttls_keyfile is not None
            if has_starttls_cert != has_starttls_key:
                warnings.append(
                    "smtpd STARTTLS config incomplete: both starttls_certfile and starttls_keyfile must be set together"
                )

            # check accounts
            usernames = set()
            for account in smtpd.accounts:
                if account.username in usernames:
                    warnings.append(
                        f"smtpd account username '{account.username}' is duplicated"
                    )
                usernames.add(account.username)

        # validate receiver.webhook ---
        webhook = self.receiver.webhook
        if webhook.enable:
            names = set()
            tokens = set()
            for account in webhook.accounts:
                if account.name in names:
                    warnings.append(
                        f"webhook account name '{account.name}' is duplicated"
                    )
                names.add(account.name)

                if account.token in tokens:
                    warnings.append(
                        f"webhook account token for '{account.name}' is duplicated"
                    )
                tokens.add(account.token)

        # validate senders ---
        for sender in self.senders:
            if not sender.enable:
                continue

            if isinstance(sender, SenderSmtp):
                # check port
                if sender.port < 1 or sender.port > 65535:
                    warnings.append(
                        f"sender[{sender.name}] port {sender.port} is out of valid range (1-65535)"
                    )

                # check TLS config
                if sender.use_tls and sender.start_tls:
                    warnings.append(
                        f"sender[{sender.name}] both use_tls and start_tls are enabled, this may cause issues"
                    )

        # validate rules ---
        rule_names = set()
        for i, rule in enumerate(self.rules):
            # check duplicate rule names
            if rule.name in rule_names:
                warnings.append(f"rule[{i}] name '{rule.name}' is duplicated")
            rule_names.add(rule.name)

            # check if sender exists
            sender_exists = any(s.name == rule.sender_name for s in self.senders)
            if not sender_exists:
                warnings.append(
                    f"rule[{rule.name}] references non-existent sender '{rule.sender_name}'"
                )

        return warnings


def generate_config_from_dict(
    data: dict[str, Any], complete_config: bool = True, validate_config: bool = True
) -> Config:
    config = Config.from_dict(data)
    if complete_config:
        config._complete_config()

    if validate_config:
        warnings = config._validate_config()
        for warning in warnings:
            logger.warning(f"Config validation: {warning}")

    return config


def generate_config_from_file(
    filename: Path | str, complete_config: bool = True, validate_config: bool = True
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

    config = generate_config_from_dict(data, complete_config, validate_config)
    logger.info(f"Load config from file: [{filename}] success!")
    return config


_config_filename: Path | str | None = None
_config: Config


def reinit_config(
    filename: Path | str | None = None,
    complete_config: bool = True,
    validate_config: bool = True,
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

    data = generate_config_from_file(filename, complete_config, validate_config)
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

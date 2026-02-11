from __future__ import annotations

from enum import Enum

DEFAULT_CONFIG_FILENAME = "/etc/push8x.toml"
DEFAULT_WEBHOOK_HOST = "0.0.0.0"
DEFAULT_WEBHOOK_PORT = 8000
DEFAULT_SMTPD_HOST = "0.0.0.0"
DEFAULT_SMTPD_PORT = 8025


class ReceiverType(Enum):
    SMTPD = "smtpd"
    WEBHOOK = "webhook"


class SenderType(Enum):
    SMTP = "smtp"
    WEBHOOK = "webhook"
    APPRISE = "apprise"

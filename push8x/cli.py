from pathlib import Path
from typing import Any

import typer

from .constans import (
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_SMTPD_HOST,
    DEFAULT_SMTPD_PORT,
    DEFAULT_WEBHOOK_HOST,
    DEFAULT_WEBHOOK_PORT,
)
from .server import main as server_main

app = typer.Typer()


class State:
    def __init__(self):
        self.config_filename: Path | None = None


state = State()


@app.callback()
def main(
    config: Path = typer.Option(
        Path(DEFAULT_CONFIG_FILENAME),
        "--config",
        "-c",
        help="Configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
    )
):
    state.config_filename = config


@app.command()
def serve(
    webhook_host: str = typer.Option(DEFAULT_WEBHOOK_HOST, help="webhook bind host"),
    webhook_port: int = typer.Option(DEFAULT_WEBHOOK_PORT, help="webhook bind port"),
    smtpd_host: str = typer.Option(DEFAULT_SMTPD_HOST, help="smtpd bind host"),
    smtpd_port: int = typer.Option(DEFAULT_SMTPD_PORT, help="smtpd bind port"),
) -> Any:
    from .config import reinit_config

    reinit_config(state.config_filename)

    from .config import config

    config.server_http.host = webhook_host
    config.server_smtp.host = smtpd_host
    server_main(config)

import asyncio
from pathlib import Path
from typing import Any

import typer
from rich.pretty import pprint

from .config import reinit_config
from .constans import (
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_SMTPD_HOST,
    DEFAULT_SMTPD_PORT,
    DEFAULT_WEBHOOK_HOST,
    DEFAULT_WEBHOOK_PORT,
    Msg,
    MsgContentType,
    ReceiverType,
)
from .rule import rule_tester
from .serve import main as serve_main

app = typer.Typer()


class State:
    def __init__(self):
        self.config_filename: Path | None = None


state = State()


@app.callback()
def main(
    config_filename: Path = typer.Option(
        Path(DEFAULT_CONFIG_FILENAME),
        "--config",
        "-c",
        help="Configuration file",
        exists=True,
        file_okay=True,
        dir_okay=False,
    )
):
    state.config_filename = config_filename


@app.command()
def serve(
    webhook_host: str = typer.Option(DEFAULT_WEBHOOK_HOST, help="webhook bind host"),
    webhook_port: int = typer.Option(DEFAULT_WEBHOOK_PORT, help="webhook bind port"),
    smtpd_host: str = typer.Option(DEFAULT_SMTPD_HOST, help="smtpd bind host"),
    smtpd_port: int = typer.Option(DEFAULT_SMTPD_PORT, help="smtpd bind port"),
) -> Any:
    reinit_config(state.config_filename)
    from .config import config

    config.server_http.host = webhook_host
    config.server_smtp.host = smtpd_host
    serve_main(config)


@app.command()
def configchecker() -> Any:
    """Config check tool."""
    reinit_config(state.config_filename)
    from .config import config

    pprint(config)


@app.command()
def ruletester(
    f_name: str = typer.Option("Sender Man"),
    f_value: str = typer.Option("sender@example.com"),
    t_name: str = typer.Option("Receiver Man"),
    t_value: str = typer.Option("receiver@example.com"),
    title: str = typer.Option("Push8X test mail"),
    content: str = typer.Option("This is a test mail from Push8X"),
    content_format: MsgContentType = typer.Option(MsgContentType.PLAIN),
    receiver: ReceiverType = typer.Option(ReceiverType.SMTPD),
) -> Any:
    """Rule Matcher test tool."""
    reinit_config(state.config_filename)
    from .config import config

    msg = Msg(
        f_name=f_name,
        f_value=f_value,
        t_name=t_name,
        t_value=t_value,
        title=title,
        content=content,
        content_format=content_format,
        ext=dict(),
        receiver=receiver,
    )

    asyncio.run(rule_tester(config, msg))

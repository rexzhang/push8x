import asyncio
from pathlib import Path
from typing import Any

import rich
import typer

from .config import reinit_config
from .constans import (
    DEFAULT_CONFIG_FILENAME,
    DEFAULT_HTTP_LISTEN_HOST,
    DEFAULT_HTTP_LISTEN_PORT,
    DEFAULT_SMTPD_LISTEN_HOST,
    DEFAULT_SMTPD_LISTEN_PORT,
    Msg,
    MsgContentFormat,
    ReceiverType,
)
from .ruler import check_rules
from .serve import main as serve_main

app = typer.Typer()
check_app = typer.Typer()
app.add_typer(check_app, name="check")


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
    http_listen_host: str = typer.Option(
        DEFAULT_HTTP_LISTEN_HOST, help="http server listen host"
    ),
    http_listen_port: int = typer.Option(
        DEFAULT_HTTP_LISTEN_PORT, help="http server listen port"
    ),
    smtpd_listen_host: str = typer.Option(
        DEFAULT_SMTPD_LISTEN_HOST, help="smtpd server listen host"
    ),
    smtpd_listen_port: int = typer.Option(
        DEFAULT_SMTPD_LISTEN_PORT, help="smtpd server listen port"
    ),
) -> Any:
    reinit_config(state.config_filename)
    from .config import config

    config.http_server.listen.host = http_listen_host
    config.http_server.listen.port = http_listen_port
    config.receiver.smtpd.listen.host = smtpd_listen_host
    config.receiver.smtpd.listen.port = smtpd_listen_port
    serve_main(config)


@check_app.command("config")
def cli_check_config() -> Any:
    """Config check tool."""
    reinit_config(state.config_filename)
    from .config import config

    rich.print(config)


@check_app.command("rules")
def cli_check_rules(
    from_name: str = typer.Option("Sender Man"),
    from_value: str = typer.Option("sender@example.com"),
    to_name: str = typer.Option("Receiver Man"),
    to_value: str = typer.Option("receiver@example.com"),
    title: str = typer.Option("Push8X test mail"),
    content: str = typer.Option("This is a test mail from Push8X"),
    content_format: MsgContentFormat = typer.Option(MsgContentFormat.PLAIN),
    receiver: ReceiverType = typer.Option(ReceiverType.SMTPD),
    mark: str = typer.Option(""),
) -> None:
    reinit_config(state.config_filename)
    from .config import config

    msg = Msg(
        # msg
        from_name=from_name,
        from_value=from_value,
        to_name=to_name,
        to_value=to_value,
        title=title,
        content=content,
        content_format=content_format,
        attachments=list(),
        ext=dict(),
        # receiver
        receiver=receiver,
        receiver_smtpd_session=None,
        receiver_webhook_headers=None,
        receiver_ext=dict(),
        # ruler
        ruler_matched_rules=list(),
    )

    result = asyncio.run(check_rules(config, msg))
    rich.print("Input Msg:", msg)
    for new_msg in result:
        rich.print("Output Msg:", new_msg)

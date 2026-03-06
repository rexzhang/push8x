"""Tests for ruler.check_rules() using TOML config files from examples/test_ruler."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest
from deepdiff import DeepDiff

from push8x.config import generate_config_from_file
from push8x.constans import Msg, MsgContentType, ReceiverType, Rule
from push8x.ruler import check_rules
from push8x.sender import Sender


@dataclass(frozen=True)
class RulerTestParams:
    """Parameters for ruler tests - stores paths for lazy loading."""

    config_path: Path
    test_file: Path


# --- Helper ---


def dict_to_msg(data: dict) -> Msg:
    """Convert dict to Msg instance."""
    receiver_type = (
        ReceiverType.SMTPD
        if data.get("receiver", "smtpd") == "smtpd"
        else ReceiverType.WEBHOOK
    )
    return Msg(
        receiver=receiver_type,
        receiver_smtpd_session=None,
        ruler_matched_rules=[],
        from_name=data.get("from_name", "Sender"),
        from_value=data.get("from_value", "sender@example.com"),
        to_name=data.get("to_name", "Recipient"),
        to_value=data.get("to_value", "recipient@example.com"),
        title=data.get("title", "Test Subject"),
        content=data.get("content", "Test content"),
        content_format=MsgContentType.PLAIN,
        attachments=data.get("attachments", []),
        ext=data.get("ext", {}),
        receiver_mark=data.get("receiver_mark", ""),
    )


def rule_to_dict(rule: Rule) -> dict:
    """Convert Rule to dict for comparison."""
    return {
        "sender_name": rule.sender_name,
        "enable": rule.enable,
        "name": rule.name,
        "ignore_if_matched_other_rule": rule.ignore_if_matched_other_rule,
        "skip_receiver": rule.skip_receiver.value if rule.skip_receiver else None,
        "skip_receiver_mark": rule.skip_receiver_mark,
        "skip_from_name": rule.skip_from_name,
        "skip_from_value": rule.skip_from_value,
        "skip_to_name": rule.skip_to_name,
        "skip_to_value": rule.skip_to_value,
        "skip_title": rule.skip_title,
        "match_receiver": rule.match_receiver.value if rule.match_receiver else None,
        "match_receiver_mark": rule.match_receiver_mark,
        "match_from_name": rule.match_from_name,
        "match_from_value": rule.match_from_value,
        "match_to_name": rule.match_to_name,
        "match_to_value": rule.match_to_value,
        "match_title": rule.match_title,
        "ignore_other_rule_if_matched": rule.ignore_other_rule_if_matched,
        "new_from_name": rule.new_from_name,
        "new_from_value": rule.new_from_value,
        "new_to_name": rule.new_to_name,
        "new_to_value": rule.new_to_value,
        "new_title": rule.new_title,
        "new_content": rule.new_content,
    }


def msg_to_dict(msg: Msg) -> dict:
    """Convert Msg to dict for comparison."""
    return {
        "from_name": msg.from_name,
        "from_value": msg.from_value,
        "to_name": msg.to_name,
        "to_value": msg.to_value,
        "title": msg.title,
        "content": msg.content,
        "content_format": msg.content_format.value,
        "attachments": msg.attachments,
        "ext": msg.ext,
        "receiver": msg.receiver.value,
        "receiver_mark": msg.receiver_mark,
        "ruler_matched_rules": [rule_to_dict(r) for r in msg.ruler_matched_rules],
    }


def result_to_json_format(result: list[tuple[Msg, Sender | None]]) -> list:
    """Convert check_rules result to JSON-serializable format for comparison."""
    return [[msg_to_dict(msg), sender] for msg, sender in result]


def get_test_paths(base_path: str | Path, test_data_file_wildcard: str) -> list[Path]:
    """
    递归检查目录，寻找同时包含 push8x.toml 和 test_ruler_*.json 的子目录。
    """
    base_dir = Path(base_path)
    matched_dirs = []

    if not base_dir.is_dir():
        return matched_dirs

    for toml_file in base_dir.rglob("push8x.toml"):
        parent_dir = toml_file.parent
        has_test_ruler_json = (
            next(parent_dir.glob(test_data_file_wildcard), None) is not None
        )
        if has_test_ruler_json:
            matched_dirs.append(parent_dir)

    return matched_dirs


def get_parametrize_args() -> tuple:
    """Get parametrize arguments for pytest.mark.parametrize."""
    return "params", get_parametrize()


def get_parametrize() -> tuple:
    """Get parametrize arguments for pytest.mark.parametrize.
    Returns (argnames, argvalues) tuple.
    """
    test_data_file_wildcard = "test_ruler_*.json"

    pytest_data = list()
    for test_path in get_test_paths(
        base_path=Path(__file__).parent.parent / "examples",
        test_data_file_wildcard=test_data_file_wildcard,
    ):
        config_path = test_path.joinpath("push8x.toml")

        for test_file in sorted(test_path.glob(test_data_file_wildcard)):
            pytest_data.append(
                pytest.param(
                    RulerTestParams(
                        config_path=config_path,
                        test_file=test_file,
                    ),
                    id=f"{test_path.name}::{test_file.stem}",
                )
            )

    return ("params", pytest_data)


# --- Parametrized Tests ---


@pytest.mark.asyncio
@pytest.mark.parametrize(*get_parametrize())
async def test_from_examples(params: RulerTestParams):
    # Load test data from JSON
    with open(params.test_file, encoding="utf-8") as f:
        json_data = json.load(f)

    # Load config
    config = generate_config_from_file(params.config_path)
    assert config is not None, f"Failed to load config from {params.config_path}"

    # Convert input message
    input_msg = dict_to_msg(json_data["input_msg"])

    # Run check_rules
    result = await check_rules(config, input_msg)
    result_json = result_to_json_format(result)

    # Compare with expected output
    diff = DeepDiff(result_json, json_data["output_result"], ignore_order=False)
    assert not diff, f"DeepDiff found differences: {diff}"

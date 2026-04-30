"""Tests for KnotConfig id character validation (security finding L-9)."""

import pytest
from pydantic import ValidationError

from pirn.core.knot_config import KnotConfig


def make_config(id: str) -> KnotConfig:
    return KnotConfig(id=id)


@pytest.mark.parametrize(
    "valid_id",
    [
        "my-knot",
        "etl.load.users",
        "param:x",
        "knot_123",
        "a",
        "A-B.C:D_1",
    ],
)
def test_valid_ids(valid_id: str) -> None:
    config = make_config(valid_id)
    assert config.id == valid_id


def test_invalid_null_byte() -> None:
    with pytest.raises(ValidationError):
        make_config("knot\x00id")


def test_invalid_newline() -> None:
    with pytest.raises(ValidationError):
        make_config("knot\nid")


def test_invalid_path_separator() -> None:
    with pytest.raises(ValidationError):
        make_config("knot/id")


def test_invalid_space() -> None:
    with pytest.raises(ValidationError):
        make_config("knot id")


def test_invalid_ansi_escape() -> None:
    with pytest.raises(ValidationError):
        make_config("knot\x1b[31mid")


def test_invalid_too_long() -> None:
    with pytest.raises(ValidationError):
        make_config("a" * 257)


def test_empty_string_rejected() -> None:
    with pytest.raises(ValidationError):
        make_config("")

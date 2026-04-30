"""Unit tests for SubTapestry construction and error semantics."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_result import RunResult
from pirn.nodes.sub_tapestry import SubTapestry, SubTapestryError


class _DoublerPipeline(SubTapestry):
    async def process(self, value: int, **_: Any) -> RunResult:
        raise NotImplementedError  # never called in unit tests


class _TwoPInputPipeline(SubTapestry):
    async def process(self, a: int, b: str, **_: Any) -> RunResult:
        raise NotImplementedError


# -------------------------------------------------------- taxonomy


def test_sub_tapestry_is_a_knot_subclass():
    assert issubclass(SubTapestry, Knot)


def test_concrete_sub_tapestry_is_a_knot_instance():
    p = Parameter("v", int, default=1)
    sub = _DoublerPipeline(value=p, _config=KnotConfig(id="sub"))
    assert isinstance(sub, Knot)
    assert isinstance(sub, SubTapestry)


# -------------------------------------------------------- construction


def test_construction_sets_knot_id():
    p = Parameter("v", int, default=1)
    sub = _DoublerPipeline(value=p, _config=KnotConfig(id="my-sub"))
    assert sub.knot_id == "my-sub"


def test_knot_parent_wired_correctly():
    p = Parameter("v", int)
    sub = _DoublerPipeline(value=p, _config=KnotConfig(id="sub"))
    assert sub.parents["value"] is p


def test_config_value_stored():
    sub = _DoublerPipeline(value=42, _config=KnotConfig(id="sub"))
    assert sub.config_values["value"] == 42


def test_mixed_parents_and_config():
    p = Parameter("a", int)
    sub = _TwoPInputPipeline(a=p, b="hello", _config=KnotConfig(id="sub"))
    assert sub.parents["a"] is p
    assert sub.config_values["b"] == "hello"


def test_requires_config_kwarg():
    p = Parameter("v", int)
    with pytest.raises(TypeError, match="_config"):
        _DoublerPipeline(value=p)  # type: ignore[call-arg]


def test_rejects_unknown_kwargs():
    p = Parameter("v", int)
    with pytest.raises(TypeError):
        _DoublerPipeline(value=p, unknown=99, _config=KnotConfig(id="sub"))


def test_missing_required_input_raises():
    with pytest.raises(TypeError, match="missing"):
        _DoublerPipeline(_config=KnotConfig(id="sub"))  # type: ignore[call-arg]


def test_knot_is_frozen_after_construction():
    p = Parameter("v", int, default=1)
    sub = _DoublerPipeline(value=p, _config=KnotConfig(id="sub"))
    with pytest.raises(AttributeError):
        sub.knot_id = "other"  # type: ignore[misc]


# -------------------------------------------------------- base process


async def test_base_process_raises_not_implemented():
    """Calling process() on SubTapestry itself raises NotImplementedError."""
    base = object.__new__(SubTapestry)
    with pytest.raises(NotImplementedError, match="must implement process"):
        await SubTapestry.process(base)


# -------------------------------------------------------- SubTapestryError


def test_sub_tapestry_error_stores_inner_result(make_failed_run_result: RunResult):
    err = SubTapestryError(make_failed_run_result)
    assert err.inner_result is make_failed_run_result


def test_sub_tapestry_error_message_mentions_exception_count(make_failed_run_result: RunResult):
    err = SubTapestryError(make_failed_run_result)
    assert "1" in str(err)


def test_sub_tapestry_error_is_exception():
    from datetime import UTC, datetime

    result = RunResult(
        run_id="r",
        terminals_requested=[],
        outputs={},
        started_at=datetime.now(UTC),
        finished_at=datetime.now(UTC),
        dispatcher="local",
    )
    err = SubTapestryError(result)
    assert isinstance(err, Exception)


# -------------------------------------------------------- self-registration


def test_auto_registers_with_active_tapestry():
    from pirn.tapestry import Tapestry

    with Tapestry() as t:
        p = Parameter("v", int, default=1)
        _DoublerPipeline(value=p, _config=KnotConfig(id="sub"))

    ids = [k.knot_id for k in t.store.all()]
    assert "sub" in ids

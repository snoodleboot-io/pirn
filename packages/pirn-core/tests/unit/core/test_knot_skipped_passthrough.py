"""A ``process()`` that returns ``Skipped`` declares a skip (WS0, PIR-856 deferral #5).

``Knot.__call__`` passes a returned ``Skipped`` through bare -- never wrapped
in ``Ok``, never checked against the return hint -- so the engine records the
knot as skipped and its children skip in turn.  ``Optional`` keeps its
``Ok(Skipped)`` contract: a skip of an optional knot is a *value* its
consumers receive.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.optional import Optional
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.tapestry import Tapestry


class _Denied(Knot):
    """Declares a skip although its return hint says int."""

    async def process(self, x: int, **_: Any) -> int:
        return Skipped(reason="denied", detail={"by": "policy"})  # type: ignore[return-value]


class _Echo(Knot):
    async def process(self, x: int, **_: Any) -> int:
        return x


def _upstream() -> Parameter:
    return Parameter("x", int, default=1, _config=KnotConfig(id="up"))


async def test_a_returned_skipped_is_passed_through_bare() -> None:
    # Arrange
    knot = _Denied(x=_upstream(), _config=KnotConfig(id="k"))

    # Act
    result = await knot({"x": 1})

    # Assert: bare Skipped, not Ok(Skipped), and no output-validation Err.
    assert isinstance(result, Skipped)
    assert result.reason == "denied"
    assert result.detail == {"by": "policy"}


async def test_the_engine_records_the_knot_as_skipped_and_skips_its_children() -> None:
    # Arrange
    with Tapestry() as t:
        p = _upstream()
        denied = _Denied(x=p, _config=KnotConfig(id="denied"))
        _Echo(x=denied, _config=KnotConfig(id="child"))

    # Act
    result = await t.run(RunRequest())

    # Assert
    assert result.succeeded
    assert result.skipped == ["denied", "child"]
    assert "denied" not in result.outputs
    record = next(rec for rec in result.lineage if rec.knot_id == "denied")
    assert record.outcome == "skipped"
    assert record.skip_reason == "denied"
    assert record.error_record_id is None


async def test_an_optional_knot_that_skips_still_yields_ok_skipped() -> None:
    # Arrange
    with Tapestry() as t:
        p = _upstream()
        opt = Optional(_Denied, x=p, _config=KnotConfig(id="opt"))
        _Echo(x=opt, _config=KnotConfig(id="child"))

    # Act
    result = await t.run(RunRequest())

    # Assert: the optional knot succeeded with a Skipped *value*; its child
    # ran and received it (and failed validation, as an int child would).
    assert "opt" in result.outputs
    assert isinstance(result.outputs["opt"], Skipped)
    assert result.outputs["opt"].reason == "denied"
    assert "opt" not in result.skipped
    record = next(rec for rec in result.lineage if rec.knot_id == "opt")
    assert record.outcome == "ok"
    assert record.extra["optional_skip"]["reason"] == "denied"


async def test_an_optional_stub_keeps_ok_skipped() -> None:
    class _NeedsValue(Knot):
        async def process(self, value: str, **_: Any) -> str:
            return value

    with Tapestry() as t:
        Optional(_NeedsValue, _config=KnotConfig(id="opt"))
    result = await t.run(RunRequest())
    assert isinstance(result.outputs["opt"], Skipped)
    assert result.outputs["opt"].detail["phase"] == "construction"


async def test_an_ok_value_is_still_validated_and_wrapped() -> None:
    knot = _Echo(x=_upstream(), _config=KnotConfig(id="k"))
    assert await knot({"x": 4}) == Ok(value=4)

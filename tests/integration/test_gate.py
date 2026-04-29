"""Gate node tests."""

from __future__ import annotations

import pytest

from pirn import Gate, KnotConfig, Parameter, RunRequest, Tapestry, knot


@knot
async def consume(value: int) -> int:
    return value * 100


async def test_gate_open_passes_through():
    with Tapestry() as t:
        p = Parameter("x", int, default=5)
        g = Gate(
            input=p,
            predicate=lambda v: v > 0,
            _config=KnotConfig(id="gate"),
        )
        consume(value=g, _config=KnotConfig(id="c"))

    result = await t.run(RunRequest())
    assert result.outputs["gate"] == 5
    assert result.outputs["c"] == 500


async def test_gate_closed_skips_downstream():
    with Tapestry() as t:
        p = Parameter("x", int, default=-3)
        g = Gate(
            input=p,
            predicate=lambda v: v > 0,
            _config=KnotConfig(id="gate"),
        )
        consume(value=g, _config=KnotConfig(id="c"))

    result = await t.run(RunRequest())
    assert "gate" in result.skipped
    assert "c" in result.skipped
    assert "c" not in result.outputs


async def test_gate_closed_lineage_records_skip():
    with Tapestry() as t:
        p = Parameter("x", int, default=-3)
        Gate(
            input=p,
            predicate=lambda v: v > 0,
            _config=KnotConfig(id="gate"),
        )

    result = await t.run(RunRequest())
    by_id = {rec.knot_id: rec for rec in result.lineage}
    assert by_id["gate"].outcome == "skipped"
    assert by_id["gate"].skip_reason == "gate_closed"


def test_gate_requires_callable_predicate():
    p = Parameter("x", int)
    with pytest.raises(TypeError):
        Gate(input=p, predicate="not callable", _config=KnotConfig(id="g"))  # type: ignore[arg-type]

"""Engine integration tests — full runs of multi-knot pipelines."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry


@knot
async def double(x: int) -> int:
    return x * 2


@knot
async def add(a: int, b: int) -> int:
    return a + b


# ---------------------------------------------------- happy path


async def test_simple_chain():
    with Tapestry() as t:
        p = Parameter("x", int)
        d = double(x=p, _config=KnotConfig(id="d"))
        a = add(a=p, b=d, _config=KnotConfig(id="answer"))

    result = await t.run(RunRequest(parameters={"x": 5}))
    assert result.succeeded
    assert result.outputs == {"param:x": 5, "d": 10, "answer": 15}
    assert len(result.lineage) == 3


async def test_default_parameter_value():
    with Tapestry() as t:
        p = Parameter("x", int, default=7)
        d = double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest())
    assert result.outputs["d"] == 14


async def test_overrides_default():
    with Tapestry() as t:
        p = Parameter("x", int, default=7)
        d = double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest(parameters={"x": 100}))
    assert result.outputs["d"] == 200


async def test_unbound_parameter_raises():
    with Tapestry() as t:
        p = Parameter("x", int)
        double(x=p, _config=KnotConfig(id="d"))
    with pytest.raises(RuntimeError, match="parameter"):
        await t.run(RunRequest())  # no value, no default


async def test_diamond():
    @knot
    async def join(left: int, right: int) -> int:
        return left * right

    with Tapestry() as t:
        p = Parameter("x", int, default=3)
        a = double(x=p, _config=KnotConfig(id="a"))  # 6
        b = double(x=a, _config=KnotConfig(id="b"))  # 12
        c = join(left=a, right=b, _config=KnotConfig(id="c"))  # 6 * 12 = 72

    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["c"] == 72


async def test_run_id_preserved():
    with Tapestry() as t:
        p = Parameter("x", int, default=1)
        double(x=p, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest(run_id="my-run-id"))
    assert result.run_id == "my-run-id"


async def test_dispatcher_name_in_result():
    with Tapestry() as t:
        p = Parameter("x", int, default=1)
        double(x=p, _config=KnotConfig(id="d"))
    result = await t.run(RunRequest())
    assert result.dispatcher == "LocalDispatcher"


# ------------------------------------------------ failure


async def test_knot_failure_recorded_in_exceptions():
    @knot
    async def boom(x: int) -> int:
        raise ValueError("boom!")

    with Tapestry() as t:
        p = Parameter("x", int, default=1)
        boom(x=p, _config=KnotConfig(id="b"))

    result = await t.run(RunRequest())
    assert not result.succeeded
    assert len(result.exceptions) == 1
    rec = result.exceptions[0]
    assert rec.knot_id == "b"
    assert rec.exc_type == "ValueError"
    assert "boom" in rec.message


async def test_failure_skips_downstream_by_default():
    @knot
    async def boom(x: int) -> int:
        raise ValueError("boom!")

    with Tapestry() as t:
        p = Parameter("x", int, default=1)
        b = boom(x=p, _config=KnotConfig(id="b"))
        # downstream of b — should be skipped
        double(x=b, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest())
    assert "d" in result.skipped


async def test_lineage_captures_skipped():
    @knot
    async def boom(x: int) -> int:
        raise ValueError("boom!")

    with Tapestry() as t:
        p = Parameter("x", int, default=1)
        b = boom(x=p, _config=KnotConfig(id="b"))
        double(x=b, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest())
    by_id = {rec.knot_id: rec for rec in result.lineage}
    assert by_id["b"].outcome == "err"
    assert by_id["b"].error_record_id is not None
    assert by_id["d"].outcome == "skipped"
    assert by_id["d"].skip_reason == "parent_failed_or_skipped"


# ------------------------------------------------ aggregator


async def test_aggregator_combines_parents():
    with Tapestry() as t:
        p = Parameter("x", int, default=2)
        a = double(x=p, _config=KnotConfig(id="a"))  # 4
        b = double(x=a, _config=KnotConfig(id="b"))  # 8
        agg = Aggregator(
            combine=lambda a, b: a + b,
            a=a,
            b=b,
            _config=KnotConfig(id="sum"),
        )

    result = await t.run(RunRequest())
    assert result.outputs["sum"] == 12


async def test_aggregator_async_combine():
    async def combine_async(a: int, b: int) -> int:
        return a * b

    with Tapestry() as t:
        p = Parameter("x", int, default=3)
        a = double(x=p, _config=KnotConfig(id="a"))  # 6
        b = double(x=a, _config=KnotConfig(id="b"))  # 12
        agg = Aggregator(
            combine=combine_async,
            a=a,
            b=b,
            _config=KnotConfig(id="prod"),
        )

    result = await t.run(RunRequest())
    assert result.outputs["prod"] == 72


# ------------------------------------------------ multi-run determinism


async def test_same_input_yields_same_output_hash():
    with Tapestry() as t:
        p = Parameter("x", int)
        d = double(x=p, _config=KnotConfig(id="d"))

    r1 = await t.run(RunRequest(parameters={"x": 5}))
    r2 = await t.run(RunRequest(parameters={"x": 5}))
    h1 = next(rec.output_hash for rec in r1.lineage if rec.knot_id == "d")
    h2 = next(rec.output_hash for rec in r2.lineage if rec.knot_id == "d")
    assert h1 == h2


async def test_different_input_yields_different_output_hash():
    with Tapestry() as t:
        p = Parameter("x", int)
        d = double(x=p, _config=KnotConfig(id="d"))

    r1 = await t.run(RunRequest(parameters={"x": 5}))
    r2 = await t.run(RunRequest(parameters={"x": 7}))
    h1 = next(rec.output_hash for rec in r1.lineage if rec.knot_id == "d")
    h2 = next(rec.output_hash for rec in r2.lineage if rec.knot_id == "d")
    assert h1 != h2


# ------------------------------------------------ lineage queries


async def test_history_lineage_query_by_output_hash():
    with Tapestry() as t:
        p = Parameter("x", int)
        d = double(x=p, _config=KnotConfig(id="d"))

    await t.run(RunRequest(parameters={"x": 5}))
    await t.run(RunRequest(parameters={"x": 5}))

    # Get d's output hash for input=5.
    r3 = await t.run(RunRequest(parameters={"x": 5}))
    out_hash = next(rec.output_hash for rec in r3.lineage if rec.knot_id == "d")

    # Query history.
    matches = await t.history.query_lineage_by_output_hash(out_hash)
    # 3 runs, each producing this output for d.
    assert len(matches) == 3
    assert all(m.knot_id == "d" for m in matches)


async def test_history_query_by_knot_id():
    with Tapestry() as t:
        p = Parameter("x", int)
        d = double(x=p, _config=KnotConfig(id="d"))

    await t.run(RunRequest(parameters={"x": 1}))
    await t.run(RunRequest(parameters={"x": 2}))

    matches = await t.history.query_lineage_by_knot_id("d")
    assert len(matches) == 2

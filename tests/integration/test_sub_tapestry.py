"""Integration tests for SubTapestry end-to-end execution."""

from __future__ import annotations

from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.nodes.sub_tapestry import SubTapestry
from pirn.tapestry import Tapestry

# -------------------------------------------------------- inner knots


@knot
async def double(x: int) -> int:
    return x * 2


@knot
async def add(a: int, b: int) -> int:
    return a + b


@knot
async def always_fail(x: int) -> int:
    raise RuntimeError("deliberate inner failure")


# -------------------------------------------------------- pipeline definitions


class DoublesPipeline(SubTapestry):
    """Doubles its input using an inner tapestry."""

    async def process(self, value: int, **_: Any) -> RunResult:
        with Tapestry() as inner:
            p = Parameter("v", int, default=value)
            double(x=p, _config=KnotConfig(id="out"))
        return await self._run_inner(inner)


class FailingPipeline(SubTapestry):
    """Inner pipeline that always errors."""

    async def process(self, value: int, **_: Any) -> RunResult:
        with Tapestry() as inner:
            p = Parameter("v", int, default=value)
            always_fail(x=p, _config=KnotConfig(id="fail"))
        return await self._run_inner(inner)


class SumPipeline(SubTapestry):
    """Inner pipeline summing two integers."""

    async def process(self, a: int, b: int, **_: Any) -> RunResult:
        with Tapestry() as inner:
            pa = Parameter("a", int, default=a)
            pb = Parameter("b", int, default=b)
            add(a=pa, b=pb, _config=KnotConfig(id="sum"))
        return await self._run_inner(inner)


# -------------------------------------------------------- execution


async def test_basic_execution_succeeds():
    with Tapestry() as outer:
        src = Parameter("v", int, default=5)
        DoublesPipeline(value=src, _config=KnotConfig(id="sub"))

    result = await outer.run(RunRequest())

    assert result.succeeded


async def test_inner_run_result_in_outputs():
    with Tapestry() as outer:
        src = Parameter("v", int, default=5)
        DoublesPipeline(value=src, _config=KnotConfig(id="sub"))

    result = await outer.run(RunRequest())

    inner = result.outputs["sub"]
    assert isinstance(inner, RunResult)
    assert inner.outputs["out"] == 10


async def test_parent_knot_value_flows_into_inner_pipeline():
    with Tapestry() as outer:
        a = Parameter("a", int, default=3)
        b = Parameter("b", int, default=4)
        SumPipeline(a=a, b=b, _config=KnotConfig(id="chain"))

    result = await outer.run(RunRequest())

    inner = result.outputs["chain"]
    assert inner.outputs["sum"] == 7


async def test_config_value_flows_into_inner_pipeline():
    with Tapestry() as outer:
        DoublesPipeline(value=6, _config=KnotConfig(id="sub"))

    result = await outer.run(RunRequest())

    inner = result.outputs["sub"]
    assert inner.outputs["out"] == 12


async def test_inner_failure_makes_outer_err():
    with Tapestry() as outer:
        src = Parameter("v", int, default=1)
        FailingPipeline(value=src, _config=KnotConfig(id="sub"))

    result = await outer.run(RunRequest())

    assert not result.succeeded
    assert any(rec.knot_id == "sub" for rec in result.exceptions)


async def test_inner_failure_wraps_sub_tapestry_error():
    """SubTapestryError is what gets caught by Knot.__call__ → Err."""
    with Tapestry() as outer:
        src = Parameter("v", int, default=1)
        FailingPipeline(value=src, _config=KnotConfig(id="sub"))

    result = await outer.run(RunRequest())

    exc_rec = next(r for r in result.exceptions if r.knot_id == "sub")
    assert "SubTapestryError" in exc_rec.exc_type


async def test_downstream_knot_receives_inner_run_result():
    """A knot downstream of SubTapestry receives the inner RunResult as input."""

    @knot
    async def extract(run: RunResult) -> int:
        return run.outputs["out"]

    with Tapestry() as outer:
        src = Parameter("v", int, default=7)
        sub = DoublesPipeline(value=src, _config=KnotConfig(id="sub"))
        extract(run=sub, _config=KnotConfig(id="extracted"))

    result = await outer.run(RunRequest())

    assert result.outputs["extracted"] == 14


# -------------------------------------------------------- run metadata


async def test_run_path_set_on_outer_run():
    with Tapestry() as outer:
        src = Parameter("v", int, default=1)
        DoublesPipeline(value=src, _config=KnotConfig(id="sub"))

    result = await outer.run(RunRequest())

    assert result.run_path == f"/{result.run_id}"


async def test_inner_run_has_parent_knot_id():
    with Tapestry() as outer:
        src = Parameter("v", int, default=1)
        DoublesPipeline(value=src, _config=KnotConfig(id="sub"))

    result = await outer.run(RunRequest())
    inner = result.outputs["sub"]

    assert inner.parent_knot_id == "sub"


async def test_inner_run_has_own_run_id():
    with Tapestry() as outer:
        src = Parameter("v", int, default=1)
        DoublesPipeline(value=src, _config=KnotConfig(id="sub"))

    result = await outer.run(RunRequest())
    inner = result.outputs["sub"]

    assert inner.run_id != result.run_id


# -------------------------------------------------------- children_of


async def test_inner_run_parent_knot_id_set_automatically():
    """_run_inner always sets parent_knot_id to self.knot_id on the inner result."""
    with Tapestry() as outer:
        src = Parameter("v", int, default=2)
        DoublesPipeline(value=src, _config=KnotConfig(id="sub"))

    outer_result = await outer.run(RunRequest())
    inner_result = outer_result.outputs["sub"]

    assert inner_result.parent_knot_id == "sub"
    # parent_run_id is None unless the user explicitly provides it
    assert inner_result.parent_run_id is None


async def test_children_of_empty_when_no_inner_runs():
    from pirn.backends.in_memory.in_memory_history import InMemoryHistory

    history = InMemoryHistory()
    with Tapestry(history=history) as t:
        p = Parameter("x", int, default=1)
        double(x=p, _config=KnotConfig(id="d"))

    result = await t.run(RunRequest())
    children = await history.children_of(result.run_id)

    assert children == []


async def test_children_of_via_explicit_parent_run_id():
    """Verify children_of works when parent_run_id is explicitly set."""
    from pirn.backends.in_memory.in_memory_history import InMemoryHistory

    history = InMemoryHistory()

    with Tapestry(history=history) as outer:
        p = Parameter("x", int, default=1)
        double(x=p, _config=KnotConfig(id="d"))

    outer_result = await outer.run(RunRequest())

    with Tapestry(history=history) as inner:
        p2 = Parameter("x", int, default=2)
        double(x=p2, _config=KnotConfig(id="d2"))

    inner_result = await inner.run(
        RunRequest(),
        _parent_run_id=outer_result.run_id,
        _parent_knot_id="d",
    )

    children = await history.children_of(outer_result.run_id)
    assert len(children) == 1
    assert children[0].run_id == inner_result.run_id


# -------------------------------------------------------- nesting depth


async def test_arbitrarily_nested_sub_tapestry():
    """Three levels of SubTapestry all succeed."""

    class Level2(SubTapestry):
        async def process(self, x: int, **_: Any) -> RunResult:
            with Tapestry() as inner:
                p = Parameter("x", int, default=x)
                double(x=p, _config=KnotConfig(id="doubled"))
            return await self._run_inner(inner)

    class Level1(SubTapestry):
        async def process(self, x: int, **_: Any) -> RunResult:
            with Tapestry() as inner:
                p = Parameter("x", int, default=x)
                Level2(x=p, _config=KnotConfig(id="l2"))
            return await self._run_inner(inner)

    with Tapestry() as outer:
        src = Parameter("x", int, default=3)
        Level1(x=src, _config=KnotConfig(id="l1"))

    result = await outer.run(RunRequest())

    assert result.succeeded
    l1_result = result.outputs["l1"]
    l2_result = l1_result.outputs["l2"]
    assert l2_result.outputs["doubled"] == 6


# -------------------------------------------------------- SubTapestry in outer pipeline


async def test_sub_tapestry_as_intermediate_node():
    """SubTapestry used as a step between two outer knots."""

    @knot
    async def square(x: int) -> int:
        return x * x

    @knot
    async def negate(x: int) -> int:
        return -x

    class DoublePipeline(SubTapestry):
        async def process(self, x: int, **_: Any) -> RunResult:
            with Tapestry() as inner:
                p = Parameter("x", int, default=x)
                double(x=p, _config=KnotConfig(id="doubled"))
            return await self._run_inner(inner)

    @knot
    async def extract_doubled(run: RunResult) -> int:
        return run.outputs["doubled"]

    with Tapestry() as outer:
        raw = Parameter("x", int, default=4)
        squared = square(x=raw, _config=KnotConfig(id="sq"))
        sub = DoublePipeline(x=squared, _config=KnotConfig(id="sub"))
        result_knot = extract_doubled(run=sub, _config=KnotConfig(id="final"))

    result = await outer.run(RunRequest())

    assert result.succeeded
    # 4 ** 2 = 16, doubled = 32
    assert result.outputs["final"] == 32

"""Aggregator node tests (beyond what's in test_engine.py)."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.aggregator import Aggregator
from pirn.tapestry import Tapestry


def test_aggregator_requires_at_least_one_parent():
    with pytest.raises(TypeError, match="at least one parent"):
        Aggregator(combine=lambda **kw: kw, _config=KnotConfig(id="a"))


def test_aggregator_rejects_non_knot_parent():
    with pytest.raises(TypeError, match="must be a Knot"):
        Aggregator(combine=lambda x: x, x=42, _config=KnotConfig(id="a"))


def test_aggregator_requires_callable_combine():
    p = Parameter("x", int)
    with pytest.raises(TypeError, match="callable"):
        Aggregator(combine="not callable", a=p, _config=KnotConfig(id="a"))


def test_aggregator_requires_config():
    p = Parameter("x", int)
    with pytest.raises(TypeError, match="_config"):
        Aggregator(combine=lambda **kw: kw, a=p)


async def test_aggregator_with_three_parents():
    @knot
    async def src(v: int) -> int:
        return v

    with Tapestry() as t:
        x = Parameter("x", int, default=1)
        y = Parameter("y", int, default=2)
        z = Parameter("z", int, default=3)
        Aggregator(
            combine=lambda a, b, c: a + b + c,
            a=x,
            b=y,
            c=z,
            _config=KnotConfig(id="agg"),
        )
    result = await t.run(RunRequest())
    assert result.outputs["agg"] == 6

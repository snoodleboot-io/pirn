"""Reduce node tests."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.core.parameter import Parameter
from pirn.nodes.reduce_ import Reduce
from pirn.tapestry import Tapestry


async def test_reduce_whole_list_with_sum():
    """sum has signature (iterable, /, start=0) — 1 required arg → whole-list form."""
    with Tapestry() as t:
        xs = Parameter("xs", list[int], default=[1, 2, 3, 4])
        Reduce(of=xs, combine=sum, _config=KnotConfig(id="s"))
    result = await t.run(RunRequest())
    assert result.outputs["s"] == 10


async def test_reduce_whole_list_lambda():
    with Tapestry() as t:
        xs = Parameter("xs", list[int], default=[1, 2, 3, 4])
        Reduce(of=xs, combine=lambda items: max(items), _config=KnotConfig(id="m"))
    result = await t.run(RunRequest())
    assert result.outputs["m"] == 4


async def test_reduce_pairwise_with_initial():
    with Tapestry() as t:
        words = Parameter("ws", list[str], default=["a", "b", "a", "c", "a"])
        Reduce(
            of=words,
            combine=lambda acc, w: {**acc, w: acc.get(w, 0) + 1},
            initial={},
            _config=KnotConfig(id="counts"),
        )
    result = await t.run(RunRequest())
    assert result.outputs["counts"] == {"a": 3, "b": 1, "c": 1}


def test_reduce_pairwise_without_initial_raises():
    p = Parameter("xs", list[int])
    with pytest.raises(TypeError, match="initial"):
        Reduce(
            of=p,
            combine=lambda a, b: a + b,
            _config=KnotConfig(id="r"),
        )


def test_reduce_too_many_args_raises():
    p = Parameter("xs", list[int])
    with pytest.raises(TypeError, match="1 or 2"):
        Reduce(
            of=p,
            combine=lambda a, b, c: a + b + c,
            _config=KnotConfig(id="r"),
        )


def test_reduce_zero_args_raises():
    p = Parameter("xs", list[int])
    with pytest.raises(TypeError, match="1 or 2"):
        Reduce(
            of=p,
            combine=lambda: 0,
            _config=KnotConfig(id="r"),
        )


async def test_reduce_pairwise_with_initial_zero():
    """Initial of 0 (falsy) must be respected — the check is for _UNSET sentinel,
    not falsiness."""
    with Tapestry() as t:
        xs = Parameter("xs", list[int], default=[1, 2, 3])
        Reduce(
            of=xs,
            combine=lambda acc, x: acc + x,
            initial=0,
            _config=KnotConfig(id="r"),
        )
    result = await t.run(RunRequest())
    assert result.outputs["r"] == 6


async def test_reduce_empty_list_pairwise_returns_initial():
    with Tapestry() as t:
        xs = Parameter("xs", list[int], default=[])
        Reduce(
            of=xs,
            combine=lambda acc, x: acc + x,
            initial=99,
            _config=KnotConfig(id="r"),
        )
    result = await t.run(RunRequest())
    assert result.outputs["r"] == 99

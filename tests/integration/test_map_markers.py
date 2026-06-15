"""Tests for the new Map/ZipMap/DictMap annotation API."""

from __future__ import annotations

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.map_markers import DictMap, Map, ZipMap
from pirn.tapestry import Tapestry


@knot
async def double(x: int, **_) -> int:
    return x * 2


@knot
async def add_pair(a: int, b: int, **_) -> int:
    return a + b


@knot
async def show_entry(k: str, v: int, **_) -> str:
    return f"{k}={v}"


@knot
async def fail_negative(v: int, **_) -> int:
    if v < 0:
        raise ValueError("negative")
    return v


async def test_map_fan_out():
    with Tapestry() as t:
        xs = Parameter("xs", list, default=[1, 2, 3], _config=KnotConfig(id="xs"))
        double(x=Map(xs), _config=KnotConfig(id="result"))
    r = await t.run(RunRequest())
    assert r.outputs["result"] == [2, 4, 6]


async def test_map_empty_collection():
    with Tapestry() as t:
        xs = Parameter("xs", list, default=[], _config=KnotConfig(id="xs"))
        double(x=Map(xs), _config=KnotConfig(id="result"))
    r = await t.run(RunRequest())
    assert r.outputs["result"] == []


async def test_map_inner_failure_propagates():
    with Tapestry() as t:
        xs = Parameter("xs", list, default=[1, -1, 2], _config=KnotConfig(id="xs"))
        fail_negative(v=Map(xs), _config=KnotConfig(id="result"))
    r = await t.run(RunRequest())
    assert not r.succeeded
    assert any(e.knot_id == "result" for e in r.exceptions)


async def test_map_type_error_set():
    with Tapestry() as t:
        xs = Parameter("xs", object, default={1, 2, 3}, _config=KnotConfig(id="xs"))
        double(x=Map(xs), _config=KnotConfig(id="result"))
    r = await t.run(RunRequest())
    assert not r.succeeded


async def test_zipmap_fan_out():
    with Tapestry() as t:
        p1 = Parameter("p1", list, default=[1, 2, 3], _config=KnotConfig(id="p1"))
        p2 = Parameter("p2", list, default=[10, 20, 30], _config=KnotConfig(id="p2"))
        add_pair(a=ZipMap(p1), b=ZipMap(p2), _config=KnotConfig(id="sums"))
    r = await t.run(RunRequest())
    assert r.outputs["sums"] == [11, 22, 33]


async def test_zipmap_truncates_to_shortest():
    with Tapestry() as t:
        p1 = Parameter("p1", list, default=[1, 2], _config=KnotConfig(id="p1"))
        p2 = Parameter("p2", list, default=[10, 20, 30], _config=KnotConfig(id="p2"))
        add_pair(a=ZipMap(p1), b=ZipMap(p2), _config=KnotConfig(id="sums"))
    r = await t.run(RunRequest())
    assert r.outputs["sums"] == [11, 22]


async def test_dictmap_fan_out():
    with Tapestry() as t:
        d = Parameter("d", dict, default={"a": 1, "b": 2}, _config=KnotConfig(id="d"))
        show_entry(k=DictMap(d), v=DictMap(d), _config=KnotConfig(id="entries"))
    r = await t.run(RunRequest())
    assert r.outputs["entries"] == ["a=1", "b=2"]


def test_cross_product_map_rejected():
    with pytest.raises(TypeError, match="cross-product"):
        with Tapestry():
            a = Parameter("a", list, default=[1], _config=KnotConfig(id="a"))
            b = Parameter("b", list, default=[2], _config=KnotConfig(id="b"))
            add_pair(a=Map(a), b=Map(b), _config=KnotConfig(id="bad"))


def test_mixing_map_and_zipmap_rejected():
    with pytest.raises(TypeError, match="mix"):
        with Tapestry():
            a = Parameter("a", list, default=[1], _config=KnotConfig(id="a"))
            b = Parameter("b", list, default=[2], _config=KnotConfig(id="b"))
            add_pair(a=Map(a), b=ZipMap(b), _config=KnotConfig(id="bad"))


def test_dictmap_requires_same_source():
    with pytest.raises(TypeError, match="same source"):
        with Tapestry():
            a = Parameter("a", dict, default={}, _config=KnotConfig(id="a"))
            b = Parameter("b", dict, default={}, _config=KnotConfig(id="b"))
            show_entry(k=DictMap(a), v=DictMap(b), _config=KnotConfig(id="bad"))


def test_dictmap_requires_two_inputs():
    @knot
    async def single_dict_input(k: str, **_) -> str:
        return k

    with pytest.raises(TypeError, match="exactly two"):
        with Tapestry():
            d = Parameter("d", dict, default={}, _config=KnotConfig(id="d"))
            single_dict_input(k=DictMap(d), _config=KnotConfig(id="bad"))

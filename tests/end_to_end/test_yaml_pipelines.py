"""End-to-end YAML pipeline tests."""

from __future__ import annotations

import pytest

from pirn.core.run_request import RunRequest
from pirn.core.knot_factory import knot
from pirn.yaml_loader.loader import load_pipeline


@knot
async def double(x: int) -> int:
    return x * 2


@knot
async def add(a: int, b: int) -> int:
    return a + b


def merge_dicts(a: dict, b: dict) -> dict:
    return {**a, **b}


# ------------------------------------------------ strict mode


async def test_yaml_strict_mode_simple_chain():
    yaml_text = """
    name: test
    nodes:
      - id: x
        type: parameter
        type_: int
        has_default: true
        default: 5
      - id: doubled
        type: knot
        callable: double
        parents:
          x: x
      - id: answer
        type: knot
        callable: add
        parents:
          a: x
          b: doubled
    """
    tapestry = load_pipeline(
        yaml_text,
        known_callables={"double": double, "add": add},
    )
    result = await tapestry.run(RunRequest())
    assert result.succeeded
    assert result.outputs["answer"] == 15


async def test_yaml_with_aggregator():
    yaml_text = """
    name: agg
    nodes:
      - id: a
        type: parameter
        type_: dict
        has_default: true
        default: {x: 1}
      - id: b
        type: parameter
        type_: dict
        has_default: true
        default: {y: 2}
      - id: merged
        type: aggregator
        combine: merge
        parents:
          a: a
          b: b
    """
    tapestry = load_pipeline(yaml_text, known_callables={"merge": merge_dicts})
    result = await tapestry.run(RunRequest())
    assert result.outputs["merged"] == {"x": 1, "y": 2}


async def test_yaml_with_gate():
    yaml_text = """
    name: gate
    nodes:
      - id: x
        type: parameter
        type_: int
        has_default: true
        default: 10
      - id: g
        type: gate
        input: x
        predicate: is_positive
    """
    tapestry = load_pipeline(
        yaml_text,
        known_callables={"is_positive": lambda v: v > 0},
    )
    result = await tapestry.run(RunRequest())
    assert result.outputs["g"] == 10


async def test_yaml_with_branch():
    yaml_text = """
    name: br
    nodes:
      - id: msg
        type: parameter
        type_: dict
        has_default: true
        default: {kind: a}
      - id: route
        type: branch
        input: msg
        selector: pick
        branches: [a, b]
    """
    tapestry = load_pipeline(
        yaml_text,
        known_callables={"pick": lambda d: d["kind"]},
    )
    result = await tapestry.run(RunRequest())
    assert result.outputs["route:a"] == {"kind": "a"}
    assert "route:b" in result.skipped


async def test_yaml_missing_known_callable_raises():
    yaml_text = """
    name: x
    nodes:
      - id: x
        type: parameter
        type_: int
        has_default: true
        default: 5
      - id: doubled
        type: knot
        callable: not_registered
        parents:
          x: x
    """
    with pytest.raises(ValueError, match="not in known_callables"):
        load_pipeline(yaml_text, known_callables={})


async def test_yaml_unknown_parent_raises():
    yaml_text = """
    name: x
    nodes:
      - id: doubled
        type: knot
        callable: double
        parents:
          x: nonexistent
    """
    with pytest.raises(ValueError, match="unknown parent"):
        load_pipeline(yaml_text, known_callables={"double": double})


async def test_yaml_with_reduce():
    yaml_text = """
    name: r
    nodes:
      - id: xs
        type: parameter
        type_: list[int]
        has_default: true
        default: [1, 2, 3, 4]
      - id: sum
        type: reduce
        of: xs
        combine: sum_all
    """
    tapestry = load_pipeline(
        yaml_text,
        known_callables={"sum_all": sum},
    )
    result = await tapestry.run(RunRequest())
    assert result.outputs["sum"] == 10


async def test_yaml_with_map():
    yaml_text = """
    name: m
    nodes:
      - id: ids
        type: parameter
        type_: list[int]
        has_default: true
        default: [1, 2, 3]
      - id: users
        type: map
        over: ids
        each: make_user
        bind: idx
    """

    @knot
    async def make_user(idx: int) -> dict:
        return {"id": idx}

    tapestry = load_pipeline(
        yaml_text,
        known_callables={"make_user": make_user},
    )
    result = await tapestry.run(RunRequest())
    assert result.outputs["users"] == [{"id": 1}, {"id": 2}, {"id": 3}]


def test_yaml_top_level_must_be_mapping():
    with pytest.raises(ValueError, match="mapping"):
        load_pipeline("- just a list")

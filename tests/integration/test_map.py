"""Map node tests."""

from __future__ import annotations

import pytest

from pirn import KnotConfig, Map, Parameter, RunRequest, Tapestry, knot


@knot
async def make_user(idx: int) -> dict:
    return {"id": idx, "name": f"u{idx}"}


@knot
async def maybe_pos(v: int) -> int:
    if v < 0:
        raise ValueError("negative")
    return v * 2


async def test_map_basic():
    with Tapestry() as t:
        ids = Parameter("ids", list[int], default=[1, 2, 3])
        Map(
            over=ids,
            each=make_user,
            bind="idx",
            _config=KnotConfig(id="users"),
        )

    result = await t.run(RunRequest())
    users = result.outputs["users"]
    assert users == [
        {"id": 1, "name": "u1"},
        {"id": 2, "name": "u2"},
        {"id": 3, "name": "u3"},
    ]


async def test_map_empty_collection():
    with Tapestry() as t:
        ids = Parameter("ids", list[int], default=[])
        Map(
            over=ids,
            each=make_user,
            bind="idx",
            _config=KnotConfig(id="users"),
        )
    result = await t.run(RunRequest())
    assert result.outputs["users"] == []


async def test_map_inner_failure_propagates():
    with Tapestry() as t:
        xs = Parameter("xs", list[int], default=[1, 2, -1, 3])
        Map(
            over=xs,
            each=maybe_pos,
            bind="v",
            _config=KnotConfig(id="m"),
        )
    result = await t.run(RunRequest())
    assert not result.succeeded
    assert any(rec.knot_id == "m" for rec in result.exceptions)


def test_map_requires_knot_factory_or_class():
    p = Parameter("x", list[int])
    with pytest.raises(TypeError, match="Knot subclass"):
        Map(over=p, each="not a knot", bind="v", _config=KnotConfig(id="m"))  # type: ignore[arg-type]


def test_map_requires_bind_string():
    p = Parameter("x", list[int])
    with pytest.raises(TypeError):
        Map(over=p, each=make_user, bind="", _config=KnotConfig(id="m"))


async def test_map_with_shared_config_value():
    """Non-Knot shared kwargs are forwarded to each inner construction."""

    @knot
    async def label(value: int, prefix: str) -> str:
        return f"{prefix}{value}"

    with Tapestry() as t:
        xs = Parameter("xs", list[int], default=[1, 2, 3])
        Map(
            over=xs,
            each=label,
            bind="value",
            prefix="n=",
            _config=KnotConfig(id="m"),
        )

    result = await t.run(RunRequest())
    assert result.outputs["m"] == ["n=1", "n=2", "n=3"]

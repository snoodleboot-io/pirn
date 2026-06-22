"""Map annotation API tests (new input-site distribution design)."""

from __future__ import annotations

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.map_markers import Map
from pirn.tapestry import Tapestry


@knot
async def make_user(idx: int, **_) -> dict:
    return {"id": idx, "name": f"u{idx}"}


@knot
async def maybe_pos(v: int, **_) -> int:
    if v < 0:
        raise ValueError("negative")
    return v * 2


async def test_map_basic():
    with Tapestry() as t:
        ids = Parameter("ids", list, default=[1, 2, 3], _config=KnotConfig(id="ids"))
        make_user(idx=Map(ids), _config=KnotConfig(id="users"))

    result = await t.run(RunRequest())
    users = result.outputs["users"]
    assert users == [
        {"id": 1, "name": "u1"},
        {"id": 2, "name": "u2"},
        {"id": 3, "name": "u3"},
    ]


async def test_map_empty_collection():
    with Tapestry() as t:
        ids = Parameter("ids", list, default=[], _config=KnotConfig(id="ids"))
        make_user(idx=Map(ids), _config=KnotConfig(id="users"))
    result = await t.run(RunRequest())
    assert result.outputs["users"] == []


async def test_map_inner_failure_propagates():
    with Tapestry() as t:
        xs = Parameter("xs", list, default=[1, 2, -1, 3], _config=KnotConfig(id="xs"))
        maybe_pos(v=Map(xs), _config=KnotConfig(id="m"))
    result = await t.run(RunRequest())
    assert not result.succeeded
    assert any(rec.knot_id == "m" for rec in result.exceptions)


def test_map_cross_product_rejected():
    @knot
    async def add(a: int, b: int, **_) -> int:
        return a + b

    p = Parameter("x", list, _config=KnotConfig(id="x"))
    q = Parameter("y", list, _config=KnotConfig(id="y"))
    with pytest.raises(TypeError, match="cross-product"):
        add(a=Map(p), b=Map(q), _config=KnotConfig(id="m"))


async def test_map_with_shared_config_value():
    """Non-Knot kwargs are still forwarded as config values."""

    @knot
    async def label(value: int, prefix: str, **_) -> str:
        return f"{prefix}{value}"

    with Tapestry() as t:
        xs = Parameter("xs", list, default=[1, 2, 3], _config=KnotConfig(id="xs"))
        label(value=Map(xs), prefix="n=", _config=KnotConfig(id="m"))

    result = await t.run(RunRequest())
    assert result.outputs["m"] == ["n=1", "n=2", "n=3"]

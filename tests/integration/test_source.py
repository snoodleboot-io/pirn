"""Source node tests."""

from __future__ import annotations

import pytest

from pirn import Knot, KnotConfig, RunRequest, Source, Tapestry


class StaticSource(Source):
    async def process(self) -> dict:
        return {"a": 1, "b": 2}


async def test_source_is_a_knot():
    s = StaticSource(_config=KnotConfig(id="s"))
    assert isinstance(s, Knot)
    assert s.knot_id == "s"


async def test_source_runs_in_pipeline():
    with Tapestry() as t:
        StaticSource(_config=KnotConfig(id="s"))
    result = await t.run(RunRequest())
    assert result.succeeded
    assert result.outputs["s"] == {"a": 1, "b": 2}


def test_source_has_no_parents():
    s = StaticSource(_config=KnotConfig(id="s"))
    assert s.parents == {}


def test_source_rejects_kwargs():
    with pytest.raises(TypeError, match="takes no inputs"):
        StaticSource(extra="nope", _config=KnotConfig(id="s"))


async def test_source_feeds_downstream():
    from pirn import knot

    @knot
    async def get_a(d: dict) -> int:
        return d["a"]

    with Tapestry() as t:
        s = StaticSource(_config=KnotConfig(id="s"))
        get_a(d=s, _config=KnotConfig(id="g"))

    result = await t.run(RunRequest())
    assert result.outputs["g"] == 1

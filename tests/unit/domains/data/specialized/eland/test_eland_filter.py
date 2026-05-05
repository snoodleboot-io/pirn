"""Tests for :class:`ElandFilter`.

The filter delegates to the eland frame's ``__getitem__`` (mask
indexing). A fake frame that records the mask exercises the knot without
requiring a live Elasticsearch cluster.
"""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specialized.eland.eland_dataframe import ElandDataFrame
from pirn.domains.data.specialized.eland.eland_filter import ElandFilter
from pirn.tapestry import Tapestry


class _FakeFrame:
    """Records mask indexing; returns a new instance for chained ops."""

    def __init__(self, name: str = "root") -> None:
        self.name = name
        self.last_mask: Any = None

    def __getitem__(self, mask: Any) -> "_FakeFrame":
        child = _FakeFrame(name=f"{self.name}[mask]")
        child.last_mask = mask
        return child


def _make_frame(uri: str = "elasticsearch://x") -> ElandDataFrame:
    return ElandDataFrame(frame=_FakeFrame(), source_uri=uri)


class TestElandFilter(unittest.IsolatedAsyncioTestCase):
    async def test_invokes_predicate_and_indexes_frame(self) -> None:
        @knot
        async def emit() -> ElandDataFrame:
            return _make_frame()

        captured: dict[str, Any] = {}

        def predicate(df: _FakeFrame) -> str:
            captured["called_with"] = df
            return "fake-mask"

        with Tapestry() as t:
            up = emit(_config=KnotConfig(id="up"))
            ElandFilter(frame=up, predicate=predicate, _config=KnotConfig(id="f"))
        result = await t.run(RunRequest())

        out = result.outputs["f"]
        assert isinstance(out, ElandDataFrame)
        assert isinstance(captured["called_with"], _FakeFrame)
        assert out.frame.last_mask == "fake-mask"
        assert out.source_uri == "elasticsearch://x"

    async def test_preserves_provenance_metadata(self) -> None:
        @knot
        async def emit() -> ElandDataFrame:
            return _make_frame(uri="elasticsearch://cluster/index")

        with Tapestry() as t:
            up = emit(_config=KnotConfig(id="up"))
            ElandFilter(
                frame=up,
                predicate=lambda df: "mask",
                _config=KnotConfig(id="f"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["f"]
        assert out.source_uri == "elasticsearch://cluster/index"


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_predicate_from_upstream_knot(self) -> None:
        @knot
        async def emit_frame() -> ElandDataFrame:
            return _make_frame()

        @knot
        async def emit_pred() -> Any:
            return lambda df: "mask"

        with Tapestry():
            frame_knot = emit_frame(_config=KnotConfig(id="frame"))
            pred_knot = emit_pred(_config=KnotConfig(id="pred"))
            ElandFilter(frame=frame_knot, predicate=pred_knot, _config=KnotConfig(id="f"))
        # Construction with Knot inputs succeeds — process() tested separately


class TestValidation(unittest.IsolatedAsyncioTestCase):
    async def _make_knot(self, **kwargs: Any) -> ElandFilter:
        @knot
        async def upstream() -> ElandDataFrame:
            return _make_frame()

        with Tapestry():
            up = upstream(_config=KnotConfig(id="up"))
            return ElandFilter(
                frame=up,
                predicate=lambda df: "mask",
                _config=KnotConfig(id="f"),
                **kwargs,
            )

    async def test_rejects_non_callable_predicate(self) -> None:
        k = await self._make_knot()
        with self.assertRaisesRegex(TypeError, "predicate must be a callable"):
            await k.process(frame=_make_frame(), predicate="status == active")

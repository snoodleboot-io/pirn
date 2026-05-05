"""Tests for :class:`ElandFilter`.

The filter delegates to the eland frame's ``__getitem__`` (mask
indexing). A fake frame that records the mask exercise the knot without
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


class TestElandFilterConstruction(unittest.TestCase):
    def test_rejects_non_callable_predicate(self) -> None:
        @knot
        async def emit() -> ElandDataFrame:
            return ElandDataFrame(frame=_FakeFrame())

        with Tapestry():
            up = emit(_config=KnotConfig(id="up"))
            with self.assertRaisesRegex(TypeError, "predicate must be a callable"):
                ElandFilter(
                    frame=up, predicate="status == active",  # type: ignore[arg-type]
                    _config=KnotConfig(id="f"),
                )


class TestElandFilterProcess(unittest.IsolatedAsyncioTestCase):
    async def test_invokes_predicate_and_indexes_frame(self) -> None:
        @knot
        async def emit() -> ElandDataFrame:
            return ElandDataFrame(frame=_FakeFrame(), source_uri="elasticsearch://x")

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
        # The same eland frame reference was passed into the predicate.
        assert isinstance(captured["called_with"], _FakeFrame)
        # The mask returned was applied to produce a new frame.
        assert out.frame.last_mask == "fake-mask"
        # Provenance metadata is preserved.
        assert out.source_uri == "elasticsearch://x"

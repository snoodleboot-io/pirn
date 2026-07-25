"""Tests for the router + typed fallback chain (S5)."""

from __future__ import annotations

import unittest
from collections.abc import Mapping
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.routing.candidate_router import CandidateRouter
from pirn_agents.specializations.routing.fallback_chain import FallbackChain
from pirn_agents.specializations.routing.fallback_result import FallbackResult
from pirn_agents.specializations.routing.route_candidate import RouteCandidate
from pirn_agents.specializations.routing.router_fallback_pipeline import RouterFallbackPipeline
from tests.specializations.conftest import StubTool


def _raise(_: Mapping[str, Any]) -> Any:
    raise RuntimeError("tool failed")


def _cands() -> tuple[RouteCandidate, ...]:
    return (
        RouteCandidate(name="a", tool=StubTool(name="a", handler=_raise)),
        RouteCandidate(name="b", tool=StubTool(name="b", handler=_raise)),
        RouteCandidate(name="c", tool=StubTool(name="c", handler="C-ok")),
    )


class TestCandidateRouter(unittest.IsolatedAsyncioTestCase):
    async def test_orders_by_confidence_descending(self) -> None:
        with Tapestry():
            router = CandidateRouter(
                candidates=_cands(),
                confidences={"a": 0.1, "b": 0.5, "c": 0.9},
                _config=KnotConfig(id="r", validate_io=False),
            )
        ordered = await router.process(
            candidates=_cands(), confidences={"a": 0.1, "b": 0.5, "c": 0.9}
        )
        assert [c.name for c in ordered] == ["c", "b", "a"]

    async def test_rejects_non_mapping_confidences(self) -> None:
        with Tapestry():
            router = CandidateRouter(
                candidates=_cands(),
                confidences={},
                _config=KnotConfig(id="r", validate_io=False),
            )
        with self.assertRaises(TypeError):
            await router.process(candidates=_cands(), confidences="bad")  # type: ignore[arg-type]


class TestFallbackChain(unittest.IsolatedAsyncioTestCase):
    async def test_stops_at_first_success(self) -> None:
        ordered = (
            RouteCandidate(name="c", tool=StubTool(name="c", handler="C-ok")),
            RouteCandidate(name="b", tool=StubTool(name="b", handler=_raise)),
        )
        with Tapestry():
            chain = FallbackChain(
                ordered=ordered,
                arguments={"input": "x"},
                confidences={"c": 0.9, "b": 0.5},
                _config=KnotConfig(id="fc", validate_io=False),
            )
        result = await chain.process(
            ordered=ordered, arguments={"input": "x"}, confidences={"c": 0.9, "b": 0.5}
        )
        assert isinstance(result, FallbackResult)
        assert result.succeeded is True
        assert result.chosen == "c"
        assert result.attempted == ("c",)

    async def test_falls_through_failures(self) -> None:
        ordered = (
            RouteCandidate(name="a", tool=StubTool(name="a", handler=_raise)),
            RouteCandidate(name="c", tool=StubTool(name="c", handler="C-ok")),
        )
        with Tapestry():
            chain = FallbackChain(
                ordered=ordered,
                arguments={},
                confidences={"a": 0.9, "c": 0.9},
                _config=KnotConfig(id="fc", validate_io=False),
            )
        result = await chain.process(
            ordered=ordered, arguments={}, confidences={"a": 0.9, "c": 0.9}
        )
        assert result.succeeded is True
        assert result.chosen == "c"
        assert result.attempted == ("a", "c")

    async def test_skips_low_confidence(self) -> None:
        ordered = (
            RouteCandidate(name="a", tool=StubTool(name="a", handler="A-ok"), min_confidence=0.8),
            RouteCandidate(name="c", tool=StubTool(name="c", handler="C-ok"), min_confidence=0.2),
        )
        with Tapestry():
            chain = FallbackChain(
                ordered=ordered,
                arguments={},
                confidences={"a": 0.1, "c": 0.5},
                _config=KnotConfig(id="fc", validate_io=False),
            )
        result = await chain.process(
            ordered=ordered, arguments={}, confidences={"a": 0.1, "c": 0.5}
        )
        assert result.chosen == "c"
        assert result.skipped == ("a",)
        assert result.attempted == ("c",)

    async def test_exhausts_chain(self) -> None:
        ordered = (RouteCandidate(name="a", tool=StubTool(name="a", handler=_raise)),)
        with Tapestry():
            chain = FallbackChain(
                ordered=ordered,
                arguments={},
                confidences={"a": 0.9},
                _config=KnotConfig(id="fc", validate_io=False),
            )
        result = await chain.process(ordered=ordered, arguments={}, confidences={"a": 0.9})
        assert result.succeeded is False
        assert result.chosen is None


class TestRouterFallbackPipeline(unittest.IsolatedAsyncioTestCase):
    async def test_end_to_end_dispatch(self) -> None:
        with Tapestry() as t:
            RouterFallbackPipeline(
                candidates=_cands(),
                confidences={"a": 0.1, "b": 0.5, "c": 0.9},
                arguments={"input": "q"},
                _config=KnotConfig(id="rf"),
            )
        run = await t.run(RunRequest())
        assert run.succeeded
        result = run.outputs["rf"]
        assert isinstance(result, FallbackResult)
        assert result.succeeded is True
        assert result.chosen == "c"
        # c has highest confidence, so it is tried first and succeeds immediately.
        assert result.attempted == ("c",)

    async def test_rejects_bad_candidate(self) -> None:
        with Tapestry():
            knot = RouterFallbackPipeline.__new__(RouterFallbackPipeline)
            object.__setattr__(knot, "_config", KnotConfig(id="rf"))
        with self.assertRaises(TypeError):
            await knot.process(candidates=("bad",), confidences={}, arguments={})  # type: ignore[arg-type]

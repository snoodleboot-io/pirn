"""Router+fallback vs. naive-retry micro-benchmark (PIR-226).

``@pytest.mark.benchmark``; the confidence-ordered fallback chain tries the most
likely candidate first and stops on success, so it invokes fewer tools than a
naive baseline that retries every candidate in declaration order.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_agents.specializations.routing.route_candidate import RouteCandidate
from pirn_agents.specializations.routing.router_fallback_pipeline import RouterFallbackPipeline
from tests.benchmarks.conftest import BenchmarkRecorder
from tests.specializations.conftest import StubTool


def _raise(_: Mapping[str, Any]) -> Any:
    raise RuntimeError("fail")


@pytest.mark.benchmark
async def test_router_fallback_fewer_invocations_than_naive(
    benchmark_recorder: BenchmarkRecorder,
) -> None:
    # Declaration order a, b, c; only c succeeds; c has the highest confidence.
    tool_a = StubTool(name="a", handler=_raise)
    tool_b = StubTool(name="b", handler=_raise)
    tool_c = StubTool(name="c", handler="C-ok")
    candidates = (
        RouteCandidate(name="a", tool=tool_a),
        RouteCandidate(name="b", tool=tool_b),
        RouteCandidate(name="c", tool=tool_c),
    )
    confidences = {"a": 0.2, "b": 0.5, "c": 0.9}

    with Tapestry() as t:
        RouterFallbackPipeline(
            candidates=candidates,
            confidences=confidences,
            arguments={"input": "q"},
            _config=KnotConfig(id="rf"),
        )
    run = await t.run(RunRequest())
    assert run.succeeded
    result = run.outputs["rf"]
    router_invocations = len(result.attempted)

    # Naive baseline: retry candidates in declaration order until one succeeds.
    naive_invocations = 0
    for candidate in candidates:
        naive_invocations += 1
        try:
            await candidate.tool.invoke({"input": "q"})
        except Exception:
            continue
        break

    assert router_invocations == 1
    assert router_invocations < naive_invocations

    benchmark_recorder.record(
        "RouterFallbackVsNaive",
        router_invocations=router_invocations,
        naive_invocations=naive_invocations,
        saved=naive_invocations - router_invocations,
    )
    report = benchmark_recorder.report()
    assert report.metric("RouterFallbackVsNaive", "saved") is not None

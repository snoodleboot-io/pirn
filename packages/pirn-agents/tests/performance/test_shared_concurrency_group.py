"""Proof: the pattern that replaces ``Bulkhead`` bounds two pipelines together.

ADR agents-speaks-core, WS4b/PIR-866, checkbox: "add tests proving two
pipelines sharing a backend group are bounded together under one run." A
pipeline wired through the engine no longer reaches for
:class:`~pirn_agents.resilience.bulkhead.Bulkhead` at all: it declares
``KnotConfig(concurrency_group=<backend>)`` on the knots that call the
backend and ``ConcurrencyLimits(groups={<backend>: n})`` on the run. This is
a real ``Tapestry`` run, not a mock, showing that two independently-built
"pipelines" -- distinct knot ids, wired with no edge between them -- whose
knots all name the *same* concurrency group are metered by the run's one
shared budget, not one budget each (the isolation guarantee
:class:`~pirn_agents.resilience.bulkhead.Bulkhead` used to promise via two
separate private semaphores).
"""

from __future__ import annotations

import asyncio
from typing import Any

from pirn.core.concurrency.concurrency_limits import ConcurrencyLimits
from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry


class _PeakTracker:
    """Records the highest number of ``_BackendCall`` knots live at once."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self.live = 0
        self.peak = 0

    async def enter(self) -> None:
        async with self._lock:
            self.live += 1
            self.peak = max(self.peak, self.live)

    async def exit(self) -> None:
        async with self._lock:
            self.live -= 1


class _BackendCall(Knot):
    """One call to a shared backend; sleeps briefly to hold its slot under load.

    ``tracker`` is typed ``Any`` (not ``_PeakTracker``): ``Knot.__init__``
    builds a Pydantic ``TypeAdapter`` for every annotated ``process()``
    parameter, and an arbitrary, non-Pydantic class raises
    ``PydanticSchemaGenerationError`` there without
    ``arbitrary_types_allowed`` -- the same reason
    ``pirn_agents.batch._map_item._MapItem`` types its ``rate_limiter`` input
    ``Any``.
    """

    async def process(self, tracker: Any, delay: float, **_: Any) -> None:
        await tracker.enter()
        try:
            await asyncio.sleep(delay)
        finally:
            await tracker.exit()


class TestTwoPipelinesShareOneBackendGroup:
    async def test_peak_concurrency_is_bounded_across_both_pipelines(self) -> None:
        tracker = _PeakTracker()
        cap = 3
        per_pipeline = 6  # 12 calls total; if each pipeline had its own
        # budget of `cap`, peak could reach 2 * cap. One shared group must
        # hold the combined peak to `cap`.

        with Tapestry() as tapestry:
            for i in range(per_pipeline):
                _BackendCall(
                    tracker=tracker,
                    delay=0.01,
                    _config=KnotConfig(id=f"pipeline_a:{i}", concurrency_group="shared_backend"),
                )
            for i in range(per_pipeline):
                _BackendCall(
                    tracker=tracker,
                    delay=0.01,
                    _config=KnotConfig(id=f"pipeline_b:{i}", concurrency_group="shared_backend"),
                )

        await tapestry.run(
            RunRequest(concurrency=ConcurrencyLimits(groups={"shared_backend": cap}))
        )

        assert tracker.peak <= cap
        assert tracker.peak > 0  # the walk is not vacuous: calls actually ran

    async def test_an_unrelated_group_is_not_throttled_by_the_shared_one(self) -> None:
        tracker = _PeakTracker()
        unrelated_tracker = _PeakTracker()

        with Tapestry() as tapestry:
            for i in range(4):
                _BackendCall(
                    tracker=tracker,
                    delay=0.01,
                    _config=KnotConfig(id=f"shared:{i}", concurrency_group="shared_backend"),
                )
            for i in range(4):
                _BackendCall(
                    tracker=unrelated_tracker,
                    delay=0.01,
                    _config=KnotConfig(id=f"other:{i}", concurrency_group="other_backend"),
                )

        await tapestry.run(
            RunRequest(
                concurrency=ConcurrencyLimits(groups={"shared_backend": 1, "other_backend": 4})
            )
        )

        assert tracker.peak <= 1
        assert unrelated_tracker.peak <= 4
        assert unrelated_tracker.peak > 1  # the other group ran unthrottled by the tight one

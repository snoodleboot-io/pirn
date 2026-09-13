"""Tests for :meth:`TraceDiffer.diff_runs` (ADR "agents speaks core" WS3 part 3).

``diff_runs`` is a thin pass-through to ``pirn.knot_diff.compare_runs`` —
these exercise it against two real ``Tapestry.run()`` calls rather than
re-testing ``compare_runs`` itself.
"""

from __future__ import annotations

from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.knot_diff import KnotDiff
from pirn.tapestry import Tapestry

from pirn_agents.determinism.trace_differ import TraceDiffer


class Doubler(Knot):
    def __init__(self, x: Knot, **kwargs: Any) -> None:
        super().__init__(x=x, **kwargs)

    async def process(self, x: int, **_: Any) -> int:
        return x * 2


def _build_tapestry() -> Tapestry:
    tapestry = Tapestry()
    with tapestry:
        param = Parameter(name="x", type_=int)
        Doubler(x=param, _config=KnotConfig(id="double"))
    return tapestry


class TestTraceDifferDiffRuns:
    async def test_identical_runs_report_no_change(self) -> None:
        tapestry = _build_tapestry()
        left = await tapestry.run(RunRequest(parameters={"x": 5}))
        right = await tapestry.run(RunRequest(parameters={"x": 5}))

        diffs = TraceDiffer().diff_runs(left, right)

        assert all(isinstance(d, KnotDiff) for d in diffs)
        assert all(not d.changed for d in diffs)

    async def test_a_changed_input_is_reported_as_changed(self) -> None:
        tapestry = _build_tapestry()
        left = await tapestry.run(RunRequest(parameters={"x": 5}))
        right = await tapestry.run(RunRequest(parameters={"x": 99}))

        diffs = TraceDiffer().diff_runs(left, right)

        double_diff = next(d for d in diffs if d.knot_id == "double")
        assert double_diff.changed
        assert double_diff.output_changed

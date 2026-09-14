"""Characterise core ``Aggregator``'s behaviour with a ``Skipped`` parent.

ADR agents-speaks-core WS5a asks whether ``AttemptTier``/``CandidateAttempt``'s
hand-rolled fold-accumulator chains (a Python ``if prior.locked: return prior``
at the top of ``process()``) could instead be expressed as an ``Aggregator``
over N sibling attempts, picking whichever one actually ran. This test pins
down the two behaviours that decide the answer, by reading
``pirn/nodes/aggregator.py`` and ``pirn/engine/engine.py::_decide`` and
verifying them against a real ``Tapestry`` run rather than trusting the
docstrings alone.

Findings (see the WS5a report for the full writeup):

1. Under the default ``ErrorPolicy.SKIP_IF_PARENT_FAILED``, an ``Aggregator``
   with *any* ``Skipped`` (or ``Err``) parent is itself ``Skipped`` wholesale
   — ``combine`` never runs, and there is no way to ask "which parents
   actually produced a value". An Aggregator therefore cannot express "pick
   the first attempt that ran" when some attempts are legitimately skipped
   (a locked chain, a sub-threshold candidate) — it has no partial-success
   mode. This confirms the fold-accumulator chain was not a pointless
   workaround for something an ``Aggregator`` already solves.
2. Under ``ErrorPolicy.RECEIVE_ERRORS``, ``combine`` receives the raw
   ``Ok``/``Err``/``Skipped`` objects for every parent (never short-circuited)
   and can discriminate — this is the shape that *could* replace a fold
   chain, but it requires all N candidates to be constructed as sibling
   knots up front (a static ``Aggregator`` fan-in), which does not fit
   ``AttemptTier``/``CandidateAttempt``: each tier's decision to attempt at
   all depends on the *previous* tier's resolved outcome (locked / cost
   accrued so far), a genuine sequential dependency, not a static N-way
   fan-in over independently-computable siblings.
"""

from __future__ import annotations

import unittest

from pirn.core.err import Err
from pirn.core.error_policy import ErrorPolicy
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.skipped import Skipped
from pirn.nodes.aggregator import Aggregator
from pirn.nodes.gate.gate import Gate
from pirn.tapestry import Tapestry


class TestAggregatorWithASkippedParent(unittest.IsolatedAsyncioTestCase):
    async def test_default_policy_skips_the_whole_aggregator(self) -> None:
        """SKIP_IF_PARENT_FAILED (the default): one Skipped parent skips everything."""
        with Tapestry() as t:
            live = Parameter("live", int, default=1, _config=KnotConfig(id="live"))
            closed_gate = Gate(
                input=Parameter("closed_input", int, default=2, _config=KnotConfig(id="closed_in")),
                predicate=lambda _x: False,
                _config=KnotConfig(id="closed"),
            )
            Aggregator(
                combine=lambda live, closed: {"live": live, "closed": closed},
                live=live,
                closed=closed_gate,
                _config=KnotConfig(id="agg"),
            )
        result = await t.run(RunRequest())

        # The run as a whole still succeeds (a Skipped result is not a
        # failure); the Aggregator itself is Skipped, not partially combined.
        assert result.succeeded
        assert "agg" not in result.outputs
        aggregator_record = next(row for row in result.lineage if row.knot_id == "agg")
        assert aggregator_record.outcome == "skipped"

    async def test_receive_errors_policy_exposes_raw_results_to_combine(self) -> None:
        """RECEIVE_ERRORS: combine sees Ok/Err/Skipped directly and can discriminate."""
        captured: dict[str, object] = {}

        def combine(live: object, closed: object) -> str:
            captured["live"] = live
            captured["closed"] = closed
            # Discriminate exactly as a fold-accumulator's process() would.
            if isinstance(closed, Skipped):
                return "picked live (closed was skipped)"
            return "unreachable"

        with Tapestry() as t:
            live = Parameter("live", int, default=1, _config=KnotConfig(id="live"))
            closed_gate = Gate(
                input=Parameter("closed_input", int, default=2, _config=KnotConfig(id="closed_in")),
                predicate=lambda _x: False,
                _config=KnotConfig(id="closed"),
            )
            Aggregator(
                combine=combine,
                live=live,
                closed=closed_gate,
                _config=KnotConfig(id="agg", error_policy=ErrorPolicy.RECEIVE_ERRORS),
            )
        result = await t.run(RunRequest())

        assert result.succeeded
        assert result.outputs["agg"] == "picked live (closed was skipped)"
        assert isinstance(captured["live"], Ok)
        assert isinstance(captured["closed"], Skipped)

    async def test_receive_errors_policy_exposes_err_too(self) -> None:
        """RECEIVE_ERRORS surfaces a failed parent as an Err, not a skip."""

        class _Boom(Exception):
            pass

        async def _raise(**_: object) -> int:
            raise _Boom("nope")

        def combine(live: object, failing: object) -> str:
            if isinstance(failing, Err):
                return "picked live (other candidate errored)"
            return "unreachable"

        with Tapestry() as t:
            live = Parameter("live", int, default=1, _config=KnotConfig(id="live2"))
            failing = Aggregator(
                combine=_raise,
                seed=Parameter("seed", int, default=0, _config=KnotConfig(id="seed")),
                _config=KnotConfig(id="failing"),
            )
            Aggregator(
                combine=combine,
                live=live,
                failing=failing,
                _config=KnotConfig(id="agg2", error_policy=ErrorPolicy.RECEIVE_ERRORS),
            )
        result = await t.run(RunRequest())

        # The run as a whole is *not* `succeeded` -- the failing candidate's
        # exception is still recorded (RunResult.succeeded is `not
        # self.exceptions`, independent of whether anything downstream
        # consumed the Err) -- but the terminal we asked for still resolved,
        # because `agg2`'s combine discriminated on the raw Err.
        assert result.outputs["agg2"] == "picked live (other candidate errored)"


if __name__ == "__main__":
    unittest.main()

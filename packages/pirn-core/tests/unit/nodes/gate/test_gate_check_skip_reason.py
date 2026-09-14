"""A ``Check`` names the skip reason its closed ``Gate`` records and propagates (PIR-872).

Without a named reason a closed gate records ``"gate_closed"`` and every knot it
stops records the engine's generic ``"parent_failed_or_skipped"``.  A ``Check``
with ``skip_reason`` set makes both the gate's row and every downstream skipped
row carry that reason instead, so raw lineage says why the work did not run.
"""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.ok import Ok
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.core.run_result import RunResult
from pirn.core.skipped import Skipped
from pirn.engine.engine import Engine
from pirn.nodes.check import Check
from pirn.nodes.gate.gate import Gate
from pirn.recording.replay_session import ReplaySession
from pirn.tapestry import Tapestry


class _Deny(Check):
    """A check that always refuses, naming why."""

    skip_reason = "approval_denied"

    async def process(self, value: int, **_: Any) -> bool:
        return value < 0


class _Anonymous(Check):
    async def process(self, value: int, **_: Any) -> bool:
        return value < 0


class _Double(Knot):
    async def process(self, value: int, **_: Any) -> int:
        return value * 2


class _Sum(Knot):
    async def process(self, left: int, right: int, **_: Any) -> int:
        return left + right


class _Boom(Knot):
    async def process(self, **_: Any) -> int:
        raise RuntimeError("boom")


class _Predicates:
    @staticmethod
    def negative(value: int) -> bool:
        return value < 0


def _rows(result: RunResult) -> dict[str, str | None]:
    return {row.knot_id: row.skip_reason for row in result.lineage}


def _gated_chain(check_cls: type[Check]) -> Tapestry:
    with Tapestry() as t:
        value = Parameter("value", int, default=3, _config=KnotConfig(id="value"))
        verdict = check_cls(value=value, _config=KnotConfig(id="verdict"))
        gate = Gate(input=value, check=verdict, _config=KnotConfig(id="gate"))
        first = _Double(value=gate, _config=KnotConfig(id="first"))
        _Double(value=first, _config=KnotConfig(id="second"))
    return t


class TestANamedReasonIsRecordedAndPropagated(unittest.IsolatedAsyncioTestCase):
    async def test_the_gate_and_every_knot_it_stops_record_the_check_s_reason(self) -> None:
        # Arrange
        t = _gated_chain(_Deny)

        # Act
        result = await t.run(RunRequest())

        # Assert
        rows = _rows(result)
        self.assertEqual(rows["gate"], "approval_denied")
        self.assertEqual(rows["first"], "approval_denied")
        self.assertEqual(rows["second"], "approval_denied")

    async def test_an_unnamed_check_keeps_the_generic_reasons(self) -> None:
        result = await _gated_chain(_Anonymous).run(RunRequest())
        rows = _rows(result)
        self.assertEqual(rows["gate"], "gate_closed")
        self.assertEqual(rows["first"], "parent_failed_or_skipped")
        self.assertEqual(rows["second"], "parent_failed_or_skipped")

    async def test_an_open_gate_records_no_skip(self) -> None:
        with Tapestry() as t:
            value = Parameter("value", int, default=-1, _config=KnotConfig(id="value"))
            verdict = _Deny(value=value, _config=KnotConfig(id="verdict"))
            gate = Gate(input=value, check=verdict, _config=KnotConfig(id="gate"))
            _Double(value=gate, _config=KnotConfig(id="first"))
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["first"], -2)
        self.assertIsNone(_rows(result)["first"])

    async def test_a_predicate_gate_is_unchanged(self) -> None:
        with Tapestry() as t:
            value = Parameter("value", int, default=3, _config=KnotConfig(id="value"))
            gate = Gate(input=value, predicate=_Predicates.negative, _config=KnotConfig(id="gate"))
            _Double(value=gate, _config=KnotConfig(id="first"))
        result = await t.run(RunRequest())
        rows = _rows(result)
        self.assertEqual(rows["gate"], "gate_closed")
        self.assertEqual(rows["first"], "parent_failed_or_skipped")

    async def test_the_gate_process_names_the_reason(self) -> None:
        with Tapestry():
            value = Parameter("value", int, default=3, _config=KnotConfig(id="value"))
            gate = Gate(
                input=value,
                check=_Deny(value=value, _config=KnotConfig(id="verdict")),
                _config=KnotConfig(id="gate"),
            )
        self.assertEqual(gate.config_values["closed_reason"], "approval_denied")
        closed = await gate.process(input=3, check=False, closed_reason="approval_denied")
        self.assertEqual(closed, Skipped(reason="approval_denied", propagates=True))
        self.assertEqual(await gate.process(input=3, check=False), Skipped(reason="gate_closed"))

    async def test_a_replayed_run_serves_the_same_reasons(self) -> None:
        t = _gated_chain(_Deny)
        recorded = await t.run(RunRequest())
        session = await ReplaySession.from_history(history=t.history, run_id=recorded.run_id)
        replayed = await t.run(RunRequest(), replay=session)
        self.assertEqual(_rows(replayed)["second"], "approval_denied")


class TestPropagationNeedsOneSharedPropagatingReason(unittest.TestCase):
    def test_a_single_propagating_skip_is_inherited(self) -> None:
        parents: dict[str, Any] = {
            "a": Skipped(reason="approval_denied", propagates=True),
            "b": Ok(value=1),
        }
        self.assertEqual(Engine._propagated_skip_reason(parents), "approval_denied")

    def test_an_unpropagated_skip_beside_it_defeats_inheritance(self) -> None:
        parents: dict[str, Any] = {
            "a": Skipped(reason="approval_denied", propagates=True),
            "b": Skipped(reason="gate_closed"),
        }
        self.assertIsNone(Engine._propagated_skip_reason(parents))

    def test_two_different_propagating_reasons_are_not_inherited(self) -> None:
        parents: dict[str, Any] = {
            "a": Skipped(reason="approval_denied", propagates=True),
            "b": Skipped(reason="budget_spent", propagates=True),
        }
        self.assertIsNone(Engine._propagated_skip_reason(parents))

    def test_no_skipped_parent_has_nothing_to_inherit(self) -> None:
        self.assertIsNone(Engine._propagated_skip_reason({"a": Ok(value=1)}))


class TestAnErrParentKeepsTheGenericReason(unittest.IsolatedAsyncioTestCase):
    async def test_a_failed_and_a_denied_parent_record_the_generic_reason(self) -> None:
        with Tapestry() as t:
            value = Parameter("value", int, default=3, _config=KnotConfig(id="value"))
            verdict = _Deny(value=value, _config=KnotConfig(id="verdict"))
            gate = Gate(input=value, check=verdict, _config=KnotConfig(id="gate"))
            boom = _Boom(_config=KnotConfig(id="boom"))
            _Sum(left=gate, right=boom, _config=KnotConfig(id="sum"))
        result = await t.run(RunRequest())
        self.assertEqual(_rows(result)["sum"], "parent_failed_or_skipped")


if __name__ == "__main__":
    unittest.main()

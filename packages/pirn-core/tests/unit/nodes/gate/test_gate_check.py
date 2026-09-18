"""``Gate(check=...)`` — a ``Check`` knot as the gate's decision (WS0)."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.core.run_request import RunRequest
from pirn.nodes.check import Check
from pirn.nodes.gate.gate import Gate
from pirn.nodes.sink import Sink
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _ValSource(Source):
    def __init__(self, *, value: Any, **kwargs: Any) -> None:
        self._value = value
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> Any:
        return self._value


class _Capture(Sink):
    async def process(self, data: Any, **_: Any) -> None:
        pass


class _Under(Check):
    """Verdict over the gated value and a second parent: no join needed."""

    async def process(self, value: int, limit: int, **_: Any) -> bool:
        return value < limit


class _Broken(Check):
    async def process(self, value: int, **_: Any) -> bool:
        raise RuntimeError("no verdict")


def _pipeline(value: int, limit: int) -> Tapestry:
    with Tapestry() as t:
        src = _ValSource(value=value, _config=KnotConfig(id="src"))
        lim = Parameter("limit", int, default=limit, _config=KnotConfig(id="limit"))
        verdict = _Under(value=src, limit=lim, _config=KnotConfig(id="under"))
        gate = Gate(input=src, check=verdict, _config=KnotConfig(id="gate"))
        _Capture(data=gate, _config=KnotConfig(id="cap"))
    return t


class TestGateCheckConstruction(unittest.TestCase):
    def test_requires_exactly_one_decision(self) -> None:
        with Tapestry():
            src = _ValSource(value=1, _config=KnotConfig(id="src"))
            verdict = _Under(value=src, limit=2, _config=KnotConfig(id="under"))
            with self.assertRaisesRegex(TypeError, "exactly one"):
                Gate(input=src, _config=KnotConfig(id="g"))
            with self.assertRaisesRegex(TypeError, "exactly one"):
                Gate(input=src, predicate=bool, check=verdict, _config=KnotConfig(id="g"))

    def test_check_must_be_a_check_knot(self) -> None:
        with Tapestry():
            src = _ValSource(value=1, _config=KnotConfig(id="src"))
            with self.assertRaisesRegex(TypeError, "must be a Check"):
                Gate(input=src, check=src, _config=KnotConfig(id="g"))

    def test_the_check_is_a_parent_and_the_predicate_is_absent(self) -> None:
        with Tapestry():
            src = _ValSource(value=1, _config=KnotConfig(id="src"))
            verdict = _Under(value=src, limit=2, _config=KnotConfig(id="under"))
            gate = Gate(input=src, check=verdict, _config=KnotConfig(id="g"))
        self.assertEqual(set(gate.parents), {"input", "check"})
        self.assertEqual(gate.config_values, {})

    def test_a_predicate_gate_has_no_check_parent(self) -> None:
        with Tapestry():
            src = _ValSource(value=1, _config=KnotConfig(id="src"))
            gate = Gate(input=src, predicate=bool, _config=KnotConfig(id="g"))
        self.assertEqual(set(gate.parents), {"input"})


class TestGateCheckExecution(unittest.IsolatedAsyncioTestCase):
    async def test_a_true_verdict_passes_the_input_through_unchanged(self) -> None:
        # Arrange
        t = _pipeline(value=3, limit=10)

        # Act
        result = await t.run(RunRequest())

        # Assert: the gate's output is the gated value, not the verdict.
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["gate"], 3)
        self.assertIn("cap", result.outputs)
        gate_record = next(rec for rec in result.lineage if rec.knot_id == "gate")
        self.assertTrue(gate_record.extra["predicate_passed"])

    async def test_a_false_verdict_closes_the_gate_and_skips_downstream(self) -> None:
        # Arrange
        t = _pipeline(value=30, limit=10)

        # Act
        result = await t.run(RunRequest())

        # Assert
        self.assertTrue(result.succeeded)
        self.assertNotIn("gate", result.outputs)
        self.assertEqual(result.skipped, ["gate", "cap"])
        gate_record = next(rec for rec in result.lineage if rec.knot_id == "gate")
        self.assertEqual(gate_record.skip_reason, "gate_closed")
        self.assertFalse(gate_record.extra["predicate_passed"])

    async def test_a_failed_check_skips_the_gate_under_the_default_policy(self) -> None:
        # Arrange
        with Tapestry() as t:
            src = _ValSource(value=1, _config=KnotConfig(id="src"))
            verdict = _Broken(value=src, _config=KnotConfig(id="broken"))
            Gate(input=src, check=verdict, _config=KnotConfig(id="gate"))

        # Act
        result = await t.run(RunRequest())

        # Assert
        self.assertFalse(result.succeeded)
        self.assertEqual([rec.knot_id for rec in result.exceptions], ["broken"])
        self.assertEqual(result.skipped, ["gate"])

    async def test_predicate_gates_are_unchanged(self) -> None:
        with Tapestry() as t:
            src = _ValSource(value=5, _config=KnotConfig(id="src"))
            Gate(input=src, predicate=lambda v: v > 0, _config=KnotConfig(id="gate"))
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["gate"], 5)

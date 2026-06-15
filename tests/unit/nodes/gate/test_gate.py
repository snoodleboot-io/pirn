"""Unit tests for Gate."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
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


class TestGateConstruction(unittest.TestCase):
    def test_rejects_non_knot_input(self) -> None:
        with self.assertRaisesRegex(TypeError, "'input' must be a Knot"):
            with Tapestry():
                Gate(input=42, predicate=bool, _config=KnotConfig(id="g"))

    def test_rejects_non_callable_predicate(self) -> None:
        with self.assertRaisesRegex(TypeError, "'predicate' must be callable"):
            with Tapestry():
                src = _ValSource(value=1, _config=KnotConfig(id="src"))
                Gate(input=src, predicate="bad", _config=KnotConfig(id="g"))

    def test_requires_config(self) -> None:
        with self.assertRaisesRegex(TypeError, "_config"):
            with Tapestry():
                src = _ValSource(value=1, _config=KnotConfig(id="src"))
                Gate(input=src, predicate=bool)


class TestGateProcess(unittest.IsolatedAsyncioTestCase):
    async def test_truthy_predicate_passes_value(self) -> None:
        with Tapestry() as t:
            src = _ValSource(value=5, _config=KnotConfig(id="src"))
            Gate(input=src, predicate=lambda v: v > 0, _config=KnotConfig(id="gate"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(result.outputs["gate"], 5)

    async def test_falsy_predicate_produces_skipped(self) -> None:
        with Tapestry() as t:
            src = _ValSource(value=-1, _config=KnotConfig(id="src"))
            Gate(input=src, predicate=lambda v: v > 0, _config=KnotConfig(id="gate"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertNotIn("gate", result.outputs)

    async def test_skipped_reason_is_gate_closed(self) -> None:
        with Tapestry() as t:
            src = _ValSource(value=0, _config=KnotConfig(id="src"))
            Gate(input=src, predicate=bool, _config=KnotConfig(id="gate"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertNotIn("gate", result.outputs)

    async def test_downstream_of_closed_gate_is_skipped(self) -> None:
        with Tapestry() as t:
            src = _ValSource(value=0, _config=KnotConfig(id="src"))
            gate = Gate(input=src, predicate=bool, _config=KnotConfig(id="gate"))
            _Capture(data=gate, _config=KnotConfig(id="cap"))
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertNotIn("cap", result.outputs)

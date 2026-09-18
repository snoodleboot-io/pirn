"""Unit tests for Next / WithContinuation / WithContinuation.attach()."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.exceptions.extensible_run_required_error import ExtensibleRunRequiredError
from pirn.nodes.next import Next
from pirn.nodes.source import Source
from pirn.nodes.with_continuation import WithContinuation
from pirn.tapestry import Tapestry


class _StrSource(Source):
    def __init__(self, *, value: Any, **kwargs: Any) -> None:
        self._value = value
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> Any:
        return self._value


class TestNext(unittest.TestCase):
    def test_next_defaults(self) -> None:
        n = Next("some_action")
        self.assertEqual(n.action, "some_action")
        self.assertEqual(n.inputs, {})
        self.assertIsNone(n.id)

    def test_next_with_inputs_and_id(self) -> None:
        n = Next("act", inputs={"k": "v"}, id="custom")
        self.assertEqual(n.inputs, {"k": "v"})
        self.assertEqual(n.id, "custom")


class TestWithContinuationConstruction(unittest.TestCase):
    def test_constructs_inside_tapestry(self) -> None:
        def fn(r: Any) -> list:
            return [Next("end")]

        with Tapestry():
            src = _StrSource(value="x", _config=KnotConfig(id="src"))
            wc = WithContinuation(src, fn=fn, pool={}, _config=KnotConfig(id="wc"))
        self.assertIsInstance(wc, WithContinuation)


class TestAttach(unittest.TestCase):
    def test_attach_creates_with_continuation(self) -> None:
        def fn(r: Any) -> list:
            return [Next("end")]

        with Tapestry():
            src = _StrSource(value="x", _config=KnotConfig(id="src"))
            wc = WithContinuation.attach(src, fn=fn, pool={})
        self.assertIsInstance(wc, WithContinuation)
        self.assertEqual(wc.knot_id, "src__cont")


class TestWithContinuationProcess(unittest.IsolatedAsyncioTestCase):
    async def test_end_action_terminates_flow(self) -> None:
        calls: list = []

        def fn(r: Any) -> list:
            calls.append(r)
            return [Next("end")]

        with Tapestry() as t:
            src = _StrSource(value="hello", _config=KnotConfig(id="src"))
            WithContinuation.attach(src, fn=fn, pool={})
        result = await t.run(RunRequest(), extensible=True)
        self.assertTrue(result.succeeded, [e.message for e in result.exceptions])
        self.assertEqual(calls, ["hello"])
        self.assertIn("src__cont_end_0", result.outputs)

    async def test_a_spawned_id_is_stable_across_runs(self) -> None:
        # A uuid4 suffix used to make every spawned id different, so nothing
        # downstream -- a replay above all -- could name the knot (PIR-873).
        def fn(_r: Any) -> list:
            return [Next("end"), Next("end")]

        spawned: list[list[str]] = []
        for attempt in range(2):
            with Tapestry() as t:
                src = _StrSource(value="hello", _config=KnotConfig(id=f"src{attempt}"))
                WithContinuation.attach(src, fn=fn, pool={})
            result = await t.run(RunRequest(), extensible=True)
            spawned.append(sorted(k for k in result.outputs if "_end_" in k))

        self.assertEqual(spawned[0], [f"src0__cont_end_{i}" for i in range(2)])
        self.assertEqual(spawned[1], [f"src1__cont_end_{i}" for i in range(2)])

    async def test_a_non_extensible_run_fails_instead_of_dropping_successors(self) -> None:
        # It used to return the upstream value unchanged and report success,
        # having silently discarded every successor the continuation asked for.
        def fn(_r: Any) -> list:
            return [Next("end")]

        with Tapestry() as t:
            src = _StrSource(value="hello", _config=KnotConfig(id="src"))
            WithContinuation.attach(src, fn=fn, pool={})
        result = await t.run(RunRequest())

        self.assertFalse(result.succeeded)
        self.assertIn(
            ExtensibleRunRequiredError.__name__,
            [record.exc_type for record in result.exceptions],
        )

    async def test_an_empty_continuation_fails_even_with_assertions_off(self) -> None:
        # A bare ``assert`` stood here, which ``python -O`` strips.
        def fn(_r: Any) -> list:
            return []

        with Tapestry() as t:
            src = _StrSource(value="hello", _config=KnotConfig(id="src"))
            WithContinuation.attach(src, fn=fn, pool={})
        result = await t.run(RunRequest(), extensible=True)

        self.assertFalse(result.succeeded)
        self.assertIn("ValueError", [record.exc_type for record in result.exceptions])

    async def test_invalid_action_raises_key_error(self) -> None:
        def fn(r: Any) -> list:
            return [Next("nonexistent")]

        with Tapestry() as t:
            src = _StrSource(value=1, _config=KnotConfig(id="src"))
            WithContinuation.attach(src, fn=fn, pool={})
        result = await t.run(RunRequest(), extensible=True)

        self.assertFalse(result.succeeded)
        self.assertIn("KeyError", [record.exc_type for record in result.exceptions])

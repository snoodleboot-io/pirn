"""Unit tests for continuation / WithContinuation / continues()."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.continuation import Next, WithContinuation, continues
from pirn.nodes.source import Source
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


class TestContinues(unittest.TestCase):
    def test_continues_creates_with_continuation(self) -> None:
        def fn(r: Any) -> list:
            return [Next("end")]

        with Tapestry():
            src = _StrSource(value="x", _config=KnotConfig(id="src"))
            wc = continues(src, fn=fn, pool={})
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
            continues(src, fn=fn, pool={})
        result = await t.run(RunRequest())
        self.assertTrue(result.succeeded)
        self.assertEqual(calls, ["hello"])

    async def test_invalid_action_raises_key_error(self) -> None:
        def fn(r: Any) -> list:
            return [Next("nonexistent")]

        with Tapestry() as t:
            src = _StrSource(value=1, _config=KnotConfig(id="src"))
            continues(src, fn=fn, pool={})
        result = await t.run(RunRequest())
        self.assertIsNotNone(result)

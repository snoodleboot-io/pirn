"""Unit tests for Sink."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.sink import Sink
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _IntSource(Source):
    async def process(self, **_: Any) -> int:
        return 7


class _CollectingSink(Sink):
    _collected: list = []

    async def process(self, value: Any, **_: Any) -> None:
        _CollectingSink._collected.append(value)


class TestSinkConstruction(unittest.TestCase):
    def test_sink_is_knot_subclass(self) -> None:
        self.assertTrue(issubclass(Sink, Knot))

    def test_sink_constructs_with_parent(self) -> None:
        with Tapestry():
            src = _IntSource(_config=KnotConfig(id="src"))
            sink = _CollectingSink(value=src, _config=KnotConfig(id="sink"))
        self.assertIsNotNone(sink)


class TestSinkProcess(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        _CollectingSink._collected = []

    async def test_sink_receives_parent_output(self) -> None:
        with Tapestry() as t:
            src = _IntSource(_config=KnotConfig(id="src"))
            _CollectingSink(value=src, _config=KnotConfig(id="sink"))
        await t.run(RunRequest())
        self.assertIn(7, _CollectingSink._collected)

    async def test_sink_output_is_none(self) -> None:
        with Tapestry() as t:
            src = _IntSource(_config=KnotConfig(id="src"))
            _CollectingSink(value=src, _config=KnotConfig(id="sink"))
        result = await t.run(RunRequest())
        self.assertIsNone(result.outputs["sink"])

"""Unit tests for Source."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _ConstSource(Source):
    def __init__(self, *, value: Knot | Any, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(value=value, _config=_config, **kwargs)

    async def process(self, *, value: Any, **_: Any) -> Any:
        return value


class TestSourceConstruction(unittest.TestCase):
    def test_valid_source_constructs(self) -> None:
        with Tapestry():
            src = _ConstSource(value=42, _config=KnotConfig(id="src"))
        self.assertIsInstance(src, Source)

    def test_source_is_knot_subclass(self) -> None:
        self.assertTrue(issubclass(Source, Knot))

    def test_source_accepts_knot_input(self) -> None:
        with Tapestry():
            upstream = _ConstSource(value=1, _config=KnotConfig(id="up"))
            src = _ConstSource(value=upstream, _config=KnotConfig(id="src"))
        self.assertIsInstance(src, Source)


class TestSourceProcess(unittest.IsolatedAsyncioTestCase):
    async def test_source_produces_value(self) -> None:
        with Tapestry() as t:
            _ConstSource(value=99, _config=KnotConfig(id="src"))
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["src"], 99)

    async def test_source_produces_dict_value(self) -> None:
        with Tapestry() as t:
            _ConstSource(value={"a": 1}, _config=KnotConfig(id="src"))
        result = await t.run(RunRequest())
        self.assertEqual(result.outputs["src"], {"a": 1})

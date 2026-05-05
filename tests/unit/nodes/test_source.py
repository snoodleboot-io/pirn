"""Unit tests for Source."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.nodes.source import Source
from pirn.tapestry import Tapestry


class _ConstSource(Source):
    def __init__(self, *, value: Any, **kwargs: Any) -> None:
        self._value = value
        super().__init__(**kwargs)

    async def process(self, **_: Any) -> Any:
        return self._value


class TestSourceConstruction(unittest.TestCase):
    def test_valid_source_constructs(self) -> None:
        with Tapestry():
            src = _ConstSource(value=42, _config=KnotConfig(id="src"))
        self.assertIsInstance(src, Source)

    def test_source_rejects_knot_parent_kwarg(self) -> None:
        with self.assertRaises(TypeError):
            with Tapestry():
                other = _ConstSource(value=1, _config=KnotConfig(id="other"))
                _ConstSource(value=2, extra=other, _config=KnotConfig(id="src"))

    def test_source_rejects_any_extra_kwarg(self) -> None:
        with self.assertRaisesRegex(TypeError, "takes no inputs"):
            with Tapestry():
                _ConstSource(value=2, extra_arg="x", _config=KnotConfig(id="src"))

    def test_source_is_knot_subclass(self) -> None:
        self.assertTrue(issubclass(Source, Knot))


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

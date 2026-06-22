"""Tests for :class:`DerivedColumnCalculator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_data.specializations.feature_engineering.derived_column_calculator import (
    DerivedColumnCalculator,
)


def _make_knot(expressions: list, **overrides: Any) -> DerivedColumnCalculator:
    return DerivedColumnCalculator(
        rows=[], expressions=expressions, **overrides, _config=KnotConfig(id="derived")
    )


class TestDerivedColumnCalculator(unittest.IsolatedAsyncioTestCase):
    async def test_arithmetic_expression(self) -> None:
        rows = [{"price": 100, "qty": 3}]
        exprs = [{"column": "total", "expression": "price * qty"}]
        k = _make_knot(exprs)
        result = await k.process(rows=rows, expressions=exprs)
        assert result[0]["total"] == 300

    async def test_constant_expression(self) -> None:
        rows = [{"x": 1}]
        exprs = [{"column": "flag", "expression": "42"}]
        k = _make_knot(exprs)
        result = await k.process(rows=rows, expressions=exprs)
        assert result[0]["flag"] == 42

    async def test_comparison_expression(self) -> None:
        rows = [{"score": 80}, {"score": 50}]
        exprs = [{"column": "pass_", "expression": "score >= 60"}]
        k = _make_knot(exprs)
        result = await k.process(rows=rows, expressions=exprs)
        assert result[0]["pass_"] is True
        assert result[1]["pass_"] is False

    async def test_chained_expressions(self) -> None:
        rows = [{"a": 2}]
        exprs = [
            {"column": "b", "expression": "a * 3"},
            {"column": "c", "expression": "b + 1"},
        ]
        k = _make_knot(exprs)
        result = await k.process(rows=rows, expressions=exprs)
        assert result[0]["b"] == 6
        assert result[0]["c"] == 7

    async def test_floor_division(self) -> None:
        rows = [{"v": 7}]
        exprs = [{"column": "q", "expression": "v // 2"}]
        k = _make_knot(exprs)
        result = await k.process(rows=rows, expressions=exprs)
        assert result[0]["q"] == 3

    async def test_unknown_column_raises(self) -> None:
        rows = [{"x": 1}]
        exprs = [{"column": "y", "expression": "missing_col + 1"}]
        k = _make_knot(exprs)
        with self.assertRaisesRegex(ValueError, "missing_col"):
            await k.process(rows=rows, expressions=exprs)

    async def test_empty_input(self) -> None:
        exprs = [{"column": "z", "expression": "1 + 1"}]
        k = _make_knot(exprs)
        result = await k.process(rows=[], expressions=exprs)
        assert result == []

    async def test_tapestry_run(self) -> None:
        rows = [{"x": 5}]
        exprs = [{"column": "y", "expression": "x + 1"}]
        with Tapestry() as t:
            DerivedColumnCalculator(rows=rows, expressions=exprs, _config=KnotConfig(id="d"))
        result = await t.run(RunRequest())
        assert result.succeeded
        assert result.outputs["d"][0]["y"] == 6


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        @knot
        async def emit_rows() -> list:
            return [{"x": 10}]

        exprs = [{"column": "y", "expression": "x * 2"}]
        with Tapestry() as t:
            rows_knot = emit_rows(_config=KnotConfig(id="rows"))
            DerivedColumnCalculator(
                rows=rows_knot,
                expressions=exprs,
                _config=KnotConfig(id="derived"),
            )
        result = await t.run(RunRequest())
        assert result.outputs["derived"][0]["y"] == 20


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, expressions: list) -> DerivedColumnCalculator:
        with Tapestry():
            return DerivedColumnCalculator(
                rows=[], expressions=expressions, _config=KnotConfig(id="val")
            )

    async def test_rejects_invalid_output_column(self) -> None:
        exprs = [{"column": "bad col", "expression": "1 + 1"}]
        k = self._make_knot(exprs)
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await k.process(rows=[], expressions=exprs)

    async def test_rejects_syntax_error(self) -> None:
        exprs = [{"column": "x", "expression": "1 +* 2"}]
        k = self._make_knot(exprs)
        with self.assertRaisesRegex(ValueError, "invalid expression"):
            await k.process(rows=[], expressions=exprs)

    async def test_rejects_empty_expression(self) -> None:
        exprs = [{"column": "x", "expression": ""}]
        k = self._make_knot(exprs)
        with self.assertRaisesRegex(ValueError, "expression"):
            await k.process(rows=[], expressions=exprs)

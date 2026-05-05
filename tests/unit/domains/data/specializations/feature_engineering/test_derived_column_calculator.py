"""Tests for :class:`DerivedColumnCalculator`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.feature_engineering.derived_column_calculator import (
    DerivedColumnCalculator,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(expressions):
    with Tapestry():
        knot = DerivedColumnCalculator(
            rows=_rows_param(),
            expressions=expressions,
            _config=KnotConfig(id="derived"),
        )
    return knot


class TestConstruction(unittest.TestCase):
    def test_rejects_invalid_output_column(self) -> None:
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            _make([{"column": "bad col", "expression": "1 + 1"}])

    def test_rejects_syntax_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "invalid expression"):
            _make([{"column": "x", "expression": "1 +* 2"}])

    def test_rejects_empty_expression(self) -> None:
        with self.assertRaisesRegex(ValueError, "expression"):
            _make([{"column": "x", "expression": ""}])


class TestBehaviour(unittest.IsolatedAsyncioTestCase):
    async def test_arithmetic_expression(self) -> None:
        rows = [{"price": 100, "qty": 3}]
        knot = _make([{"column": "total", "expression": "price * qty"}])
        result = await knot.process(rows=rows)
        assert result[0]["total"] == 300

    async def test_constant_expression(self) -> None:
        rows = [{"x": 1}]
        knot = _make([{"column": "flag", "expression": "42"}])
        result = await knot.process(rows=rows)
        assert result[0]["flag"] == 42

    async def test_comparison_expression(self) -> None:
        rows = [{"score": 80}, {"score": 50}]
        knot = _make([{"column": "pass_", "expression": "score >= 60"}])
        result = await knot.process(rows=rows)
        assert result[0]["pass_"] is True
        assert result[1]["pass_"] is False

    async def test_chained_expressions(self) -> None:
        rows = [{"a": 2}]
        knot = _make([
            {"column": "b", "expression": "a * 3"},
            {"column": "c", "expression": "b + 1"},
        ])
        result = await knot.process(rows=rows)
        assert result[0]["b"] == 6
        assert result[0]["c"] == 7

    async def test_floor_division(self) -> None:
        rows = [{"v": 7}]
        knot = _make([{"column": "q", "expression": "v // 2"}])
        result = await knot.process(rows=rows)
        assert result[0]["q"] == 3

    async def test_unknown_column_raises(self) -> None:
        rows = [{"x": 1}]
        knot = _make([{"column": "y", "expression": "missing_col + 1"}])
        with self.assertRaisesRegex(ValueError, "missing_col"):
            await knot.process(rows=rows)

    async def test_empty_input(self) -> None:
        knot = _make([{"column": "z", "expression": "1 + 1"}])
        result = await knot.process(rows=[])
        assert result == []

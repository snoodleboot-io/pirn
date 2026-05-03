"""Tests for :class:`BinningKnot`."""

from __future__ import annotations

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.data.specializations.feature_engineering.binning_knot import (
    BinningKnot,
)
from pirn.tapestry import Tapestry



def _rows_param():
    return Parameter("rows", list, _config=KnotConfig(id="rows"))


def _make(**kwargs):
    with Tapestry():
        knot = BinningKnot(
            rows=_rows_param(),
            **kwargs,
            _config=KnotConfig(id="binning"),
        )
    return knot


class TestConstruction:
    def test_rejects_non_positive_bins(self) -> None:
        with pytest.raises(ValueError, match="num_bins"):
            _make(column="v", num_bins=0)

    def test_rejects_invalid_strategy(self) -> None:
        with pytest.raises(ValueError, match="strategy"):
            _make(column="v", num_bins=3, strategy="kmeans")

    def test_rejects_invalid_column(self) -> None:
        with pytest.raises(ValueError, match="plain identifier"):
            _make(column="bad col", num_bins=3)


@pytest.mark.asyncio
class TestBehaviour:
    async def test_equal_width_three_bins(self) -> None:
        rows = [{"v": float(i)} for i in range(1, 10)]
        knot = _make(column="v", num_bins=3, strategy="equal_width")
        result = await knot.process(rows=rows)
        bins = {r["v_bin"] for r in result}
        assert bins == {1, 2, 3}

    async def test_quantile_three_bins(self) -> None:
        rows = [{"v": float(i)} for i in range(1, 10)]
        knot = _make(column="v", num_bins=3, strategy="quantile")
        result = await knot.process(rows=rows)
        bins = {r["v_bin"] for r in result}
        assert bins == {1, 2, 3}

    async def test_output_column_name(self) -> None:
        rows = [{"score": 50.0}]
        knot = _make(column="score", num_bins=2)
        result = await knot.process(rows=rows)
        assert "score_bin" in result[0]

    async def test_single_value_assigned_bin(self) -> None:
        rows = [{"v": 5.0}]
        knot = _make(column="v", num_bins=3)
        result = await knot.process(rows=rows)
        assert isinstance(result[0]["v_bin"], int)

    async def test_original_column_preserved(self) -> None:
        rows = [{"v": 3.0, "label": "x"}]
        knot = _make(column="v", num_bins=2)
        result = await knot.process(rows=rows)
        assert result[0]["v"] == 3.0
        assert result[0]["label"] == "x"

    async def test_empty_input(self) -> None:
        knot = _make(column="v", num_bins=3)
        result = await knot.process(rows=[])
        assert result == []

"""Tests for :class:`BinningKnot`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.data.specializations.feature_engineering.binning_knot import BinningKnot
from pirn.tapestry import Tapestry


def _make_knot(**overrides: Any) -> BinningKnot:
    defaults: dict[str, Any] = {
        "column": "v",
        "num_bins": 3,
        "strategy": "equal_width",
    }
    defaults.update(overrides)
    return BinningKnot(rows=[], **defaults, _config=KnotConfig(id="binning"))


class TestBinningKnot(unittest.IsolatedAsyncioTestCase):
    async def test_equal_width_three_bins(self) -> None:
        rows = [{"v": float(i)} for i in range(1, 10)]
        with Tapestry() as t:
            _make_knot()
        result = await t.run(RunRequest())
        assert result.succeeded
        # process() receives resolved rows — test directly via process()
        k = _make_knot()
        out = await k.process(rows=rows, column="v", num_bins=3, strategy="equal_width")
        bins = {r["v_bin"] for r in out}
        assert bins == {1, 2, 3}

    async def test_quantile_three_bins(self) -> None:
        rows = [{"v": float(i)} for i in range(1, 10)]
        k = _make_knot(strategy="quantile")
        out = await k.process(rows=rows, column="v", num_bins=3, strategy="quantile")
        bins = {r["v_bin"] for r in out}
        assert bins == {1, 2, 3}

    async def test_output_column_name(self) -> None:
        rows = [{"score": 50.0}]
        k = _make_knot(column="score", num_bins=2)
        out = await k.process(rows=rows, column="score", num_bins=2, strategy="equal_width")
        assert "score_bin" in out[0]

    async def test_original_column_preserved(self) -> None:
        rows = [{"v": 3.0, "label": "x"}]
        k = _make_knot()
        out = await k.process(rows=rows, column="v", num_bins=2, strategy="equal_width")
        assert out[0]["v"] == 3.0
        assert out[0]["label"] == "x"

    async def test_empty_input(self) -> None:
        k = _make_knot()
        out = await k.process(rows=[], column="v", num_bins=3, strategy="equal_width")
        assert out == []

    async def test_tapestry_run(self) -> None:
        rows = [{"v": 1.0}, {"v": 5.0}, {"v": 9.0}]
        with Tapestry() as t:
            k = BinningKnot(
                rows=rows, column="v", num_bins=3, strategy="equal_width",
                _config=KnotConfig(id="b"),
            )
        result = await t.run(RunRequest())
        assert result.succeeded
        assert len(result.outputs["b"]) == 3


class TestWiring(unittest.IsolatedAsyncioTestCase):
    async def test_rows_from_upstream_knot(self) -> None:
        @knot
        async def emit_rows() -> list:
            return [{"v": float(i)} for i in range(1, 10)]

        with Tapestry() as t:
            rows_knot = emit_rows(_config=KnotConfig(id="rows"))
            BinningKnot(
                rows=rows_knot,
                column="v",
                num_bins=3,
                strategy="equal_width",
                _config=KnotConfig(id="binning"),
            )
        result = await t.run(RunRequest())
        assert len(result.outputs["binning"]) == 9


class TestValidation(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, **kwargs: Any) -> BinningKnot:
        defaults: dict[str, Any] = {
            "column": "v",
            "num_bins": 3,
            "strategy": "equal_width",
        }
        defaults.update(kwargs)
        with Tapestry():
            return BinningKnot(rows=[], **defaults, _config=KnotConfig(id="val"))

    async def _call(self, k: BinningKnot, **overrides: Any) -> Any:
        args: dict[str, Any] = {
            "rows": [{"v": 1.0}],
            "column": "v",
            "num_bins": 3,
            "strategy": "equal_width",
        }
        args.update(overrides)
        return await k.process(**args)

    async def test_rejects_invalid_column(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "plain identifier"):
            await self._call(k, column="bad col")

    async def test_rejects_non_positive_bins(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "num_bins"):
            await self._call(k, num_bins=0)

    async def test_rejects_invalid_strategy(self) -> None:
        k = self._make_knot()
        with self.assertRaisesRegex(ValueError, "strategy"):
            await self._call(k, strategy="kmeans")

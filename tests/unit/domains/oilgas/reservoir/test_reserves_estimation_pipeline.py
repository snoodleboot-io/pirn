"""Unit tests for :class:`ReservesEstimationPipeline`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn_oilgas.reservoir.reserves_estimation_pipeline import (
    ReservesEstimationPipeline,
)

_HISTORY: list[dict[str, Any]] = [
    {"date_iso": "2020-01-01", "rate_bopd": 500.0},
    {"date_iso": "2021-01-01", "rate_bopd": 400.0},
    {"date_iso": "2022-01-01", "rate_bopd": 320.0},
]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> ReservesEstimationPipeline:
        return ReservesEstimationPipeline(
            production_history=None,  # type: ignore[arg-type]
            economic_limit_bopd=5.0,
            royalty_rate=0.2,
            _config=KnotConfig(id="rep", validate_io=False),
        )

    async def test_rejects_non_positive_economic_limit(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "economic_limit_bopd"):
            await knot.process(
                production_history=_HISTORY,
                economic_limit_bopd=0.0,
                royalty_rate=0.2,
            )

    async def test_rejects_invalid_royalty_rate(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "royalty_rate"):
            await knot.process(
                production_history=_HISTORY,
                economic_limit_bopd=5.0,
                royalty_rate=1.0,
            )

    async def test_returns_reserves_categories(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            production_history=_HISTORY,
            economic_limit_bopd=5.0,
            royalty_rate=0.2,
        )
        assert "proved_reserves_mbo" in out
        assert "probable_reserves_mbo" in out
        assert "possible_reserves_mbo" in out
        assert "eur_mbo" in out
        assert out["proved_reserves_mbo"] > 0.0

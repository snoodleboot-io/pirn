"""Unit tests for :class:`ReservesEstimationPipeline`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.reserves_estimation_pipeline import (
    ReservesEstimationPipeline,
)
from pirn.tapestry import Tapestry


class _HistorySource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"date_iso": "2020-01-01", "rate_bopd": 500.0},
            {"date_iso": "2021-01-01", "rate_bopd": 400.0},
            {"date_iso": "2022-01-01", "rate_bopd": 320.0},
        ]


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_economic_limit(self) -> None:
        with self.assertRaisesRegex(ValueError, "economic_limit_bopd"):
            with Tapestry():
                src = _HistorySource(_config=KnotConfig(id="src"))
                ReservesEstimationPipeline(
                    production_history=src,
                    economic_limit_bopd=0.0,
                    royalty_rate=0.2,
                    _config=KnotConfig(id="rep"),
                )

    def test_rejects_invalid_royalty_rate(self) -> None:
        with self.assertRaisesRegex(ValueError, "royalty_rate"):
            with Tapestry():
                src = _HistorySource(_config=KnotConfig(id="src"))
                ReservesEstimationPipeline(
                    production_history=src,
                    economic_limit_bopd=5.0,
                    royalty_rate=1.0,
                    _config=KnotConfig(id="rep"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_reserves_categories(self) -> None:
        with Tapestry() as t:
            src = _HistorySource(_config=KnotConfig(id="src"))
            ReservesEstimationPipeline(
                production_history=src,
                economic_limit_bopd=5.0,
                royalty_rate=0.2,
                _config=KnotConfig(id="rep"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["rep"]
        assert "proved_reserves_mbo" in out
        assert "probable_reserves_mbo" in out
        assert "possible_reserves_mbo" in out
        assert "eur_mbo" in out
        assert out["proved_reserves_mbo"] > 0.0

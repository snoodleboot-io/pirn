"""Unit tests for :class:`CorrosionRateEstimator`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.integrity.corrosion_rate_estimator import (
    CorrosionRateEstimator,
)

_RUN: dict[str, Any] = {"feature_count": 10}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self, years: float = 5.0) -> CorrosionRateEstimator:
        return CorrosionRateEstimator(
            previous_run=None,  # type: ignore[arg-type]
            current_run=None,  # type: ignore[arg-type]
            years_between=years,
            _config=KnotConfig(id="cre", validate_io=False),
        )

    async def test_rejects_non_numeric_years(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "years_between"):
            await knot.process(previous_run=_RUN, current_run=_RUN, years_between="x")  # type: ignore[arg-type]

    async def test_rejects_non_positive_years(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "positive"):
            await knot.process(previous_run=_RUN, current_run=_RUN, years_between=0.0)

    async def test_returns_corrosion_rate(self) -> None:
        knot = self._make_knot(years=5.0)
        out = await knot.process(previous_run=_RUN, current_run=_RUN, years_between=5.0)
        assert out["max_rate_mpy"] == 5.0
        assert out["feature_count"] == 10.0

    async def test_raises_on_missing_feature_count_field(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(KeyError, "feature_count"):
            await knot.process(previous_run=_RUN, current_run={}, years_between=5.0)

    async def test_custom_feature_count_field(self) -> None:
        knot = self._make_knot()
        custom_run: dict[str, Any] = {"anomaly_count": 7}
        out = await knot.process(
            previous_run=_RUN, current_run=custom_run, years_between=5.0,
            feature_count_field="anomaly_count",
        )
        assert out["feature_count"] == 7.0

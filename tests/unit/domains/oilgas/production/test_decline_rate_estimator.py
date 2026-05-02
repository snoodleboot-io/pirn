"""Unit tests for :class:`DeclineRateEstimator`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.decline_rate_estimator import DeclineRateEstimator
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _Source(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="rate")


class TestConstruction:
    def test_rejects_non_positive_window(self) -> None:
        with pytest.raises(ValueError, match="window_days"):
            with Tapestry():
                src = _Source(_config=KnotConfig(id="src"))
                DeclineRateEstimator(
                    rate_series=src,
                    window_days=0,
                    _config=KnotConfig(id="dr"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_rate(self) -> None:
        with Tapestry() as t:
            src = _Source(_config=KnotConfig(id="src"))
            DeclineRateEstimator(
                rate_series=src,
                window_days=90,
                _config=KnotConfig(id="dr"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["dr"]
        assert isinstance(out, float)
        assert out == 0.15

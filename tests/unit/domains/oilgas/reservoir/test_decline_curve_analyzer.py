"""Unit tests for :class:`DeclineCurveAnalyzer`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.reservoir.decline_curve_analyzer import DeclineCurveAnalyzer
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _RateSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="s")


class TestConstruction:
    def test_rejects_invalid_method(self) -> None:
        with pytest.raises(ValueError, match="method"):
            with Tapestry():
                src = _RateSource(_config=KnotConfig(id="src"))
                DeclineCurveAnalyzer(
                    rate_series=src,
                    method="bogus",
                    _config=KnotConfig(id="dca"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_decline_params(self) -> None:
        with Tapestry() as t:
            src = _RateSource(_config=KnotConfig(id="src"))
            DeclineCurveAnalyzer(
                rate_series=src,
                method="hyperbolic",
                _config=KnotConfig(id="dca"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["dca"]
        assert "qi" in out
        assert "di_per_year" in out
        assert out["b"] == 0.5

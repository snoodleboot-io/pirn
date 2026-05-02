"""Unit tests for :class:`WaterInjectionTracker`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.water_injection_tracker import (
    WaterInjectionTracker,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _Source(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="inj", sample_interval_sec=60.0)


class TestConstruction:
    def test_requires_injection_rate(self) -> None:
        with pytest.raises(TypeError, match="injection_rate"):
            WaterInjectionTracker(_config=KnotConfig(id="wi"))  # type: ignore[call-arg]


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_cumulative_series(self) -> None:
        with Tapestry() as t:
            src = _Source(_config=KnotConfig(id="src"))
            WaterInjectionTracker(
                injection_rate=src, _config=KnotConfig(id="wi")
            )
        result = await t.run(RunRequest())
        out = result.outputs["wi"]
        assert isinstance(out, ScadaTimeSeries)
        assert "cumulative_inj" in out.sensor_id

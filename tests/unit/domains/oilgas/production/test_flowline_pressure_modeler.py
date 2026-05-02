"""Unit tests for :class:`FlowlinePressureModeler`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.flowline_pressure_modeler import (
    FlowlinePressureModeler,
)
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries
from pirn.tapestry import Tapestry


class _Source(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> ScadaTimeSeries:
        return ScadaTimeSeries(sensor_id="rate", sample_interval_sec=60.0)


class TestConstruction:
    def test_rejects_non_positive_diameter(self) -> None:
        with pytest.raises(ValueError, match="pipe_inner_diameter_in"):
            with Tapestry():
                src = _Source(_config=KnotConfig(id="src"))
                FlowlinePressureModeler(
                    rate_series=src,
                    pipe_inner_diameter_in=0.0,
                    pipe_length_ft=1000.0,
                    _config=KnotConfig(id="fp"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_dp_series(self) -> None:
        with Tapestry() as t:
            src = _Source(_config=KnotConfig(id="src"))
            FlowlinePressureModeler(
                rate_series=src,
                pipe_inner_diameter_in=4.0,
                pipe_length_ft=1000.0,
                _config=KnotConfig(id="fp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fp"]
        assert isinstance(out, ScadaTimeSeries)
        assert "dp:" in out.sensor_id

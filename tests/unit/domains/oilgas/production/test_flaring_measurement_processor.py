"""Unit tests for :class:`FlaringMeasurementProcessor`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.flaring_measurement_processor import (
    FlaringMeasurementProcessor,
)
from pirn.tapestry import Tapestry


class _MeasurementsSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"start_iso": "2026-01-01T00:00:00Z", "end_iso": "2026-01-01T06:00:00Z", "flow_rate_mmscfd": 2.0},
            {"start_iso": "2026-01-02T00:00:00Z", "end_iso": "2026-01-02T03:00:00Z", "flow_rate_mmscfd": 1.0},
        ]


class TestConstruction:
    def test_rejects_invalid_efficiency_factor(self) -> None:
        with pytest.raises(ValueError, match="efficiency_factor"):
            with Tapestry():
                src = _MeasurementsSource(_config=KnotConfig(id="src"))
                FlaringMeasurementProcessor(
                    measurements=src,
                    gas_composition={"co2": 0.05},
                    efficiency_factor=0.0,
                    _config=KnotConfig(id="fp"),
                )

    def test_rejects_non_dict_composition(self) -> None:
        with pytest.raises(TypeError, match="gas_composition"):
            with Tapestry():
                src = _MeasurementsSource(_config=KnotConfig(id="src"))
                FlaringMeasurementProcessor(
                    measurements=src,
                    gas_composition="not_a_dict",  # type: ignore[arg-type]
                    efficiency_factor=0.98,
                    _config=KnotConfig(id="fp"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_flaring_summary(self) -> None:
        with Tapestry() as t:
            src = _MeasurementsSource(_config=KnotConfig(id="src"))
            FlaringMeasurementProcessor(
                measurements=src,
                gas_composition={"co2": 0.05, "ch4": 0.85},
                efficiency_factor=0.98,
                _config=KnotConfig(id="fp"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fp"]
        assert out["event_count"] == 2
        assert isinstance(out["total_flared_mmscf"], float)
        assert isinstance(out["co2_tonnes"], float)

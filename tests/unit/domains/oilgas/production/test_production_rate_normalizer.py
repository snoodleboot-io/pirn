"""Unit tests for :class:`ProductionRateNormalizer`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.production.production_rate_normalizer import (
    ProductionRateNormalizer,
)
from pirn.tapestry import Tapestry


class _MeasurementsSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"rate_bopd": 500.0, "wellhead_pressure_psia": 100.0, "wellhead_temp_f": 120.0},
        ]


class TestConstruction:
    def test_rejects_non_positive_pressure(self) -> None:
        with pytest.raises(ValueError, match="reference_pressure_psia"):
            with Tapestry():
                src = _MeasurementsSource(_config=KnotConfig(id="src"))
                ProductionRateNormalizer(
                    measurements=src,
                    reference_pressure_psia=0.0,
                    reference_temp_f=60.0,
                    _config=KnotConfig(id="prn"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_normalized_rates(self) -> None:
        with Tapestry() as t:
            src = _MeasurementsSource(_config=KnotConfig(id="src"))
            ProductionRateNormalizer(
                measurements=src,
                reference_pressure_psia=14.7,
                reference_temp_f=60.0,
                _config=KnotConfig(id="prn"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["prn"]
        assert isinstance(out, list)
        assert len(out) == 1
        assert "normalized_rate_bopd" in out[0]

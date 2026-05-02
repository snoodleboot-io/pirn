"""Unit tests for :class:`CorrosionRateEstimator`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.integrity.corrosion_rate_estimator import (
    CorrosionRateEstimator,
)
from pirn.tapestry import Tapestry


class _PigRunSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"feature_count": 10}


class TestConstruction:
    def test_rejects_non_numeric_years(self) -> None:
        with pytest.raises(TypeError, match="years_between"):
            with Tapestry():
                prev = _PigRunSource(_config=KnotConfig(id="prev"))
                cur = _PigRunSource(_config=KnotConfig(id="cur"))
                CorrosionRateEstimator(
                    previous_run=prev,
                    current_run=cur,
                    years_between="x",  # type: ignore[arg-type]
                    _config=KnotConfig(id="cre"),
                )

    def test_rejects_non_positive_years(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            with Tapestry():
                prev = _PigRunSource(_config=KnotConfig(id="prev"))
                cur = _PigRunSource(_config=KnotConfig(id="cur"))
                CorrosionRateEstimator(
                    previous_run=prev,
                    current_run=cur,
                    years_between=0.0,
                    _config=KnotConfig(id="cre"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_corrosion_rate(self) -> None:
        with Tapestry() as t:
            prev = _PigRunSource(_config=KnotConfig(id="prev"))
            cur = _PigRunSource(_config=KnotConfig(id="cur"))
            CorrosionRateEstimator(
                previous_run=prev,
                current_run=cur,
                years_between=5.0,
                _config=KnotConfig(id="cre"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["cre"]
        assert out["max_rate_mpy"] == 5.0
        assert out["feature_count"] == 10.0

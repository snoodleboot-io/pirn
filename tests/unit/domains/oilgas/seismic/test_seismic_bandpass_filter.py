"""Unit tests for :class:`SeismicBandpassFilter`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.seismic_bandpass_filter import SeismicBandpassFilter
from pirn.tapestry import Tapestry


class _DataSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "traces": [{"samples": [0.0, 1.0, -1.0]}],
            "sample_interval_ms": 4.0,
        }


class TestConstruction:
    def test_rejects_wrong_frequency_order(self) -> None:
        with pytest.raises(ValueError, match="low_cut_hz < low_pass_hz"):
            with Tapestry():
                src = _DataSource(_config=KnotConfig(id="src"))
                SeismicBandpassFilter(
                    data=src,
                    low_cut_hz=10.0,
                    low_pass_hz=5.0,
                    high_pass_hz=80.0,
                    high_cut_hz=100.0,
                    _config=KnotConfig(id="sbf"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_filtered_data(self) -> None:
        with Tapestry() as t:
            src = _DataSource(_config=KnotConfig(id="src"))
            SeismicBandpassFilter(
                data=src,
                low_cut_hz=5.0,
                low_pass_hz=10.0,
                high_pass_hz=80.0,
                high_cut_hz=100.0,
                _config=KnotConfig(id="sbf"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["sbf"]
        assert out["filtered"] is True
        assert "traces" in out

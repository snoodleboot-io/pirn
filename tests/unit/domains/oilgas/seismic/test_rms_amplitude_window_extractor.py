"""Unit tests for :class:`RMSAmplitudeWindowExtractor`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.rms_amplitude_window_extractor import (
    RMSAmplitudeWindowExtractor,
)
from pirn.tapestry import Tapestry


class _VolumeSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"traces": []}


class _HorizonSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "picks": [
                {"inline": 100, "crossline": 200, "time_ms": 1500.0},
                {"inline": 101, "crossline": 200, "time_ms": 1502.0},
            ]
        }


class TestConstruction:
    def test_rejects_non_positive_window(self) -> None:
        with pytest.raises(ValueError, match="window_ms_above"):
            with Tapestry():
                vol = _VolumeSource(_config=KnotConfig(id="vol"))
                hor = _HorizonSource(_config=KnotConfig(id="hor"))
                RMSAmplitudeWindowExtractor(
                    volume=vol,
                    horizon=hor,
                    window_ms_above=0.0,
                    window_ms_below=20.0,
                    _config=KnotConfig(id="rms"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_rms_map(self) -> None:
        with Tapestry() as t:
            vol = _VolumeSource(_config=KnotConfig(id="vol"))
            hor = _HorizonSource(_config=KnotConfig(id="hor"))
            RMSAmplitudeWindowExtractor(
                volume=vol,
                horizon=hor,
                window_ms_above=20.0,
                window_ms_below=20.0,
                _config=KnotConfig(id="rms"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["rms"]
        assert "rms_map" in out
        assert len(out["rms_map"]) == 2
        assert out["window_ms"] == 40.0

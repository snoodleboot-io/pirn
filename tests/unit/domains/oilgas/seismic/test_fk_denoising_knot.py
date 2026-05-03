"""Unit tests for :class:`FKDenoisingKnot`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.fk_denoising_knot import FKDenoisingKnot
from pirn.tapestry import Tapestry


class _GatherSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {
            "traces": [
                {"offset_m": 100.0, "samples": [0.0, 1.0, 0.5]},
                {"offset_m": 200.0, "samples": [0.1, 0.9, 0.4]},
            ]
        }


class TestConstruction:
    def test_rejects_non_positive_velocity(self) -> None:
        with pytest.raises(ValueError, match="velocity_threshold_m_s"):
            with Tapestry():
                src = _GatherSource(_config=KnotConfig(id="src"))
                FKDenoisingKnot(
                    gather=src,
                    velocity_threshold_m_s=0.0,
                    taper_width_pct=10.0,
                    _config=KnotConfig(id="fk"),
                )

    def test_rejects_invalid_taper_width(self) -> None:
        with pytest.raises(ValueError, match="taper_width_pct"):
            with Tapestry():
                src = _GatherSource(_config=KnotConfig(id="src"))
                FKDenoisingKnot(
                    gather=src,
                    velocity_threshold_m_s=1500.0,
                    taper_width_pct=60.0,
                    _config=KnotConfig(id="fk"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_denoised_gather(self) -> None:
        with Tapestry() as t:
            src = _GatherSource(_config=KnotConfig(id="src"))
            FKDenoisingKnot(
                gather=src,
                velocity_threshold_m_s=1500.0,
                taper_width_pct=10.0,
                _config=KnotConfig(id="fk"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["fk"]
        assert "denoised_traces" in out
        assert "noise_model" in out
        assert isinstance(out["denoised_traces"], list)

"""Unit tests for :class:`DepthShiftCorrector`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.well.depth_shift_corrector import DepthShiftCorrector
from pirn.tapestry import Tapestry


class _LogSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> list[dict[str, Any]]:
        return [
            {"depth_ft": 1000.0, "value": 0.15},
            {"depth_ft": 1001.0, "value": 0.16},
        ]


class TestConstruction:
    def test_rejects_non_numeric_shift(self) -> None:
        with pytest.raises(TypeError, match="shift_ft"):
            with Tapestry():
                src = _LogSource(_config=KnotConfig(id="src"))
                DepthShiftCorrector(
                    log_curve=src,
                    shift_ft="five",  # type: ignore[arg-type]
                    _config=KnotConfig(id="dsc"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_shifts_depths(self) -> None:
        with Tapestry() as t:
            src = _LogSource(_config=KnotConfig(id="src"))
            DepthShiftCorrector(
                log_curve=src, shift_ft=5.0, _config=KnotConfig(id="dsc")
            )
        result = await t.run(RunRequest())
        out = result.outputs["dsc"]
        assert out[0]["depth_ft"] == pytest.approx(1005.0)
        assert out[1]["depth_ft"] == pytest.approx(1006.0)
        assert out[0]["value"] == 0.15

    async def test_zero_shift_unchanged(self) -> None:
        with Tapestry() as t:
            src = _LogSource(_config=KnotConfig(id="src"))
            DepthShiftCorrector(
                log_curve=src, shift_ft=0.0, _config=KnotConfig(id="dsc")
            )
        result = await t.run(RunRequest())
        out = result.outputs["dsc"]
        assert out[0]["depth_ft"] == pytest.approx(1000.0)

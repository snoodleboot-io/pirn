"""Unit tests for :class:`AccelerometerActivityClassifier`."""

from __future__ import annotations

from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.wearables.accelerometer_activity_classifier import (
    AccelerometerActivityClassifier,
)
from pirn.tapestry import Tapestry


@knot
async def emit_accel_data() -> dict[str, Any]:
    return {
        "x": [0.1, 0.2, 0.3, 0.4, 0.5],
        "y": [0.0, 0.1, 0.2, 0.1, 0.0],
        "z": [9.8, 9.7, 9.8, 9.9, 9.8],
        "timestamps_iso": [
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:00:01Z",
            "2024-01-01T00:00:02Z",
            "2024-01-01T00:00:03Z",
            "2024-01-01T00:00:04Z",
        ],
    }


class TestConstruction:
    def test_rejects_non_knot_accel_data(self) -> None:
        with pytest.raises(TypeError, match="accel_data"):
            AccelerometerActivityClassifier(
                accel_data="not-a-knot",  # type: ignore[arg-type]
                sample_rate_hz=50.0,
                window_sec=5.0,
                _config=KnotConfig(id="ac"),
            )

    def test_rejects_non_positive_sample_rate(self) -> None:
        with Tapestry():
            a = emit_accel_data(_config=KnotConfig(id="a"))
            with pytest.raises(ValueError, match="sample_rate_hz"):
                AccelerometerActivityClassifier(
                    accel_data=a,
                    sample_rate_hz=0.0,
                    window_sec=5.0,
                    _config=KnotConfig(id="ac"),
                )

    def test_rejects_non_positive_window_sec(self) -> None:
        with Tapestry():
            a = emit_accel_data(_config=KnotConfig(id="a"))
            with pytest.raises(ValueError, match="window_sec"):
                AccelerometerActivityClassifier(
                    accel_data=a,
                    sample_rate_hz=50.0,
                    window_sec=0.0,
                    _config=KnotConfig(id="ac"),
                )

    def test_rejects_empty_activity_classes(self) -> None:
        with Tapestry():
            a = emit_accel_data(_config=KnotConfig(id="a"))
            with pytest.raises(ValueError, match="activity_classes"):
                AccelerometerActivityClassifier(
                    accel_data=a,
                    sample_rate_hz=50.0,
                    window_sec=5.0,
                    activity_classes=(),
                    _config=KnotConfig(id="ac"),
                )


@pytest.mark.asyncio
class TestProcess:
    async def test_returns_list(self) -> None:
        with Tapestry() as t:
            a = emit_accel_data(_config=KnotConfig(id="a"))
            AccelerometerActivityClassifier(
                accel_data=a,
                sample_rate_hz=1.0,
                window_sec=2.0,
                _config=KnotConfig(id="ac"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ac"]
        assert isinstance(out, list)

    async def test_each_window_has_required_keys(self) -> None:
        with Tapestry() as t:
            a = emit_accel_data(_config=KnotConfig(id="a"))
            AccelerometerActivityClassifier(
                accel_data=a,
                sample_rate_hz=1.0,
                window_sec=2.0,
                _config=KnotConfig(id="ac"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ac"]
        assert len(out) > 0
        for window in out:
            assert "start_iso" in window
            assert "end_iso" in window
            assert "activity_class" in window
            assert "vector_magnitude" in window

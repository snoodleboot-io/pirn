"""Unit tests for :class:`AccelerometerActivityClassifier`."""

from __future__ import annotations

import unittest
from typing import Any

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


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_dict_accel_data(self) -> None:
        inst = object.__new__(AccelerometerActivityClassifier)
        with self.assertRaisesRegex(TypeError, "accel_data"):
            await AccelerometerActivityClassifier.process(
                inst,
                accel_data="not-a-dict",  # type: ignore[arg-type]
                sample_rate_hz=50.0,
                window_sec=5.0,
            )

    async def test_rejects_non_positive_sample_rate(self) -> None:
        inst = object.__new__(AccelerometerActivityClassifier)
        with self.assertRaisesRegex(ValueError, "sample_rate_hz"):
            await AccelerometerActivityClassifier.process(
                inst,
                accel_data={},
                sample_rate_hz=0.0,
                window_sec=5.0,
            )

    async def test_rejects_non_positive_window_sec(self) -> None:
        inst = object.__new__(AccelerometerActivityClassifier)
        with self.assertRaisesRegex(ValueError, "window_sec"):
            await AccelerometerActivityClassifier.process(
                inst,
                accel_data={},
                sample_rate_hz=50.0,
                window_sec=0.0,
            )

    async def test_rejects_empty_activity_classes(self) -> None:
        inst = object.__new__(AccelerometerActivityClassifier)
        with self.assertRaisesRegex(ValueError, "activity_classes"):
            await AccelerometerActivityClassifier.process(
                inst,
                accel_data={},
                sample_rate_hz=50.0,
                window_sec=5.0,
                activity_classes=(),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
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

"""Unit tests for :class:`PPGHeartRateExtractor`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.wearables.ppg_heart_rate_extractor import PPGHeartRateExtractor
from pirn.tapestry import Tapestry


@knot
async def emit_ppg_data() -> dict[str, Any]:
    return {
        "red": [0.8, 0.7, 0.9, 0.8, 0.7],
        "ir": [0.9, 0.8, 1.0, 0.9, 0.8],
        "timestamps_iso": [
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:00:01Z",
            "2024-01-01T00:00:02Z",
            "2024-01-01T00:00:03Z",
            "2024-01-01T00:00:04Z",
        ],
    }


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_dict_ppg_data(self) -> None:
        inst = object.__new__(PPGHeartRateExtractor)
        with self.assertRaisesRegex(TypeError, "ppg_data"):
            await PPGHeartRateExtractor.process(
                inst,
                ppg_data="not-a-dict",  # type: ignore[arg-type]
                sample_rate_hz=25.0,
                window_sec=10.0,
            )

    async def test_rejects_non_positive_sample_rate(self) -> None:
        inst = object.__new__(PPGHeartRateExtractor)
        with self.assertRaisesRegex(ValueError, "sample_rate_hz"):
            await PPGHeartRateExtractor.process(
                inst,
                ppg_data={},
                sample_rate_hz=0.0,
                window_sec=10.0,
            )

    async def test_rejects_non_positive_window_sec(self) -> None:
        inst = object.__new__(PPGHeartRateExtractor)
        with self.assertRaisesRegex(ValueError, "window_sec"):
            await PPGHeartRateExtractor.process(
                inst,
                ppg_data={},
                sample_rate_hz=25.0,
                window_sec=-1.0,
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_list(self) -> None:
        with Tapestry() as t:
            p = emit_ppg_data(_config=KnotConfig(id="p"))
            PPGHeartRateExtractor(
                ppg_data=p,
                sample_rate_hz=1.0,
                window_sec=2.0,
                _config=KnotConfig(id="ppg"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ppg"]
        assert isinstance(out, list)

    async def test_each_window_has_required_keys(self) -> None:
        with Tapestry() as t:
            p = emit_ppg_data(_config=KnotConfig(id="p"))
            PPGHeartRateExtractor(
                ppg_data=p,
                sample_rate_hz=1.0,
                window_sec=2.0,
                _config=KnotConfig(id="ppg"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ppg"]
        assert len(out) > 0
        for window in out:
            assert "start_iso" in window
            assert "end_iso" in window
            assert "heart_rate_bpm" in window
            assert "spo2_pct" in window

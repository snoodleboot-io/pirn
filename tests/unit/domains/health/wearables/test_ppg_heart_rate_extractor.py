"""Unit tests for :class:`PPGHeartRateExtractor`."""

from __future__ import annotations

from typing import Any
import unittest


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


class TestConstruction(unittest.TestCase):
    def test_rejects_non_knot_ppg_data(self) -> None:
        with self.assertRaisesRegex(TypeError, "ppg_data"):
            PPGHeartRateExtractor(
                ppg_data="not-a-knot",  # type: ignore[arg-type]
                sample_rate_hz=25.0,
                window_sec=10.0,
                _config=KnotConfig(id="ppg"),
            )

    def test_rejects_non_positive_sample_rate(self) -> None:
        with Tapestry():
            p = emit_ppg_data(_config=KnotConfig(id="p"))
            with self.assertRaisesRegex(ValueError, "sample_rate_hz"):
                PPGHeartRateExtractor(
                    ppg_data=p,
                    sample_rate_hz=0.0,
                    window_sec=10.0,
                    _config=KnotConfig(id="ppg"),
                )

    def test_rejects_non_positive_window_sec(self) -> None:
        with Tapestry():
            p = emit_ppg_data(_config=KnotConfig(id="p"))
            with self.assertRaisesRegex(ValueError, "window_sec"):
                PPGHeartRateExtractor(
                    ppg_data=p,
                    sample_rate_hz=25.0,
                    window_sec=-1.0,
                    _config=KnotConfig(id="ppg"),
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

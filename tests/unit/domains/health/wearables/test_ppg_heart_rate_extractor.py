"""Unit tests for :class:`PPGHeartRateExtractor`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import math
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.core.knot_factory import knot
from pirn.core.run_request import RunRequest
from pirn.domains.health.wearables.ppg_heart_rate_extractor import PPGHeartRateExtractor
from pirn.tapestry import Tapestry

_FS = 25.0  # Hz
_N = 250    # samples — 10 seconds of data, enough for multiple peaks at 1 Hz
# Synthetic PPG: 1 Hz sine (one peak per second) at 25 Hz sample rate
_PPG_WAVE = [math.sin(2 * math.pi * 1.0 * i / _FS) for i in range(_N)]


@knot
async def emit_ppg_data() -> dict[str, Any]:
    return {
        "red": _PPG_WAVE,
        "ir": _PPG_WAVE,
        "timestamps_iso": [f"2024-01-01T00:00:{i // int(_FS):02d}Z" for i in range(_N)],
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
                sample_rate_hz=_FS,
                window_sec=5.0,
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
                sample_rate_hz=_FS,
                window_sec=5.0,
                _config=KnotConfig(id="ppg"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["ppg"]
        assert len(out) > 0
        for window in out:
            assert "hr_bpm" in window
            assert "timestamp_sec" in window

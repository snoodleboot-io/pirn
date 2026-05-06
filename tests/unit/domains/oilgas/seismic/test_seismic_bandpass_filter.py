"""Unit tests for :class:`SeismicBandpassFilter`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.seismic_bandpass_filter import SeismicBandpassFilter

_DATA: dict[str, Any] = {
    "traces": [{"samples": [0.0, 1.0, -1.0]}],
    "sample_interval_ms": 4.0,
}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> SeismicBandpassFilter:
        return SeismicBandpassFilter(
            data=None,  # type: ignore[arg-type]
            low_cut_hz=5.0,
            low_pass_hz=10.0,
            high_pass_hz=80.0,
            high_cut_hz=100.0,
            _config=KnotConfig(id="sbf", validate_io=False),
        )

    async def test_rejects_wrong_frequency_order(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "low_cut_hz < low_pass_hz"):
            await knot.process(
                data=_DATA,
                low_cut_hz=10.0,
                low_pass_hz=5.0,
                high_pass_hz=80.0,
                high_cut_hz=100.0,
            )

    async def test_returns_filtered_data(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            data=_DATA,
            low_cut_hz=5.0,
            low_pass_hz=10.0,
            high_pass_hz=80.0,
            high_cut_hz=100.0,
        )
        assert out["filtered"] is True
        assert "traces" in out

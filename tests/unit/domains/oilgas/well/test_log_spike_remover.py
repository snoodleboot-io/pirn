"""Unit tests for :class:`LogSpikeRemover`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.well.log_spike_remover import LogSpikeRemover

_SPIKED: list[dict[str, Any]] = [
    {"depth_ft": float(d), "value": 1.0 if d != 5 else 100.0}
    for d in range(1, 12)
]
_CLEAN: list[dict[str, Any]] = [
    {"depth_ft": float(d), "value": 1.0} for d in range(1, 12)
]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> LogSpikeRemover:
        return LogSpikeRemover(
            log_curve=None,  # type: ignore[arg-type]
            window_size=5,
            mad_threshold=2.0,
            _config=KnotConfig(id="lsr", validate_io=False),
        )

    async def test_rejects_even_window_size(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "window_size"):
            await knot.process(log_curve=_SPIKED, window_size=4, mad_threshold=3.0)

    async def test_rejects_window_size_one(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "window_size"):
            await knot.process(log_curve=_SPIKED, window_size=1, mad_threshold=3.0)

    async def test_removes_spike(self) -> None:
        knot = self._make_knot()
        out = await knot.process(log_curve=_SPIKED, window_size=5, mad_threshold=2.0)
        assert isinstance(out, list)
        assert len(out) == 11
        spike_entry = next(e for e in out if e["depth_ft"] == 5.0)
        assert spike_entry["spike_removed"] is True

    async def test_no_spike_flag_on_clean_data(self) -> None:
        knot = self._make_knot()
        out = await knot.process(log_curve=_CLEAN, window_size=5, mad_threshold=2.0)
        assert all(not e["spike_removed"] for e in out)

"""Unit tests for :class:`DepthShiftCorrector`."""

from __future__ import annotations

import unittest
from typing import Any

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.well.depth_shift_corrector import DepthShiftCorrector

_LOG: list[dict[str, Any]] = [
    {"depth_ft": 1000.0, "value": 0.15},
    {"depth_ft": 1001.0, "value": 0.16},
]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> DepthShiftCorrector:
        return DepthShiftCorrector(
            log_curve=None,  # type: ignore[arg-type]
            shift_ft=5.0,
            _config=KnotConfig(id="dsc", validate_io=False),
        )

    async def test_rejects_non_numeric_shift(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "shift_ft"):
            await knot.process(log_curve=_LOG, shift_ft="five")  # type: ignore[arg-type]

    async def test_shifts_depths(self) -> None:
        knot = self._make_knot()
        out = await knot.process(log_curve=_LOG, shift_ft=5.0)
        assert out[0]["depth_ft"] == pytest.approx(1005.0)
        assert out[1]["depth_ft"] == pytest.approx(1006.0)
        assert out[0]["value"] == 0.15

    async def test_zero_shift_unchanged(self) -> None:
        knot = self._make_knot()
        out = await knot.process(log_curve=_LOG, shift_ft=0.0)
        assert out[0]["depth_ft"] == pytest.approx(1000.0)

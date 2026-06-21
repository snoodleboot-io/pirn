"""Unit tests for :class:`CoreToLogDepthMatcher`."""

from __future__ import annotations

import unittest
from typing import Any

from pirn.core.knot_config import KnotConfig
from pirn_oilgas.well.core_to_log_depth_matcher import CoreToLogDepthMatcher

_CORE: list[dict[str, Any]] = [
    {"depth_ft": 1000.0, "value": 0.15},
    {"depth_ft": 1005.0, "value": 0.18},
]
_LOG: list[dict[str, Any]] = [
    {"depth_ft": 1001.5, "value": 0.14},
    {"depth_ft": 1006.0, "value": 0.17},
]


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> CoreToLogDepthMatcher:
        return CoreToLogDepthMatcher(
            core_data=None,  # type: ignore[arg-type]
            log_data=None,  # type: ignore[arg-type]
            max_shift_ft=5.0,
            _config=KnotConfig(id="cdm", validate_io=False),
        )

    async def test_rejects_non_positive_max_shift(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "max_shift_ft"):
            await knot.process(core_data=_CORE, log_data=_LOG, max_shift_ft=0.0)

    async def test_matches_depths(self) -> None:
        knot = self._make_knot()
        out = await knot.process(core_data=_CORE, log_data=_LOG, max_shift_ft=5.0)
        assert isinstance(out, list)
        assert len(out) == 2
        assert "core_depth_ft" in out[0]
        assert "matched_log_depth_ft" in out[0]
        assert "shift_ft" in out[0]

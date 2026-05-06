"""Unit tests for :class:`SeismicQCGate`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.seismic_qc_gate import SeismicQCGate

_PASSING: dict[str, Any] = {"traces": [{"samples": [1.0]}] * 10, "fold": 20}
_LOW_FOLD: dict[str, Any] = {"traces": [], "fold": 5}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> SeismicQCGate:
        return SeismicQCGate(
            data=None,  # type: ignore[arg-type]
            max_null_pct=10.0,
            min_fold=10,
            max_amplitude=10000.0,
            _config=KnotConfig(id="qc", validate_io=False),
        )

    async def test_rejects_out_of_range_null_pct(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "max_null_pct"):
            await knot.process(
                data=_PASSING,
                max_null_pct=110.0,
                min_fold=10,
                max_amplitude=10000.0,
            )

    async def test_passes_valid_data(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            data=_PASSING,
            max_null_pct=10.0,
            min_fold=10,
            max_amplitude=10000.0,
        )
        assert out["passed"] is True
        assert out["trace_count"] == 10

    async def test_raises_on_low_fold(self) -> None:
        knot = self._make_knot()
        with self.assertRaises(ValueError):
            await knot.process(
                data=_LOW_FOLD,
                max_null_pct=10.0,
                min_fold=10,
                max_amplitude=10000.0,
            )

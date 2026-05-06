"""Unit tests for :class:`TypeCurveFitter`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.type_curve_fitter import TypeCurveFitter
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaTimeSeries(sensor_id="s")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> TypeCurveFitter:
        return TypeCurveFitter(
            rate_series=None,  # type: ignore[arg-type]
            _config=KnotConfig(id="tc", validate_io=False),
        )

    async def test_returns_eur(self) -> None:
        knot = self._make_knot()
        out = await knot.process(rate_series=_SERIES)
        assert "qi" in out
        assert "eur_stb" in out

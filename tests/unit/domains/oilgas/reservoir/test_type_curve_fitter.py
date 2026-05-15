"""Unit tests for :class:`TypeCurveFitter`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.reservoir.type_curve_fitter import TypeCurveFitter
from pirn.domains.oilgas.types.scada_payload import ScadaPayload
from pirn.domains.oilgas.types.scada_time_series import ScadaTimeSeries

_SERIES = ScadaPayload(
    metadata=ScadaTimeSeries(sensor_id="s", sample_count=12, sample_interval_sec=86400.0),
    data=np.linspace(1000.0, 400.0, 12),
)


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

"""Unit tests for :class:`AcousticImpedanceInverter`."""

from __future__ import annotations

from typing import Any
import unittest

from pirn.core.knot_config import KnotConfig
from pirn.domains.oilgas.seismic.acoustic_impedance_inverter import (
    AcousticImpedanceInverter,
)

_SEISMIC: dict[str, Any] = {"shape": [100, 100, 500], "data": []}
_WAVELET: dict[str, Any] = {"samples": [0.0, 1.0, 0.0], "sample_rate_hz": 250.0}
_LF_MODEL: dict[str, Any] = {"impedance": [], "shape": [100, 100, 500]}


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> AcousticImpedanceInverter:
        return AcousticImpedanceInverter(
            seismic_volume=None,  # type: ignore[arg-type]
            wavelet=None,  # type: ignore[arg-type]
            low_frequency_model=None,  # type: ignore[arg-type]
            regularization=0.01,
            _config=KnotConfig(id="aii", validate_io=False),
        )

    async def test_rejects_negative_regularization(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(ValueError, "regularization"):
            await knot.process(
                seismic_volume=_SEISMIC,
                wavelet=_WAVELET,
                low_frequency_model=_LF_MODEL,
                regularization=-1.0,
            )

    async def test_returns_impedance_volume(self) -> None:
        knot = self._make_knot()
        out = await knot.process(
            seismic_volume=_SEISMIC,
            wavelet=_WAVELET,
            low_frequency_model=_LF_MODEL,
            regularization=0.01,
        )
        assert "impedance_volume" in out
        assert "misfit" in out
        assert isinstance(out["misfit"], float)

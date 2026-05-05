"""Unit tests for :class:`AcousticImpedanceInverter`."""

from __future__ import annotations

from typing import Any
import unittest


from pirn.core.knot import Knot
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.oilgas.seismic.acoustic_impedance_inverter import (
    AcousticImpedanceInverter,
)
from pirn.tapestry import Tapestry


class _SeismicSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"shape": [100, 100, 500], "data": []}


class _WaveletSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"samples": [0.0, 1.0, 0.0], "sample_rate_hz": 250.0}


class _LFModelSource(Knot):
    def __init__(self, *, _config: KnotConfig, **kwargs: Any) -> None:
        super().__init__(_config=_config, **kwargs)

    async def process(self, **_: Any) -> dict[str, Any]:
        return {"impedance": [], "shape": [100, 100, 500]}


class TestConstruction(unittest.TestCase):
    def test_rejects_negative_regularization(self) -> None:
        with self.assertRaisesRegex(ValueError, "regularization"):
            with Tapestry():
                sv = _SeismicSource(_config=KnotConfig(id="sv"))
                wv = _WaveletSource(_config=KnotConfig(id="wv"))
                lf = _LFModelSource(_config=KnotConfig(id="lf"))
                AcousticImpedanceInverter(
                    seismic_volume=sv,
                    wavelet=wv,
                    low_frequency_model=lf,
                    regularization=-1.0,
                    _config=KnotConfig(id="aii"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_impedance_volume(self) -> None:
        with Tapestry() as t:
            sv = _SeismicSource(_config=KnotConfig(id="sv"))
            wv = _WaveletSource(_config=KnotConfig(id="wv"))
            lf = _LFModelSource(_config=KnotConfig(id="lf"))
            AcousticImpedanceInverter(
                seismic_volume=sv,
                wavelet=wv,
                low_frequency_model=lf,
                regularization=0.01,
                _config=KnotConfig(id="aii"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["aii"]
        assert "impedance_volume" in out
        assert "misfit" in out
        assert isinstance(out["misfit"], float)

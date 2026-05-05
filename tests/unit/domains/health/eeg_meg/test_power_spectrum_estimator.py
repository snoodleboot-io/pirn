"""Unit tests for :class:`PowerSpectrumEstimator`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.power_spectrum_estimator import (
    PowerSpectrumEstimator,
)
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            PowerSpectrumEstimator(
                signal="x",  # type: ignore[arg-type]
                method="welch",
                _config=KnotConfig(id="p"),
            )

    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            PowerSpectrumEstimator(
                signal=SignalFrame(),
                method="bogus",
                _config=KnotConfig(id="p"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_band_mapping(self) -> None:
        with Tapestry() as t:
            PowerSpectrumEstimator(
                signal=SignalFrame(),
                method="welch",
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, Mapping)
        assert "alpha" in out

"""Unit tests for :class:`TimeFrequencyDecomposer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.time_frequency_decomposer import (
    TimeFrequencyDecomposer,
)
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            TimeFrequencyDecomposer(
                signal="x",  # type: ignore[arg-type]
                frequencies_hz=[10.0],
                method="morlet",
                _config=KnotConfig(id="t"),
            )

    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "frequencies_hz"):
            TimeFrequencyDecomposer(
                signal=SignalFrame(),
                frequencies_hz=42,  # type: ignore[arg-type]
                method="morlet",
                _config=KnotConfig(id="t"),
            )

    def test_rejects_non_positive_freq(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            TimeFrequencyDecomposer(
                signal=SignalFrame(),
                frequencies_hz=[0.0],
                method="morlet",
                _config=KnotConfig(id="t"),
            )

    def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            TimeFrequencyDecomposer(
                signal=SignalFrame(),
                frequencies_hz=[10.0],
                method="bogus",
                _config=KnotConfig(id="t"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_per_freq_mapping(self) -> None:
        with Tapestry() as t:
            TimeFrequencyDecomposer(
                signal=SignalFrame(),
                frequencies_hz=[8.0, 12.0],
                method="morlet",
                _config=KnotConfig(id="t"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["t"]
        assert isinstance(out, Mapping)
        assert 8.0 in out

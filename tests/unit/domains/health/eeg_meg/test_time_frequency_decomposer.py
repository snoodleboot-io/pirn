"""Unit tests for :class:`TimeFrequencyDecomposer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.domains.health.eeg_meg.time_frequency_decomposer import (
    TimeFrequencyDecomposer,
)
from pirn.domains.health.types.signal_frame import SignalFrame


_CFG = KnotConfig(id="t")
_SIGNAL = SignalFrame()
_KNOT = TimeFrequencyDecomposer(signal=_SIGNAL, frequencies_hz=[10.0], method="morlet", _config=_CFG)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            await _KNOT.process(signal="x", frequencies_hz=[10.0], method="morlet")  # type: ignore[arg-type]

    async def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "frequencies_hz"):
            await _KNOT.process(signal=_SIGNAL, frequencies_hz=42, method="morlet")  # type: ignore[arg-type]

    async def test_rejects_non_positive_freq(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            await _KNOT.process(signal=_SIGNAL, frequencies_hz=[0.0], method="morlet")

    async def test_rejects_invalid_method(self) -> None:
        with self.assertRaisesRegex(ValueError, "method"):
            await _KNOT.process(signal=_SIGNAL, frequencies_hz=[10.0], method="bogus")

    async def test_returns_per_freq_mapping(self) -> None:
        out = await _KNOT.process(signal=_SIGNAL, frequencies_hz=[8.0, 12.0], method="morlet")
        assert isinstance(out, Mapping)
        assert 8.0 in out

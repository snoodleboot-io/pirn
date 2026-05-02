"""Unit tests for :class:`TimeFrequencyDecomposer`."""

from __future__ import annotations

from collections.abc import Mapping

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.time_frequency_decomposer import (
    TimeFrequencyDecomposer,
)
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction:
    def test_rejects_non_signal(self) -> None:
        with pytest.raises(TypeError, match="SignalFrame"):
            TimeFrequencyDecomposer(
                signal="x",  # type: ignore[arg-type]
                frequencies_hz=[10.0],
                method="morlet",
                _config=KnotConfig(id="t"),
            )

    def test_rejects_non_sequence(self) -> None:
        with pytest.raises(TypeError, match="frequencies_hz"):
            TimeFrequencyDecomposer(
                signal=SignalFrame(),
                frequencies_hz=42,  # type: ignore[arg-type]
                method="morlet",
                _config=KnotConfig(id="t"),
            )

    def test_rejects_non_positive_freq(self) -> None:
        with pytest.raises(ValueError, match="positive"):
            TimeFrequencyDecomposer(
                signal=SignalFrame(),
                frequencies_hz=[0.0],
                method="morlet",
                _config=KnotConfig(id="t"),
            )

    def test_rejects_invalid_method(self) -> None:
        with pytest.raises(ValueError, match="method"):
            TimeFrequencyDecomposer(
                signal=SignalFrame(),
                frequencies_hz=[10.0],
                method="bogus",
                _config=KnotConfig(id="t"),
            )


@pytest.mark.asyncio
class TestProcess:
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

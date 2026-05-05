"""Unit tests for :class:`CoherenceAnalyzer`."""

from __future__ import annotations

from collections.abc import Mapping
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.coherence_analyzer import CoherenceAnalyzer
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            CoherenceAnalyzer(
                signal="x",  # type: ignore[arg-type]
                channel_pairs=[],
                band_low_hz=1.0,
                band_high_hz=10.0,
                _config=KnotConfig(id="c"),
            )

    def test_rejects_non_sequence_pairs(self) -> None:
        with self.assertRaisesRegex(TypeError, "channel_pairs"):
            CoherenceAnalyzer(
                signal=SignalFrame(),
                channel_pairs=42,  # type: ignore[arg-type]
                band_low_hz=1.0,
                band_high_hz=10.0,
                _config=KnotConfig(id="c"),
            )

    def test_rejects_invalid_pair(self) -> None:
        with self.assertRaisesRegex(TypeError, r"\(str, str\)"):
            CoherenceAnalyzer(
                signal=SignalFrame(),
                channel_pairs=[(1, 2)],  # type: ignore[list-item]
                band_low_hz=1.0,
                band_high_hz=10.0,
                _config=KnotConfig(id="c"),
            )

    def test_rejects_low_ge_high(self) -> None:
        with self.assertRaisesRegex(ValueError, "<"):
            CoherenceAnalyzer(
                signal=SignalFrame(),
                channel_pairs=[],
                band_low_hz=10.0,
                band_high_hz=10.0,
                _config=KnotConfig(id="c"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_per_pair_mapping(self) -> None:
        with Tapestry() as t:
            CoherenceAnalyzer(
                signal=SignalFrame(),
                channel_pairs=[("F3", "F4")],
                band_low_hz=8.0,
                band_high_hz=13.0,
                _config=KnotConfig(id="c"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert isinstance(out, Mapping)
        assert ("F3", "F4") in out

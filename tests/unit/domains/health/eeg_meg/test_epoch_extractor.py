"""Unit tests for :class:`EpochExtractor`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.eeg_meg.epoch_extractor import EpochExtractor
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            EpochExtractor(
                signal="x",  # type: ignore[arg-type]
                event_times_sec=[1.0],
                tmin_sec=-0.2,
                tmax_sec=0.5,
                _config=KnotConfig(id="e"),
            )

    def test_rejects_non_sequence(self) -> None:
        with self.assertRaisesRegex(TypeError, "event_times_sec"):
            EpochExtractor(
                signal=SignalFrame(),
                event_times_sec=42,  # type: ignore[arg-type]
                tmin_sec=-0.2,
                tmax_sec=0.5,
                _config=KnotConfig(id="e"),
            )

    def test_rejects_tmin_ge_tmax(self) -> None:
        with self.assertRaisesRegex(ValueError, "<"):
            EpochExtractor(
                signal=SignalFrame(),
                event_times_sec=[1.0],
                tmin_sec=0.5,
                tmax_sec=0.5,
                _config=KnotConfig(id="e"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_epochs(self) -> None:
        with Tapestry() as t:
            EpochExtractor(
                signal=SignalFrame(
                    signal_id="s",
                    channel_count=4,
                    sample_rate_hz=250.0,
                    samples_per_channel=2500,
                ),
                event_times_sec=[1.0, 2.0, 3.0],
                tmin_sec=-0.2,
                tmax_sec=0.5,
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert isinstance(out, tuple)
        assert len(out) == 3
        assert all(isinstance(x, SignalFrame) for x in out)

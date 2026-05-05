"""Unit tests for :class:`SleepStager`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.health.types.signal_frame import SignalFrame
from pirn.domains.health.wearables.sleep_stager import SleepStager
from pirn.tapestry import Tapestry


class TestConstruction(unittest.TestCase):
    def test_rejects_non_signal(self) -> None:
        with self.assertRaisesRegex(TypeError, "SignalFrame"):
            SleepStager(
                signal="x",  # type: ignore[arg-type]
                epoch_length_sec=30.0,
                _config=KnotConfig(id="s"),
            )

    def test_rejects_non_numeric(self) -> None:
        with self.assertRaisesRegex(TypeError, "epoch_length_sec"):
            SleepStager(
                signal=SignalFrame(),
                epoch_length_sec="x",  # type: ignore[arg-type]
                _config=KnotConfig(id="s"),
            )

    def test_rejects_non_positive(self) -> None:
        with self.assertRaisesRegex(ValueError, "positive"):
            SleepStager(
                signal=SignalFrame(),
                epoch_length_sec=0.0,
                _config=KnotConfig(id="s"),
            )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_returns_stages_tuple(self) -> None:
        with Tapestry() as t:
            SleepStager(
                signal=SignalFrame(
                    sample_rate_hz=100.0,
                    samples_per_channel=12000,
                ),
                epoch_length_sec=30.0,
                _config=KnotConfig(id="s"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["s"]
        assert isinstance(out, tuple)
        assert all(isinstance(x, str) for x in out)

"""Unit tests for :class:`Downsampler`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.downsampler import Downsampler
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_downsample_factor_le_one(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "downsample_factor"):
                Downsampler(
                    signal=sig,
                    downsample_factor=1,
                    _config=KnotConfig(id="d"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            Downsampler(
                signal=sig,
                downsample_factor=4,
                _config=KnotConfig(id="d"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["d"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 250.0
        assert out.samples_per_channel == 256

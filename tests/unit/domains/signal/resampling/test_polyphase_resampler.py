"""Unit tests for :class:`PolyphaseResampler`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.polyphase_resampler import PolyphaseResampler
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_upsample_factor(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "upsample_factor"):
                PolyphaseResampler(
                    signal=sig,
                    upsample_factor=0,
                    downsample_factor=2,
                    filter_length=32,
                    _config=KnotConfig(id="pr"),
                )

    def test_rejects_non_positive_downsample_factor(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "downsample_factor"):
                PolyphaseResampler(
                    signal=sig,
                    upsample_factor=2,
                    downsample_factor=0,
                    filter_length=32,
                    _config=KnotConfig(id="pr"),
                )

    def test_rejects_non_positive_filter_length(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "filter_length"):
                PolyphaseResampler(
                    signal=sig,
                    upsample_factor=2,
                    downsample_factor=2,
                    filter_length=0,
                    _config=KnotConfig(id="pr"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            PolyphaseResampler(
                signal=sig,
                upsample_factor=3,
                downsample_factor=2,
                filter_length=32,
                _config=KnotConfig(id="pr"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["pr"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 1500.0
        assert out.samples_per_channel == 1536

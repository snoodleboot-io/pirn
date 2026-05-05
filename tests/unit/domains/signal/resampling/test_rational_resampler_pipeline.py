"""Unit tests for :class:`RationalResamplerPipeline`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.resampling.rational_resampler_pipeline import (
    RationalResamplerPipeline,
)
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_non_positive_upsample_factor(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "upsample_factor"):
                RationalResamplerPipeline(
                    signal=sig,
                    upsample_factor=0,
                    downsample_factor=2,
                    _config=KnotConfig(id="r"),
                )

    def test_rejects_non_positive_downsample_factor(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "downsample_factor"):
                RationalResamplerPipeline(
                    signal=sig,
                    upsample_factor=2,
                    downsample_factor=0,
                    _config=KnotConfig(id="r"),
                )

    def test_simplifies_ratio_via_gcd(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            r = RationalResamplerPipeline(
                signal=sig,
                upsample_factor=4,
                downsample_factor=8,
                _config=KnotConfig(id="r"),
            )
            assert r.upsample_factor == 1
            assert r.downsample_factor == 2


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            RationalResamplerPipeline(
                signal=sig,
                upsample_factor=3,
                downsample_factor=2,
                _config=KnotConfig(id="r"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["r"]
        assert isinstance(out, SignalFrame)
        assert out.sample_rate_hz == 1500.0

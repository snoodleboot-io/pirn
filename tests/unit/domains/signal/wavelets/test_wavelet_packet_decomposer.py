"""Unit tests for :class:`WaveletPacketDecomposer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.types.wavelet_frame import WaveletFrame
from pirn.domains.signal.wavelets.wavelet_packet_decomposer import (
    WaveletPacketDecomposer,
)
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.TestCase):
    def test_rejects_empty_wavelet_name(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "non-empty"):
                WaveletPacketDecomposer(
                    signal=sig,
                    wavelet_name="",
                    level_count=3,
                    _config=KnotConfig(id="w"),
                )

    def test_rejects_non_positive_level_count(self) -> None:
        with Tapestry():
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            with self.assertRaisesRegex(ValueError, "level_count"):
                WaveletPacketDecomposer(
                    signal=sig,
                    wavelet_name="db4",
                    level_count=0,
                    _config=KnotConfig(id="w"),
                )


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_wavelet_frame_with_packet_count(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            WaveletPacketDecomposer(
                signal=sig,
                wavelet_name="db4",
                level_count=4,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, WaveletFrame)
        assert out.wavelet_name == "db4"
        assert out.scale_count == 16

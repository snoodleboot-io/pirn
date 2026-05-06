"""Unit tests for :class:`HilbertTransformer`."""

from __future__ import annotations
import unittest


from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.hilbert_transformer import HilbertTransformer
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_frame


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_analytic_signal_frame(self) -> None:
        with Tapestry():
            k = HilbertTransformer.__new__(HilbertTransformer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        signal = SignalFrame(
            signal_id="s", channel_count=2, sample_rate_hz=44100.0, samples_per_channel=512
        )
        result = await k.process(signal=signal)
        assert isinstance(result, SignalFrame)
        assert result.signal_id == "s:analytic"
        assert result.channel_count == 2
        assert result.sample_rate_hz == 44100.0


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_signal_frame_with_analytic_marker(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_frame(_config=KnotConfig(id="sig"))
            HilbertTransformer(signal=sig, _config=KnotConfig(id="h"))
        result = await t.run(RunRequest())
        out = result.outputs["h"]
        assert isinstance(out, SignalFrame)
        assert out.signal_id == "test:analytic"
        assert out.sample_rate_hz == 1000.0

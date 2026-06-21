"""Unit tests for :class:`HilbertTransformer`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_signal.spectral.hilbert_transformer import HilbertTransformer
from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_payload import SpectrumPayload

from tests.conftest import emit_signal_payload


def _make_signal_payload(
    signal_id: str = "s",
    channel_count: int = 1,
    sample_rate_hz: float = 44100.0,
    samples: int = 512,
) -> SignalPayload:
    frame = SignalFrame(
        signal_id=signal_id,
        channel_count=channel_count,
        sample_rate_hz=sample_rate_hz,
        samples_per_channel=samples,
    )
    return SignalPayload(metadata=frame, data=np.zeros(samples))


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_process_returns_analytic_spectrum_payload(self) -> None:
        with Tapestry():
            k = HilbertTransformer.__new__(HilbertTransformer)
            object.__setattr__(k, "_config", KnotConfig(id="x"))
        signal = _make_signal_payload(signal_id="s", channel_count=2, sample_rate_hz=44100.0, samples=512)
        result = await k.process(signal=signal)
        assert isinstance(result, SpectrumPayload)
        assert result.frame.signal_id == "s:analytic"
        assert result.frame.frequency_bins == 512


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_payload_with_analytic_marker(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            HilbertTransformer(signal=sig, _config=KnotConfig(id="h"))
        result = await t.run(RunRequest())
        out = result.outputs["h"]
        assert isinstance(out, SpectrumPayload)
        assert out.frame.signal_id == "test:analytic"
        assert out.frame.frequency_resolution_hz > 0

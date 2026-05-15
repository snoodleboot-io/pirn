"""Unit tests for :class:`WelchEstimator`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.domains.signal.spectral.welch_estimator import WelchEstimator
from pirn.domains.signal.types.signal_frame import SignalFrame
from pirn.domains.signal.types.signal_payload import SignalPayload
from pirn.domains.signal.types.spectrum_payload import SpectrumPayload
from pirn.tapestry import Tapestry
from tests.unit.domains.signal.conftest import emit_signal_payload


def _make_signal_payload(samples: int = 1024) -> SignalPayload:
    frame = SignalFrame(
        signal_id="test",
        channel_count=1,
        sample_rate_hz=1000.0,
        samples_per_channel=samples,
    )
    return SignalPayload(metadata=frame, data=np.zeros(samples))


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_segment_length(self) -> None:
        with Tapestry():
            k = WelchEstimator.__new__(WelchEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="w"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, segment_length=0)

    async def test_rejects_negative_overlap(self) -> None:
        with Tapestry():
            k = WelchEstimator.__new__(WelchEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="w"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, segment_length=64, overlap=-1)

    async def test_rejects_overlap_ge_segment_length(self) -> None:
        with Tapestry():
            k = WelchEstimator.__new__(WelchEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="w"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, segment_length=64, overlap=64)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            WelchEstimator(
                signal=sig,
                segment_length=128,
                overlap=64,
                _config=KnotConfig(id="w"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["w"]
        assert isinstance(out, SpectrumPayload)
        assert out.frame.frequency_bins == 65
        assert out.frame.signal_id == "test"

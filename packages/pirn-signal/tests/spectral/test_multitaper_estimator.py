"""Unit tests for :class:`MultitaperEstimator`."""

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
from pirn_signal.spectral.multitaper_estimator import MultitaperEstimator
from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.spectrum_payload import SpectrumPayload

from tests.conftest import emit_signal_payload


def _make_signal_payload(samples: int = 1024) -> SignalPayload:
    frame = SignalFrame(
        signal_id="test",
        channel_count=1,
        sample_rate_hz=1000.0,
        samples_per_channel=samples,
    )
    return SignalPayload(metadata=frame, data=np.zeros(samples))


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_time_bandwidth(self) -> None:
        with Tapestry():
            k = MultitaperEstimator.__new__(MultitaperEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="m"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, time_bandwidth=0, taper_count=4)

    async def test_rejects_non_positive_taper_count(self) -> None:
        with Tapestry():
            k = MultitaperEstimator.__new__(MultitaperEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="m"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, time_bandwidth=4.0, taper_count=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            MultitaperEstimator(
                signal=sig,
                time_bandwidth=4.0,
                taper_count=7,
                _config=KnotConfig(id="m"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["m"]
        assert isinstance(out, SpectrumPayload)
        assert out.frame.frequency_bins == 1024 // 2 + 1

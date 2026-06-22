"""Unit tests for :class:`BartlettPSDEstimator`."""

from __future__ import annotations

import unittest

try:
    import scipy  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("scipy not installed") from _e

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry
from pirn_signal.spectral.bartlett_psd_estimator import BartlettPSDEstimator
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


class TestBartlettPSDEstimator(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_num_segments(self) -> None:
        with Tapestry():
            k = BartlettPSDEstimator.__new__(BartlettPSDEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="bpsd"))
        signal = _make_signal_payload()
        with pytest.raises(ValueError, match="num_segments"):
            await k.process(signal=signal, num_segments=0)

    async def test_emits_spectrum_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            BartlettPSDEstimator(
                signal=sig,
                num_segments=4,
                _config=KnotConfig(id="bpsd"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["bpsd"]
        assert isinstance(out, SpectrumPayload)
        assert out.frame.signal_id == "test"

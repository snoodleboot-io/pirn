"""Unit tests for :class:`PisarenkoEstimator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.statistical.pisarenko_estimator import PisarenkoEstimator
from pirn_signal.types.feature_payload import FeaturePayload
from tests.conftest import emit_signal_payload, make_signal_payload


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_sinusoid_count(self) -> None:
        with Tapestry():
            k = PisarenkoEstimator.__new__(PisarenkoEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="p"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, sinusoid_count=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_feature_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            PisarenkoEstimator(
                signal=sig,
                sinusoid_count=3,
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, FeaturePayload)
        assert out.metadata.feature_names == ("freq_0", "freq_1", "freq_2")
        assert out.data.shape == (1, 3)

    async def test_multichannel_computes_per_channel(self) -> None:
        with Tapestry():
            k = PisarenkoEstimator.__new__(PisarenkoEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="p"))
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=64)
        out = await k.process(signal=multichannel, sinusoid_count=3)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape == (2, 3)

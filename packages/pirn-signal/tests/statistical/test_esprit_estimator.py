"""Unit tests for :class:`ESPRITEstimator`."""

from __future__ import annotations

import unittest

from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.statistical.esprit_estimator import ESPRITEstimator
from pirn_signal.types.feature_payload import FeaturePayload
from tests.conftest import emit_signal_payload, make_signal_payload


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_subspace_dim(self) -> None:
        with Tapestry():
            k = ESPRITEstimator.__new__(ESPRITEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="e"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, signal_subspace_dim=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_feature_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            ESPRITEstimator(
                signal=sig,
                signal_subspace_dim=2,
                _config=KnotConfig(id="e"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["e"]
        assert isinstance(out, FeaturePayload)
        assert out.metadata.feature_names == ("freq_0", "freq_1")
        assert out.data.shape == (1, 2)

    async def test_multichannel_computes_per_channel(self) -> None:
        with Tapestry():
            k = ESPRITEstimator.__new__(ESPRITEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="e"))
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=64)
        out = await k.process(signal=multichannel, signal_subspace_dim=2)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape == (2, 2)

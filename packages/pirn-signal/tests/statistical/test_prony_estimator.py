"""Unit tests for :class:`PronyEstimator`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.statistical.prony_estimator import PronyEstimator
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import emit_signal_payload, make_signal_payload
from tests.reference_signals import ReferenceSignals


class TestConstruction(unittest.IsolatedAsyncioTestCase):
    async def test_rejects_non_positive_component_count(self) -> None:
        with Tapestry():
            k = PronyEstimator.__new__(PronyEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="p"))
        signal = make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, component_count=0)


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_feature_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            PronyEstimator(
                signal=sig,
                component_count=4,
                _config=KnotConfig(id="p"),
            )
        result = await t.run(RunRequest())
        out = result.outputs["p"]
        assert isinstance(out, FeaturePayload)
        assert out.metadata.feature_names == ("pole", "residue")
        assert out.data.shape == (1, 4, 2)

    async def test_multichannel_computes_per_channel(self) -> None:
        with Tapestry():
            k = PronyEstimator.__new__(PronyEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="p"))
        multichannel = make_signal_payload(channel_count=2, samples_per_channel=64)
        out = await k.process(signal=multichannel, component_count=4)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape == (2, 4, 2)


class TestPronyReference(unittest.IsolatedAsyncioTestCase):
    """Recover the poles and residues of a known sum of damped sinusoids.

    A noiseless signal ``x(n) = sum_k A_k z_k^n`` satisfies a linear recurrence whose
    characteristic polynomial has exactly the roots ``z_k`` (Prony 1795; Kay 1988,
    sec. 11.3), so Prony's method must return them to numerical precision.
    """

    @staticmethod
    def _bare() -> PronyEstimator:
        with Tapestry():
            k = PronyEstimator.__new__(PronyEstimator)
            object.__setattr__(k, "_config", KnotConfig(id="p"))
        return k

    async def test_recovers_poles_and_residues_of_two_damped_sinusoids(self) -> None:
        # Arrange: two real damped cosines = four complex-conjugate modes.
        first = np.exp(-0.01 + 0.3j)
        second = np.exp(-0.05 + 1.1j)
        poles = (first, np.conj(first), second, np.conj(second))
        amplitudes = (1.0 + 0.5j, 1.0 - 0.5j, 0.4 - 0.2j, 0.4 + 0.2j)
        samples = ReferenceSignals.damped_exponentials(poles, amplitudes, 200).real
        payload = SignalPayload(
            metadata=make_signal_payload(samples_per_channel=samples.size).metadata,
            data=samples,
        )

        # Act
        out = await self._bare().process(signal=payload, component_count=4)

        # Assert: every generating mode is found, with its residue.
        found = {complex(pole): complex(residue) for pole, residue in out.data[0]}
        for pole, amplitude in zip(poles, amplitudes, strict=True):
            nearest = min(found, key=lambda candidate: abs(candidate - pole))
            assert abs(nearest - pole) < 1e-8, (pole, found)
            assert abs(found[nearest] - amplitude) < 1e-6, (amplitude, found)

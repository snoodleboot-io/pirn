"""Unit tests for :class:`CepstrumAnalyzer`."""

from __future__ import annotations

import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.run_request import RunRequest
from pirn.tapestry import Tapestry

from pirn_signal.spectral.cepstrum_analyzer import CepstrumAnalyzer
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
    async def test_rejects_invalid_kind(self) -> None:
        with Tapestry():
            k = CepstrumAnalyzer.__new__(CepstrumAnalyzer)
            object.__setattr__(k, "_config", KnotConfig(id="c"))
        signal = _make_signal_payload()
        with self.assertRaises((TypeError, ValueError)):
            await k.process(signal=signal, cepstrum_kind="bogus")


class TestProcess(unittest.IsolatedAsyncioTestCase):
    async def test_emits_spectrum_payload(self) -> None:
        with Tapestry() as t:
            sig = emit_signal_payload(_config=KnotConfig(id="sig"))
            CepstrumAnalyzer(signal=sig, _config=KnotConfig(id="c"))
        result = await t.run(RunRequest())
        out = result.outputs["c"]
        assert isinstance(out, SpectrumPayload)
        assert out.metadata.frequency_bins == 1024


class TestEveryCepstrumKindIsDistinct(unittest.IsolatedAsyncioTestCase):
    """All three kinds used to return the real cepstrum."""

    @staticmethod
    def _echo_signal(delay: int = 64, samples: int = 1024) -> SignalPayload:
        """An impulse plus a half-amplitude echo at ``delay`` samples."""
        data = np.zeros(samples)
        data[0] = 1.0
        data[delay] = 0.5
        frame = SignalFrame(
            signal_id="echo",
            channel_count=1,
            sample_rate_hz=1000.0,
            samples_per_channel=samples,
        )
        return SignalPayload(metadata=frame, data=data)

    @staticmethod
    def _knot() -> CepstrumAnalyzer:
        with Tapestry():
            knot = CepstrumAnalyzer.__new__(CepstrumAnalyzer)
            object.__setattr__(knot, "_config", KnotConfig(id="cep"))
        return knot

    async def test_each_kind_returns_its_own_transform(self) -> None:
        payload = self._echo_signal()
        knot = self._knot()

        real = await knot.process(signal=payload, cepstrum_kind="real")
        power = await knot.process(signal=payload, cepstrum_kind="power")
        complex_ = await knot.process(signal=payload, cepstrum_kind="complex")

        assert not np.allclose(real.data, power.data)
        assert not np.allclose(real.data, complex_.data[: real.data.shape[-1]])

    async def test_power_cepstrum_is_the_log_power_spectrum_transform(self) -> None:
        """The power cepstrum is twice the real cepstrum: log|X|^2 = 2 log|X|."""
        payload = self._echo_signal()
        knot = self._knot()

        real = await knot.process(signal=payload, cepstrum_kind="real")
        power = await knot.process(signal=payload, cepstrum_kind="power")

        np.testing.assert_allclose(power.data, 2.0 * np.asarray(real.data), atol=1e-10)

    async def test_every_kind_shows_the_echo_delay(self) -> None:
        # Arrange: an echo at 64 samples puts a cepstral peak at quefrency 64.
        delay = 64
        payload = self._echo_signal(delay=delay)
        knot = self._knot()

        for kind in ("real", "power", "complex"):
            out = await knot.process(signal=payload, cepstrum_kind=kind)
            cepstrum = np.asarray(out.data, dtype=float).reshape(-1)
            # Ignore the low-quefrency region, which the spectral envelope dominates.
            search = cepstrum[10 : cepstrum.size // 2]
            peak = int(np.argmax(np.abs(search))) + 10
            assert peak == delay, (kind, peak)

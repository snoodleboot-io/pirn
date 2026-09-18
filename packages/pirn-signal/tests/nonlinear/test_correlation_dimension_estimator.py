"""Unit tests for :class:`CorrelationDimensionEstimator`."""

from __future__ import annotations

import unittest

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.nonlinear.correlation_dimension_estimator import (
    CorrelationDimensionEstimator,
)
from pirn_signal.types.feature_payload import FeaturePayload
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()
_MULTICHANNEL_SIGNAL = make_signal_payload(channel_count=2, samples_per_channel=256)


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestCorrelationDimensionEstimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> CorrelationDimensionEstimator:
        return CorrelationDimensionEstimator(
            signal=_up(),
            embedding_dim=3,
            radius_min=0.1,
            radius_max=1.0,
            _config=KnotConfig(id="cde"),
        )

    async def test_rejects_non_positive_embedding_dim(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="embedding_dim"):
            await knot.process(_SIGNAL, embedding_dim=0, radius_min=0.1, radius_max=1.0)

    async def test_rejects_non_positive_radius_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="radius_min"):
            await knot.process(_SIGNAL, embedding_dim=3, radius_min=0.0, radius_max=1.0)

    async def test_rejects_radius_max_le_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="radius_max"):
            await knot.process(_SIGNAL, embedding_dim=3, radius_min=1.0, radius_max=0.5)

    async def test_emits_feature_payload(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, embedding_dim=3, radius_min=0.1, radius_max=1.0)
        assert isinstance(out, FeaturePayload)
        assert out.metadata.feature_names == ("correlation_dimension",)
        assert out.data.shape == (1, 1)

    async def test_multichannel_computes_per_channel(self) -> None:
        knot = self._make()
        out = await knot.process(
            _MULTICHANNEL_SIGNAL, embedding_dim=3, radius_min=0.1, radius_max=1.0
        )
        assert isinstance(out, FeaturePayload)
        assert out.metadata.channel_count == 2
        assert out.data.shape == (2, 1)


class TestRadiusBandIsUsed(unittest.IsolatedAsyncioTestCase):
    """``radius_min`` bounds the fitted scaling region instead of being ignored."""

    @staticmethod
    def _lorenz_like() -> SignalPayload:
        """A deterministic quasi-periodic trace with structure at several scales."""
        time = np.linspace(0.0, 40.0, 600)
        data = np.sin(time) + 0.5 * np.sin(np.sqrt(2.0) * time)
        return make_signal_payload(samples_per_channel=data.size).derive("quasi", data)

    def _knot(self) -> CorrelationDimensionEstimator:
        return CorrelationDimensionEstimator(
            signal=_up(),
            embedding_dim=3,
            radius_min=0.01,
            radius_max=1.0,
            _config=KnotConfig(id="cd"),
        )

    async def test_different_radius_bands_give_different_slopes(self) -> None:
        payload = self._lorenz_like()
        knot = self._knot()

        wide = await knot.process(payload, embedding_dim=3, radius_min=0.01, radius_max=2.0)
        narrow = await knot.process(payload, embedding_dim=3, radius_min=0.9, radius_max=2.0)

        assert float(wide.data[0, 0]) != float(narrow.data[0, 0])

    async def test_a_sine_wave_has_a_correlation_dimension_near_one(self) -> None:
        # A pure sine traces a closed curve: its correlation dimension is 1.
        time = np.linspace(0.0, 20.0 * np.pi, 500)
        payload = make_signal_payload(samples_per_channel=time.size).derive("sine", np.sin(time))

        out = await self._knot().process(payload, embedding_dim=3, radius_min=0.05, radius_max=0.5)

        assert 0.7 < float(out.data[0, 0]) < 1.4, float(out.data[0, 0])

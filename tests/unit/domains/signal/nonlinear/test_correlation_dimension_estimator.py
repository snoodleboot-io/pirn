"""Unit tests for :class:`CorrelationDimensionEstimator`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.nonlinear.correlation_dimension_estimator import (
    CorrelationDimensionEstimator,
)
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


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

    async def test_emits_mapping(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, embedding_dim=3, radius_min=0.1, radius_max=1.0)
        assert isinstance(out, dict)
        assert "correlation_dimension" in out

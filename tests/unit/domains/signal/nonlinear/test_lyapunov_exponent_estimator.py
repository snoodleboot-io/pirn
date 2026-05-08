"""Unit tests for :class:`LyapunovExponentEstimator`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.nonlinear.lyapunov_exponent_estimator import LyapunovExponentEstimator
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestLyapunovExponentEstimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> LyapunovExponentEstimator:
        return LyapunovExponentEstimator(
            signal=_up(),
            embedding_dim=3,
            time_delay=1,
            _config=KnotConfig(id="le"),
        )

    async def test_rejects_non_positive_embedding_dim(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="embedding_dim"):
            await knot.process(_SIGNAL, embedding_dim=0, time_delay=1)

    async def test_rejects_non_positive_time_delay(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="time_delay"):
            await knot.process(_SIGNAL, embedding_dim=3, time_delay=0)

    async def test_emits_mapping(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, embedding_dim=3, time_delay=1)
        assert isinstance(out, dict)
        assert "lyapunov_exponent" in out

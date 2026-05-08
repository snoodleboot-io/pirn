"""Unit tests for :class:`HurstExponentEstimator`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.nonlinear.hurst_exponent_estimator import HurstExponentEstimator
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestHurstExponentEstimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> HurstExponentEstimator:
        return HurstExponentEstimator(
            signal=_up(),
            method="rs",
            _config=KnotConfig(id="he"),
        )

    async def test_rejects_unknown_method(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="method"):
            await knot.process(_SIGNAL, method="unknown")

    async def test_emits_mapping(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, method="rs")
        assert isinstance(out, dict)
        assert "hurst_exponent" in out
        assert "signal_id" in out

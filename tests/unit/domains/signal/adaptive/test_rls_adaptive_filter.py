"""Unit tests for :class:`RLSAdaptiveFilter`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.adaptive.rls_adaptive_filter import RLSAdaptiveFilter
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()
_REF = make_signal_payload(signal_id="reference")


def _up(name: str) -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestRLSAdaptiveFilter(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> RLSAdaptiveFilter:
        return RLSAdaptiveFilter(
            signal=_up("signal"),
            reference=_up("reference"),
            filter_length=8,
            forgetting_factor=0.99,
            _config=KnotConfig(id="rls"),
        )

    async def test_rejects_non_positive_filter_length(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="filter_length"):
            await knot.process(_SIGNAL, _REF, filter_length=0, forgetting_factor=0.99)

    async def test_rejects_forgetting_factor_le_zero(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="forgetting_factor"):
            await knot.process(_SIGNAL, _REF, filter_length=8, forgetting_factor=0.0)

    async def test_rejects_forgetting_factor_gt_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="forgetting_factor"):
            await knot.process(_SIGNAL, _REF, filter_length=8, forgetting_factor=1.5)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, _REF, filter_length=8, forgetting_factor=0.99)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:rls"

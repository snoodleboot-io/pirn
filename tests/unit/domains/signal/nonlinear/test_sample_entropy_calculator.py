"""Unit tests for :class:`SampleEntropyCalculator`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.nonlinear.sample_entropy_calculator import SampleEntropyCalculator
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestSampleEntropyCalculator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> SampleEntropyCalculator:
        return SampleEntropyCalculator(
            signal=_up(),
            m=2,
            r=0.2,
            _config=KnotConfig(id="sec"),
        )

    async def test_rejects_non_positive_m(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="m"):
            await knot.process(_SIGNAL, m=0, r=0.2)

    async def test_rejects_non_positive_r(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="r"):
            await knot.process(_SIGNAL, m=2, r=0.0)

    async def test_emits_dict(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, m=2, r=0.2)
        assert isinstance(out, dict)
        assert "value" in out
        assert "embedding_dim" in out

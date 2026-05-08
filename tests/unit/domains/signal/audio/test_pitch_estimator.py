"""Unit tests for :class:`PitchEstimator`."""

from __future__ import annotations

import unittest

import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.audio.pitch_estimator import PitchEstimator
from pirn.domains.signal.types.signal_payload import SignalPayload
from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestPitchEstimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> PitchEstimator:
        return PitchEstimator(
            signal=_up(),
            f_min_hz=80.0,
            f_max_hz=400.0,
            _config=KnotConfig(id="pe"),
        )

    async def test_rejects_non_positive_f_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="f_min_hz"):
            await knot.process(_SIGNAL, f_min_hz=0.0, f_max_hz=400.0)

    async def test_rejects_f_max_le_f_min(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="f_max_hz"):
            await knot.process(_SIGNAL, f_min_hz=400.0, f_max_hz=80.0)

    async def test_rejects_unknown_algorithm(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="algorithm"):
            await knot.process(_SIGNAL, f_min_hz=80.0, f_max_hz=400.0, algorithm="bad")

    async def test_emits_mapping(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, f_min_hz=80.0, f_max_hz=400.0)
        assert isinstance(out, dict)
        assert "f0_hz" in out
        assert "signal_id" in out

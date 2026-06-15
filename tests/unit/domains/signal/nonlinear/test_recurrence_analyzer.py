"""Unit tests for :class:`RecurrenceAnalyzer`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.nonlinear.recurrence_analyzer import RecurrenceAnalyzer
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestRecurrenceAnalyzer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> RecurrenceAnalyzer:
        return RecurrenceAnalyzer(
            signal=_up(),
            embedding_dim=3,
            time_delay=1,
            recurrence_threshold=0.1,
            _config=KnotConfig(id="ra"),
        )

    async def test_rejects_non_positive_embedding_dim(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="embedding_dim"):
            await knot.process(_SIGNAL, embedding_dim=0, time_delay=1, recurrence_threshold=0.1)

    async def test_rejects_non_positive_time_delay(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="time_delay"):
            await knot.process(_SIGNAL, embedding_dim=3, time_delay=0, recurrence_threshold=0.1)

    async def test_rejects_non_positive_threshold(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="recurrence_threshold"):
            await knot.process(_SIGNAL, embedding_dim=3, time_delay=1, recurrence_threshold=0.0)

    async def test_emits_mapping(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, embedding_dim=3, time_delay=1, recurrence_threshold=0.1)
        assert isinstance(out, dict)
        assert "embedding_dim" in out

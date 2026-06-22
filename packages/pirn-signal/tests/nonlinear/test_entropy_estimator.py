"""Unit tests for :class:`EntropyEstimator`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.nonlinear.entropy_estimator import EntropyEstimator
from pirn_signal.types.signal_payload import SignalPayload

from tests.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestEntropyEstimator(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> EntropyEstimator:
        return EntropyEstimator(
            signal=_up(),
            entropy_kind="sample",
            embedding_dim=2,
            _config=KnotConfig(id="ee"),
        )

    async def test_rejects_unknown_entropy_kind(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="entropy_kind"):
            await knot.process(_SIGNAL, entropy_kind="unknown", embedding_dim=2)

    async def test_rejects_non_positive_embedding_dim(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="embedding_dim"):
            await knot.process(_SIGNAL, entropy_kind="sample", embedding_dim=0)

    async def test_emits_mapping(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, entropy_kind="sample", embedding_dim=2)
        assert isinstance(out, dict)
        assert out["entropy_kind"] == "sample"

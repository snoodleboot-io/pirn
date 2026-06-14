"""Unit tests for :class:`SSADecomposer`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.separation.ssa_decomposer import SSADecomposer
from pirn_signal.types.signal_payload import SignalPayload
from pirn_signal.types.source_payload import SourcePayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestSSADecomposer(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> SSADecomposer:
        return SSADecomposer(
            signal=_up(),
            embedding_dim=10,
            component_count=4,
            _config=KnotConfig(id="ssa"),
        )

    async def test_rejects_embedding_dim_le_one(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="embedding_dim"):
            await knot.process(_SIGNAL, embedding_dim=1, component_count=1)

    async def test_rejects_non_positive_component_count(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="component_count"):
            await knot.process(_SIGNAL, embedding_dim=10, component_count=0)

    async def test_rejects_component_count_above_embedding_dim(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="component_count"):
            await knot.process(_SIGNAL, embedding_dim=4, component_count=8)

    async def test_emits_source_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, embedding_dim=10, component_count=4)
        assert isinstance(out, SourcePayload)
        assert out.frame.source_count == 4

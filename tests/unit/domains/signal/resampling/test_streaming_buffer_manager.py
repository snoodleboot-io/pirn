"""Unit tests for :class:`StreamingBufferManager`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.resampling.streaming_buffer_manager import StreamingBufferManager
from pirn_signal.types.signal_payload import SignalPayload

from tests.unit.domains.signal.conftest import make_signal_payload

_SIGNAL = make_signal_payload()


def _up(name: str = "signal") -> Parameter:
    return Parameter(name, SignalPayload, _config=KnotConfig(id=name))


class TestStreamingBufferManager(unittest.IsolatedAsyncioTestCase):
    def _make(self) -> StreamingBufferManager:
        return StreamingBufferManager(
            signal=_up(),
            frame_size=512,
            hop_size=256,
            _config=KnotConfig(id="sbm"),
        )

    async def test_rejects_non_positive_frame_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="frame_size"):
            await knot.process(_SIGNAL, frame_size=0, hop_size=256)

    async def test_rejects_non_positive_hop_size(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="hop_size"):
            await knot.process(_SIGNAL, frame_size=512, hop_size=0)

    async def test_rejects_hop_greater_than_frame(self) -> None:
        knot = self._make()
        with pytest.raises(ValueError, match="hop_size"):
            await knot.process(_SIGNAL, frame_size=128, hop_size=512)

    async def test_emits_signal_frame(self) -> None:
        knot = self._make()
        out = await knot.process(_SIGNAL, frame_size=512, hop_size=256)
        assert isinstance(out, SignalPayload)
        assert out.frame.signal_id == "test:framed"

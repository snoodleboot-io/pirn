"""Unit tests for :class:`StreamingBufferManager`."""

from __future__ import annotations

import unittest

import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.resampling.streaming_buffer_manager import StreamingBufferManager
from pirn_signal.types.signal_payload import SignalPayload
from tests.conftest import make_signal_payload

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
        assert out.metadata.signal_id == "test:framed"

    async def test_mono_signal_frames_are_shaped_channel_first(self) -> None:
        # A single channel still comes back with an explicit channel axis:
        # shape (1, n_frames, frame_size), not the bare (n_frames, frame_size)
        # this knot used to return.
        knot = self._make()
        out = await knot.process(_SIGNAL, frame_size=512, hop_size=256)
        assert out.metadata.channel_count == 1
        assert out.data.shape == (1, 3, 512)

    async def test_multichannel_frames_every_channel_independently(self) -> None:
        # Arrange (PIR-870): before this fix only channel 0 was framed and
        # every other channel's data was silently discarded.
        knot = self._make()
        multichannel = make_signal_payload(channel_count=3, samples_per_channel=1024)

        # Act
        out = await knot.process(multichannel, frame_size=512, hop_size=256)

        # Assert: one framed sub-array per input channel.
        assert isinstance(out, SignalPayload)
        assert out.metadata.channel_count == 3
        assert out.data.shape == (3, 3, 512)

    async def test_a_signal_shorter_than_one_frame_yields_zero_frames_per_channel(self) -> None:
        knot = self._make()
        short = make_signal_payload(channel_count=2, samples_per_channel=100)
        out = await knot.process(short, frame_size=512, hop_size=256)
        assert out.data.shape == (2, 0, 512)

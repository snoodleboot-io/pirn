"""Unit tests for :class:`StreamingBufferManager`."""

from __future__ import annotations

import unittest

import numpy as np
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

    async def test_a_signal_shorter_than_one_frame_is_padded_into_one_frame(self) -> None:
        # Returning zero frames threw the whole signal away.
        knot = self._make()
        short = make_signal_payload(channel_count=2, samples_per_channel=100)

        out = await knot.process(short, frame_size=512, hop_size=256)

        assert out.data.shape == (2, 1, 512)
        np.testing.assert_array_equal(out.data[:, 0, :100], np.atleast_2d(short.data))
        np.testing.assert_array_equal(out.data[:, 0, 100:], np.zeros((2, 412)))
        assert out.metadata.samples_per_channel == 100


class TestNoSamplesAreDropped(unittest.IsolatedAsyncioTestCase):
    """Framing that stopped at the last complete frame lost the tail of every call."""

    def _make(self) -> StreamingBufferManager:
        return StreamingBufferManager(
            signal=_up(),
            frame_size=512,
            hop_size=256,
            _config=KnotConfig(id="sbm"),
        )

    async def test_trailing_samples_survive_as_a_zero_padded_final_frame(self) -> None:
        # Arrange: 1000 samples at F=512/H=256 ends 232 samples past the last
        # complete frame (which covers 0..768).
        sample_count = 1000
        data = np.arange(1, sample_count + 1, dtype=np.float64)
        payload = make_signal_payload(samples_per_channel=sample_count).derive("ramp", data)

        # Act
        out = await self._make().process(payload, frame_size=512, hop_size=256)

        # Assert: three frames (the third zero-padded), and every input sample is in one.
        assert out.data.shape == (1, 3, 512)
        covered = np.zeros(sample_count, dtype=bool)
        for index in range(out.data.shape[1]):
            start = index * 256
            frame = out.data[0, index]
            end = min(start + 512, sample_count)
            np.testing.assert_array_equal(frame[: end - start], data[start:end])
            covered[start:end] = True
        assert covered.all(), "input samples missing from every frame"
        # The padded tail of the last frame is zeros, not stale or dropped data.
        last_start = (out.data.shape[1] - 1) * 256
        np.testing.assert_array_equal(out.data[0, -1, sample_count - last_start :], 0.0)

    async def test_samples_per_channel_reports_the_signal_length_not_the_frame_size(self) -> None:
        sample_count = 1000
        payload = make_signal_payload(samples_per_channel=sample_count).derive(
            "ramp", np.arange(sample_count, dtype=np.float64)
        )

        out = await self._make().process(payload, frame_size=512, hop_size=256)

        assert out.metadata.samples_per_channel == sample_count

    async def test_hop_equal_to_frame_tiles_without_overlap_or_loss(self) -> None:
        data = np.arange(300, dtype=np.float64)
        payload = make_signal_payload(samples_per_channel=300).derive("ramp", data)

        out = await self._make().process(payload, frame_size=128, hop_size=128)

        assert out.data.shape == (1, 3, 128)
        flat = out.data[0].reshape(-1)
        np.testing.assert_array_equal(flat[:300], data)
        np.testing.assert_array_equal(flat[300:], 0.0)

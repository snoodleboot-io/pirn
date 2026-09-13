"""Unit tests for :class:`SignalObjectStoreDisassembler`."""

from __future__ import annotations

import unittest

import pytest

pytest.importorskip("soundfile")

import numpy as np
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter

from pirn_signal.disassemblers.signal_object_store_disassembler import (
    SignalObjectStoreDisassembler,
)
from pirn_signal.types.signal_frame import SignalFrame
from pirn_signal.types.signal_payload import SignalPayload


def _payload_param() -> Parameter:
    return Parameter("payload", SignalPayload, _config=KnotConfig(id="payload"))


def _make() -> SignalObjectStoreDisassembler:
    return SignalObjectStoreDisassembler(
        payload=_payload_param(),
        _config=KnotConfig(id="disassembler"),
    )


def _signal_payload(*, channel_count: int = 1, samples_per_channel: int = 64) -> SignalPayload:
    frame = SignalFrame(
        signal_id="clip-01",
        channel_count=channel_count,
        sample_rate_hz=8000.0,
        samples_per_channel=samples_per_channel,
    )
    shape = (channel_count, samples_per_channel) if channel_count > 1 else (samples_per_channel,)
    data = np.zeros(shape, dtype=np.float32)
    return SignalPayload(metadata=frame, data=data)


class TestSignalObjectStoreDisassembler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_bytes_for_single_channel_payload(self) -> None:
        knot = _make()
        result = await knot.process(payload=_signal_payload())
        assert isinstance(result, bytes)
        assert result.startswith(b"RIFF")

    async def test_returns_bytes_for_multi_channel_payload(self) -> None:
        knot = _make()
        result = await knot.process(payload=_signal_payload(channel_count=2))
        assert isinstance(result, bytes)
        assert len(result) > 0

    async def test_rejects_non_signal_payload(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="payload must be SignalPayload"):
            await knot.process(payload={"not": "a payload"})  # type: ignore[arg-type]

    async def test_rejects_empty_data(self) -> None:
        knot = _make()
        frame = SignalFrame(
            signal_id="empty",
            channel_count=1,
            sample_rate_hz=8000.0,
            samples_per_channel=0,
        )
        empty_payload = SignalPayload(metadata=frame, data=np.zeros(0, dtype=np.float32))
        with pytest.raises(ValueError, match=r"payload\.data must be non-empty"):
            await knot.process(payload=empty_payload)

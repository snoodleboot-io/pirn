"""Unit tests for :class:`SignalObjectStoreAssembler`."""

from __future__ import annotations

import io
import unittest

try:
    import librosa  # noqa: F401
except ImportError as _e:
    raise unittest.SkipTest("librosa not installed") from _e

from unittest.mock import patch

import numpy as np
import pytest

from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn.domains.signal.assemblers.signal_object_store_assembler import SignalObjectStoreAssembler
from pirn.domains.signal.types.signal_payload import SignalPayload


def _body_param() -> Parameter:
    return Parameter("body", bytes, _config=KnotConfig(id="body"))


def _make(signal_id: str = "test-signal") -> SignalObjectStoreAssembler:
    return SignalObjectStoreAssembler(
        body=_body_param(),
        signal_id=signal_id,
        _config=KnotConfig(id="assembler"),
    )


def _fake_decode(body: bytes, signal_id: str) -> SignalPayload:
    from pirn.domains.signal.types.signal_frame import SignalFrame
    data = np.zeros((2, 512), dtype=np.float32)
    frame = SignalFrame(
        signal_id=signal_id,
        channel_count=2,
        sample_rate_hz=44100.0,
        samples_per_channel=512,
    )
    return SignalPayload(metadata=frame, data=data)


class TestSignalObjectStoreAssembler(unittest.IsolatedAsyncioTestCase):

    async def test_returns_signal_payload(self) -> None:
        knot = _make("clip-01")
        with patch(
            "pirn.domains.signal.assemblers.signal_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(body=b"audio-bytes", signal_id="clip-01")
        assert isinstance(result, SignalPayload)

    async def test_metadata_signal_id_matches(self) -> None:
        knot = _make("clip-01")
        with patch(
            "pirn.domains.signal.assemblers.signal_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(body=b"audio-bytes", signal_id="clip-01")
        assert result.frame.signal_id == "clip-01"

    async def test_metadata_channel_count_populated(self) -> None:
        knot = _make("clip-01")
        with patch(
            "pirn.domains.signal.assemblers.signal_object_store_assembler._decode",
            side_effect=_fake_decode,
        ):
            result = await knot.process(body=b"audio-bytes", signal_id="clip-01")
        assert result.frame.channel_count == 2

    async def test_rejects_non_bytes_body(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="body must be bytes"):
            await knot.process(body="not-bytes", signal_id="x")  # type: ignore[arg-type]

    async def test_rejects_non_str_signal_id(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="signal_id must be str"):
            await knot.process(body=b"x", signal_id=123)  # type: ignore[arg-type]

    async def test_rejects_empty_signal_id(self) -> None:
        knot = _make()
        with pytest.raises(ValueError, match="signal_id must be non-empty"):
            await knot.process(body=b"x", signal_id="")

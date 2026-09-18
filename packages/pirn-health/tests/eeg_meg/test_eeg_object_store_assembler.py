"""Unit tests for :class:`EegObjectStoreAssembler` (PIR-873).

The assembler is the read half of the object-store round trip whose write half
is :class:`EegObjectStoreDisassembler`: what one writes the other must read
back unchanged, and bytes that do not decode must fail loudly rather than
become a recording of silence.
"""

from __future__ import annotations

import io
import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig

from pirn_health.assemblers.eeg_object_store_assembler import EegObjectStoreAssembler
from pirn_health.disassemblers.eeg_object_store_disassembler import EegObjectStoreDisassembler
from pirn_health.types.health_signal_frame import HealthSignalFrame
from pirn_health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="a")
_SAMPLE_RATE_HZ = 256.0
_DURATION_SEC = 2.0
_CHANNELS = 3
_SAMPLES = int(_SAMPLE_RATE_HZ * _DURATION_SEC)


def _signal() -> np.ndarray:
    """A distinguishable multi-channel recording: three tones, no zero channel."""
    time = np.arange(_SAMPLES) / _SAMPLE_RATE_HZ
    return np.vstack(
        [np.sin(2 * np.pi * freq * time) for freq in (8.0, 10.0, 12.0)],
    ).astype(np.float32)


def _assembler() -> EegObjectStoreAssembler:
    return EegObjectStoreAssembler(
        body=b"",
        subject_id="subject-1",
        channel_count=_CHANNELS,
        sample_rate_hz=_SAMPLE_RATE_HZ,
        duration_sec=_DURATION_SEC,
        _config=_CFG,
    )


async def _assemble(body: bytes) -> HealthSignalPayload:
    return await _assembler().process(
        body=body,
        subject_id="subject-1",
        channel_count=_CHANNELS,
        sample_rate_hz=_SAMPLE_RATE_HZ,
        duration_sec=_DURATION_SEC,
    )


class TestObjectStoreRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_disassembled_bytes_assemble_back_to_the_same_signal(self) -> None:
        # Arrange: the exact bytes the EEG disassembler uploads.
        data = _signal()
        frame = HealthSignalFrame(
            signal_id="subject-1",
            channel_count=_CHANNELS,
            sample_rate_hz=_SAMPLE_RATE_HZ,
            samples_per_channel=_SAMPLES,
        )
        payload = HealthSignalPayload(metadata=frame, data=data)
        body = await EegObjectStoreDisassembler(
            payload=payload, _config=KnotConfig(id="d")
        ).process(payload=payload)

        # Act
        out = await _assemble(body)

        # Assert: the samples survive, rather than becoming zeros.
        np.testing.assert_array_equal(out.data, data)
        assert out.metadata.samples_per_channel == _SAMPLES
        assert out.metadata.channel_count == _CHANNELS

    async def test_single_array_npz_is_also_accepted(self) -> None:
        data = _signal()
        buffer = io.BytesIO()
        np.savez(buffer, samples=data)

        out = await _assemble(buffer.getvalue())

        np.testing.assert_array_equal(out.data, data)


class TestUndecodableBytes(unittest.IsolatedAsyncioTestCase):
    async def test_non_numpy_bytes_raise_instead_of_returning_zeros(self) -> None:
        with self.assertRaisesRegex(ValueError, "not a NumPy"):
            await _assemble(b"this is not an npy buffer")

    async def test_shape_disagreeing_with_the_frame_raises(self) -> None:
        buffer = io.BytesIO()
        np.save(buffer, np.ones((_CHANNELS + 1, _SAMPLES), dtype=np.float32))

        with self.assertRaisesRegex(ValueError, "declared frame"):
            await _assemble(buffer.getvalue())

    async def test_multi_array_npz_raises(self) -> None:
        buffer = io.BytesIO()
        np.savez(buffer, first=_signal(), second=_signal())

        with self.assertRaisesRegex(ValueError, "exactly one array"):
            await _assemble(buffer.getvalue())

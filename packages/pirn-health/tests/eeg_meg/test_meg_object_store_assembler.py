"""Unit tests for :class:`MegObjectStoreAssembler` (PIR-873).

Mirror of the EEG assembler tests: the MEG assembler must read back exactly
what :class:`MegObjectStoreDisassembler` wrote, and must raise on bytes it
cannot decode instead of substituting zeros.
"""

from __future__ import annotations

import io
import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig

from pirn_health.assemblers.meg_object_store_assembler import MegObjectStoreAssembler
from pirn_health.disassemblers.meg_object_store_disassembler import MegObjectStoreDisassembler
from pirn_health.types.health_signal_frame import HealthSignalFrame
from pirn_health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="a")
_SAMPLE_RATE_HZ = 1000.0
_CHANNELS = 2
_SAMPLES = 512


def _signal() -> np.ndarray:
    time = np.arange(_SAMPLES) / _SAMPLE_RATE_HZ
    return np.vstack([np.cos(2 * np.pi * 40.0 * time), np.sin(2 * np.pi * 7.0 * time)]).astype(
        np.float32
    )


async def _assemble(body: bytes) -> HealthSignalPayload:
    knot = MegObjectStoreAssembler(
        body=b"",
        signal_id="meg-1",
        channel_count=_CHANNELS,
        sample_rate_hz=_SAMPLE_RATE_HZ,
        samples_per_channel=_SAMPLES,
        _config=_CFG,
    )
    return await knot.process(
        body=body,
        signal_id="meg-1",
        channel_count=_CHANNELS,
        sample_rate_hz=_SAMPLE_RATE_HZ,
        samples_per_channel=_SAMPLES,
    )


class TestMegObjectStoreRoundTrip(unittest.IsolatedAsyncioTestCase):
    async def test_disassembled_bytes_assemble_back_to_the_same_signal(self) -> None:
        # Arrange
        data = _signal()
        frame = HealthSignalFrame(
            signal_id="meg-1",
            channel_count=_CHANNELS,
            sample_rate_hz=_SAMPLE_RATE_HZ,
            samples_per_channel=_SAMPLES,
        )
        payload = HealthSignalPayload(metadata=frame, data=data)
        body = await MegObjectStoreDisassembler(
            payload=payload, _config=KnotConfig(id="d")
        ).process(payload=payload)

        # Act
        out = await _assemble(body)

        # Assert
        np.testing.assert_array_equal(out.data, data)

    async def test_undecodable_bytes_raise_instead_of_returning_zeros(self) -> None:
        with self.assertRaisesRegex(ValueError, "not a NumPy"):
            await _assemble(b"\x00\x01\x02 not numpy")

    async def test_wrong_sample_count_raises(self) -> None:
        buffer = io.BytesIO()
        np.save(buffer, np.ones((_CHANNELS, _SAMPLES - 1), dtype=np.float32))

        with self.assertRaisesRegex(ValueError, "declared frame"):
            await _assemble(buffer.getvalue())

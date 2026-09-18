"""Unit tests for :class:`EegObjectStoreDisassembler`."""

from __future__ import annotations

import io
import unittest

import numpy as np
from pirn.core.knot_config import KnotConfig

from pirn_health.disassemblers.eeg_object_store_disassembler import EegObjectStoreDisassembler
from pirn_health.types.health_signal_frame import HealthSignalFrame
from pirn_health.types.health_signal_payload import HealthSignalPayload

_CFG = KnotConfig(id="d")
_FRAME = HealthSignalFrame(signal_id="eeg-1", channel_count=2, sample_rate_hz=256.0)
_PAYLOAD = HealthSignalPayload(metadata=_FRAME, data=np.zeros((2, 4), dtype=np.float32))


class TestProcess(unittest.IsolatedAsyncioTestCase):
    def _make_knot(self) -> EegObjectStoreDisassembler:
        return EegObjectStoreDisassembler(payload=_PAYLOAD, _config=_CFG)

    async def test_rejects_non_payload(self) -> None:
        knot = self._make_knot()
        with self.assertRaisesRegex(TypeError, "EegObjectStoreDisassembler.*HealthSignalPayload"):
            await knot.process(payload="not-a-payload")

    async def test_serialises_to_npy_bytes(self) -> None:
        knot = self._make_knot()
        out = await knot.process(payload=_PAYLOAD)
        assert isinstance(out, bytes)
        round_tripped = np.load(io.BytesIO(out))
        assert np.array_equal(round_tripped, _PAYLOAD.data)

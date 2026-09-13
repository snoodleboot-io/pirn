"""Unit tests for :class:`WaveletObjectStoreDisassembler`."""

from __future__ import annotations

import io
import unittest

import numpy as np
import pytest
from pirn.core.knot_config import KnotConfig
from pirn.core.parameter import Parameter
from pirn_signal.disassemblers.wavelet_object_store_disassembler import (
    WaveletObjectStoreDisassembler,
)
from pirn_signal.types.wavelet_frame import WaveletFrame
from pirn_signal.types.wavelet_payload import WaveletPayload


def _payload_param() -> Parameter:
    return Parameter("payload", WaveletPayload, _config=KnotConfig(id="payload"))


def _make() -> WaveletObjectStoreDisassembler:
    return WaveletObjectStoreDisassembler(
        payload=_payload_param(),
        _config=KnotConfig(id="disassembler"),
    )


def _wavelet_payload(level_count: int = 3) -> WaveletPayload:
    frame = WaveletFrame(signal_id="wav-01", wavelet_name="db4", scale_count=level_count)
    data = [np.arange(4, dtype=float) * (i + 1) for i in range(level_count)]
    return WaveletPayload(metadata=frame, data=data)


class TestWaveletObjectStoreDisassembler(unittest.IsolatedAsyncioTestCase):
    async def test_returns_bytes(self) -> None:
        knot = _make()
        result = await knot.process(payload=_wavelet_payload())
        assert isinstance(result, bytes)
        assert len(result) > 0

    async def test_round_trips_each_level(self) -> None:
        knot = _make()
        payload = _wavelet_payload(level_count=2)
        result = await knot.process(payload=payload)
        with np.load(io.BytesIO(result)) as npz:
            np.testing.assert_array_equal(npz["level_0"], payload.data[0])
            np.testing.assert_array_equal(npz["level_1"], payload.data[1])
            assert str(npz["wavelet_name"]) == "db4"

    async def test_rejects_non_wavelet_payload(self) -> None:
        knot = _make()
        with pytest.raises(TypeError, match="payload must be WaveletPayload"):
            await knot.process(payload={"not": "a payload"})  # type: ignore[arg-type]

    async def test_rejects_empty_level_list(self) -> None:
        knot = _make()
        frame = WaveletFrame(signal_id="empty", wavelet_name="db4", scale_count=0)
        empty_payload = WaveletPayload(metadata=frame, data=[])
        with pytest.raises(ValueError, match="at least one decomposition level"):
            await knot.process(payload=empty_payload)
